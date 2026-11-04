"""Model provider abstraction.

The interface exists from the first commit so that swapping providers is a
configuration change rather than a rewrite, and so tests can substitute a fake
without touching the network.

Nothing here sends patient data anywhere. This module only proves that a
configured key and model are usable; the callers that build prompts out of
patient records come later, behind the PHI gate in `config.ai_blocked_reason`.
"""
import difflib
import logging
from dataclasses import dataclass, field
from typing import Iterator, Protocol

from config import AI_REASONING_LEVELS

logger = logging.getLogger(__name__)

# How many near-miss model IDs to offer when the configured one is absent.
_MAX_SUGGESTIONS = 5


@dataclass
class ProviderStatus:
    """Whether a provider is actually usable, and if not, precisely why.

    Deliberately more granular than a boolean: "the key is wrong" and "the key
    is fine but that model does not exist on this account" need different
    fixes, and collapsing them into one failure message sends the operator
    hunting in the wrong place.
    """

    model: str = ''
    key_configured: bool = False
    key_valid: bool = False
    model_available: bool = False
    suggestions: list = field(default_factory=list)
    message: str = ''

    @property
    def ok(self):
        return self.key_configured and self.key_valid and self.model_available


class Provider(Protocol):
    """What the rest of the app is allowed to assume about a model backend."""

    def check(self) -> ProviderStatus:
        """Verify the configured credentials and model without sending data."""

    def stream_chat(self, messages, **kwargs) -> Iterator[str]:
        """Yield response text incrementally."""


class OpenAIProvider:
    """Provider backed by the OpenAI API."""

    def __init__(self, api_key, model, timeout=60.0, reasoning_effort=''):
        self.api_key = api_key or ''
        self.model = model or ''
        self.timeout = timeout
        self.reasoning_effort = (reasoning_effort or '').strip().lower()

    def _client(self):
        import openai
        return openai.OpenAI(api_key=self.api_key, timeout=self.timeout)

    def check(self):
        """Confirm the key authenticates *and* the configured model exists.

        Checking only the key would let a wrong or retired model ID sit
        silently in configuration until it surfaced as a failed request in
        front of a clinician mid-consultation. Listing the account's models is
        one cheap call that moves that failure to the settings page, where it
        can be fixed.
        """
        status = ProviderStatus(model=self.model)

        if not self.api_key:
            status.message = ('No API key is configured. Set OPENAI_API_KEY in '
                              'the environment and restart.')
            return status
        status.key_configured = True

        if not self.model:
            status.message = 'No model is configured. Set AI_MODEL.'
            return status

        try:
            import openai
        except ImportError:
            status.message = 'The openai package is not installed.'
            return status

        try:
            available = [model.id for model in self._client().models.list()]
        except openai.AuthenticationError:
            status.message = 'The configured key was rejected as invalid or expired.'
            return status
        except openai.APIError as exc:
            logger.warning('AI provider check failed: %s', type(exc).__name__)
            status.message = 'The AI provider returned an error.'
            return status
        except Exception:
            # Never let a settings page take the process down.
            logger.exception('Unexpected error during AI provider check')
            status.message = 'The provider could not be checked. Try again.'
            return status

        status.key_valid = True

        bare_model = self.model[len('openai/'):] if self.model.startswith('openai/') else self.model
        if self.model in available or bare_model in available:
            status.model_available = True
            status.message = f'Key accepted, and "{self.model}" is available on this account.'
            return status

        status.suggestions = difflib.get_close_matches(
            bare_model, available, n=_MAX_SUGGESTIONS, cutoff=0.3
        ) or sorted(available)[:_MAX_SUGGESTIONS]
        status.message = (
            f'The key works, but this account has no model called "{self.model}". '
            'Set AI_MODEL to one of the available IDs.'
        )
        return status

    def stream_chat(self, messages, **kwargs):
        """Stream a chat completion as plain text chunks.

        gpt-5.6-luna documents both v1/chat/completions and v1/responses, so
        this uses the former: it is the simpler shape and the one that stays
        portable if the provider is ever swapped. Reasoning effort is only
        sent when configured, so a model that rejects the parameter is a
        blank env var away from working rather than a code change.
        """
        if self.reasoning_effort:
            kwargs.setdefault('reasoning_effort', self.reasoning_effort)
        bare_model = self.model[len('openai/'):] if self.model.startswith('openai/') else self.model
        stream = self._client().chat.completions.create(
            model=bare_model, messages=messages, stream=True, **kwargs
        )
        for chunk in stream:
            for choice in getattr(chunk, 'choices', None) or []:
                delta = getattr(choice, 'delta', None)
                text = getattr(delta, 'content', None) if delta else None
                if text:
                    yield text


