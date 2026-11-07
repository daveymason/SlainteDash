# 🏥 SlainteDash — Multi-Vertical Clinical Cockpit & 11-Agent Enterprise Hub

A Flask + [HTMX](https://htmx.org/) clinical workstation and **Autonomous 11-Agent Command Center (`/agents`)** built by **SlainteTech AI Security Labs** for exploring, authoring, and governing HL7 FHIR R4 clinical data across **7 specialized verticals** (`Emergency Department`, `GP`, `Dentist`, `Pharmacy`, `Ambulance EMS`, `Elite Sports Club`, and `Astronaut Health Monitoring`). Routes return HTML fragments with zero client-side framework overhead.

---

## ⚠️ Before you point this at real patient data

This is a demonstration app. It defaults to `hapi.fhir.org` (or local `SlainteFHIR :8082` in appliance mode), holding **synthetic data**. Read [SECURITY.md](SECURITY.md) before
connecting it to anything real — it lists what is in place and what is still
missing.

---

## 🚀 Features

- **11 Dedicated Autonomous Agent Dashboards (`/agents` & `/agents/<agent_id>`)** — Every agent in the 11-agent enterprise fleet has its own interactive operational page (`01 BOLA Red-Team`, `02 FHIR R4 Integrity`, `03 CVE & Supply-Chain`, `04 GDPR Art. 9 Privacy`, `05 GovAudit & Provenance`, `06 Clinical & HL7v2 Ingestion Pipeline`, `07 Cited Patient Summariser`, `08 3-Tier Rx-Guard Pharmacology`, `09 Dx-Triage & NEWS2 Acuity`, `10 SlainteScribe-Voice Ambient Voice Scribe`, and `11 SlainteRev-Coding HIPE / ICD-10-AM Revenue Auditor`).
- **7 Enterprise Hospital Integrations (Phase 11.5)** — **HL7 SMART-on-FHIR v2 App Launch** (`/.well-known/smart-configuration` + Epic/Cerner launch simulator at `/settings/smart`), **Enterprise OIDC PKCE SSO** (`Entra ID / Okta / Keycloak`), **Native HL7v2 (`ADT^A01` / `ORU^R01` / `RDE^O11`) Pipe-Hat Translator**, **Irish HSE PCRS GMS Claim CSV Export**, **Granular Clinical RBAC** (`prescriber`, `pharmacist`, `triage_nurse`, `auditor`, `admin`) + **60-Minute Break-the-Glass Emergency Grants**, **HMAC-SHA256 SIEM Webhooks**, and a **Printable `NIS2 / EU AI Act / GDPR Art. 9 / HIQA` Compliance Attestation Certificate** (`/agents/compliance-certificate`).
- **7 Role-Adaptive Clinical Cockpits (`"Sign in as..."`)** — Switch between `SlainteED` (Emergency Dept), `SlainteGP` (General Practice), `SlainteDent` (Dental Surgery + 32-Tooth FDI Odontogram), `SlaintePharm` (Clinical Pharmacy + Dispensing Queue), `SlainteEMS` (Ambulance/ePCR), `SlainteSport` (Elite Sports Medicine), and `SlainteAstro` (Astronaut Bio-Telemetry). Switching cockpits dynamically adapts the **Sidebar** (`Live Triage` shown only for `SlainteED` and `SlainteEMS`), the **Specialty Workspace**, and the **Patients Roster**.
- **Patient details, Clinical Writes & 3-Tier `SlainteRx-Guard`** — Full FHIR R4 prescribing, vital signs + 24h NEWS2 sparklines, SNOMED/ICD-10 conditions, allergies, SOAP notes, Ambient Voice Scribe order drafting, HIPE comorbidity coding scanner, and 3-Tier `SlainteRx-Guard` screening (Tier 1 Allergy + Tier 2 ISMP High-Alert DDI + Tier 3 Lab `eGFR` Renal Dosing Gate).
- **Minimalist Clinical UI & Immutable Audit Ledger** — High-contrast, accessible medical interface (`static/styles.css`) with progressive login lockout, SQLite WAL rate limiting, and append-only SQLite `audit_log`, `ai_exchange`, & `break_glass_grants` tables protected by 6 kernel immutability triggers.

---

## 🛠️ Quickstart

```bash
git clone https://github.com/daveymason/Patient-Dashboard-htmx-python-fhir.git
cd Patient-Dashboard-htmx-python-fhir

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # paste into SECRET_KEY
# set INITIAL_ADMIN_USERNAME and INITIAL_ADMIN_PASSWORD to your own login

export $(grep -v '^#' .env | xargs)     # or use direnv / python-dotenv
FLASK_DEBUG=true python app.py
```

Visit <http://127.0.0.1:5000/>.

Sign in with the username and password you set as `INITIAL_ADMIN_USERNAME` /
`INITIAL_ADMIN_PASSWORD`. Anyone who registers an account is recorded as
**pending** and sees nothing until you approve them under **Users**.

### Fastest local check

To just click around locally without editing `.env` at all:

```bash
SECRET_KEY="dev-local-key-0123456789abcdef0123456789abcdef" \
INITIAL_ADMIN_USERNAME="admin" \
INITIAL_ADMIN_PASSWORD="dev-password-please-change" \
SESSION_COOKIE_SECURE=false \
FLASK_DEBUG=true \
python app.py
```

Then visit **<http://127.0.0.1:5000/>** and sign in with `admin` /
`dev-password-please-change`. This is a throwaway key and password for local
use only — never run a real deployment this way.

### Granting access from the command line

`INITIAL_ADMIN_USERNAME`/`INITIAL_ADMIN_PASSWORD` only apply on first boot. To
grant or recover administrator access at any time:

```bash
flask --app app grant-admin yourusername
flask --app app list-users
```

`grant-admin` creates the account if it does not exist and promotes it if it
does, prompting for a password either way — so a locked-out install never
needs the database edited by hand. The app warns at startup whenever no
active administrator exists.

### Docker

```bash
docker build -t patient-dashboard .
docker run -p 8000:8000 --env-file .env -v "$PWD/instance:/app/instance" patient-dashboard
```

### Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The suite runs offline — the FHIR backend is stubbed — and covers each defect
fixed in the hardening pass.

---

## ⚙️ Configuration

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `SECRET_KEY` | **Yes** (prod) | — | Session signing. The app refuses to start without it outside debug. |
| `INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD` | Recommended | — | Account granted admin on first boot. Must be set together; invalid or weak values are ignored, not seeded. |
| `FHIR_SERVER_URL` | No | `https://hapi.fhir.org/baseR4` | FHIR R4 base URL. |
| `FHIR_TIMEOUT` | No | `10` | Per-request timeout, seconds. |
| `FHIR_PAGE_SIZE` | No | `20` | Patients per page. |
| `DATABASE_PATH` | No | `./instance/dashboard.db` | User store and audit log. |
| `SESSION_COOKIE_SECURE` | No | `true` | Set `false` only for local HTTP. |
| `SESSION_LIFETIME_MINUTES` | No | `60` | Idle session lifetime. |
| `LOG_HASH_SALT` | Recommended | random | Salt for pseudonymised log identifiers. Keep stable and secret. |
| `LOG_JSON` | No | `true` | Structured JSON logs. |
| `HEALTH_SHOW_BACKEND` | No | `false` | Expose the FHIR URL on `/health`. |
| `RATELIMIT_AUTH` | No | `10 per minute` | Limit on auth endpoints. |
| `OPENAI_API_KEY` | No | — | AI provider key. Environment only — never stored in the database. |
| `AI_MODEL` | No | `gpt-5.6-luna` | Model ID. Verify it against your account on the AI Settings page. |
| `AI_REASONING_EFFORT` | No | `low` | `none`…`max`. Reasoning tokens bill at the output rate, so this is the cost lever. Blank omits the parameter. |
| `AI_ALLOW_REAL_PHI` | No | `false` | Permits AI against a non-demo FHIR server. Requires a BAA/DPIA. |
| `AI_DEIDENTIFY` | No | `auto` | Withholds name, address, contact and record numbers from model context. `auto` = on unless the FHIR server is a known synthetic one. |
| `AI_CONTEXT_TOKEN_CEILING` | No | `120000` | Above this, a record is curated rather than sent whole. Allergies are never dropped. |

Running multiple gunicorn workers **requires** a stable `SECRET_KEY` — otherwise
each worker signs cookies with a different key and sign-in fails intermittently.

---

## 🧱 Layout

| File | Role |
|---|---|
| `app.py` | Application factory and routes |
| `wsgi.py` | Production entry point (`gunicorn wsgi:app`) |
| `config.py` | Environment-driven configuration |
| `fhir_client.py` | HTTP client: timeouts, retries, concurrency, typed results |
| `fhir_utils.py` | Defensive parsing of FHIR resources |
| `auth.py` | Username/password sign-in and roles |
| `db.py` | SQLite user store and append-only audit log |
| `logging_setup.py` | JSON logging with identifiers pseudonymised |

---

## 🗺️ Roadmap

[docs/PROJECT-PLAN.md](docs/PROJECT-PLAN.md) is the single planning document —
phases in build order, with task checklists, technical detail, a risk register
and the verified FHIR and model facts behind the decisions.

---

## 🤝 Contributing

1. Fork & clone the repo
2. Create a feature branch
3. Run `pytest` before opening a pull request
4. Open a pull request

---

## 📄 License

MIT License. See [LICENSE](LICENSE).

---

## 🙏 Credits

- Logo by [Freepik](https://www.freepik.com/icon/computer_8811410) (Flaticon)
- Project by [daveymason.com](https://daveymason.com)

---

[Project Repository](https://github.com/daveymason/Patient-Dashboard-htmx-python-fhir)