class OllamaProvider:
    """Provider backed by a local sovereign Ollama daemon (no cloud API key required)."""

    def __init__(self, model, base_url='http://localhost:11434', timeout=30.0):
        self.model = model or ''
        self.bare_model = self.model[len('ollama/'):] if self.model.startswith('ollama/') else self.model
        self.base_url = (base_url or 'http://localhost:11434').rstrip('/')
        self.timeout = timeout
        self.api_key = 'local-ollama'
        self.reasoning_effort = ''

    def check(self):
        import requests
        status = ProviderStatus(model=self.model, key_configured=True, key_valid=True)
        if not self.bare_model:
            status.message = 'No local Ollama model is configured.'
            return status
        for candidate_base in [self.base_url, 'http://localhost:11434', 'http://host.docker.internal:11434']:
            try:
                resp = requests.get(f'{candidate_base}/api/tags', timeout=4.0)
                if resp.status_code == 200:
                    models = [m.get('name', '') for m in resp.json().get('models', [])]
                    if self.bare_model in models:
                        status.model_available = True
                        status.message = f'Local Ollama daemon online at {candidate_base}; "{self.bare_model}" is loaded and ready.'
                        return status
                    status.suggestions = models[:_MAX_SUGGESTIONS]
                    status.message = (
                        f'Local Ollama is reachable at {candidate_base}, but "{self.bare_model}" is not pulled yet.'
                    )
                    return status
            except Exception:
                continue
        status.key_valid = False
        status.message = 'Could not reach local Ollama daemon on port 11434.'
        return status

    def stream_chat(self, messages, **kwargs):
        import requests
        prompt_parts = []
        for m in messages:
            role = m.get('role', 'user').upper()
            prompt_parts.append(f'[{role}]\n{m.get("content", "")}')
        full_prompt = '\n\n'.join(prompt_parts)
        for candidate_base in [self.base_url, 'http://localhost:11434', 'http://host.docker.internal:11434']:
            try:
                resp = requests.post(
                    f'{candidate_base}/api/generate',
                    json={'model': self.bare_model, 'prompt': full_prompt, 'stream': False},
                    timeout=self.timeout,
                )
                if resp.status_code == 200:
                    text = resp.json().get('response', '')
                    if text:
                        yield text
                        return
            except Exception:
                continue


def from_config(config, model_override=None):
    """Build the provider described by a Flask config mapping."""
    model = (model_override or config.get('AI_MODEL') or '').strip()
    if model.startswith('ollama/'):
        import os
        ollama_base = config.get('OLLAMA_API_BASE') or os.environ.get('OLLAMA_API_BASE', 'http://localhost:11434')
        return OllamaProvider(
            model=model,
            base_url=ollama_base,
            timeout=config.get('AI_REQUEST_TIMEOUT', 60.0),
        )
    effort = (config.get('AI_REASONING_EFFORT') or '').strip().lower()
    if effort and effort not in AI_REASONING_LEVELS:
        logger.warning(
            'Ignoring AI_REASONING_EFFORT=%r: expected one of %s.',
            effort, ', '.join(AI_REASONING_LEVELS),
        )
        effort = ''
    return OpenAIProvider(
        api_key=config.get('OPENAI_API_KEY', ''),
        model=model,
        timeout=config.get('AI_REQUEST_TIMEOUT', 60.0),
        reasoning_effort=effort,
    )
