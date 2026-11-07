// Shared HTMX wiring & global clinical display preferences.

(function () {
    'use strict';

    // Attach the CSRF token to every mutating HTMX request.
    document.body.addEventListener('htmx:configRequest', function (event) {
        var method = (event.detail.verb || 'get').toLowerCase();
        if (method === 'get' || method === 'head') {
            return;
        }
        var meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) {
            event.detail.headers['X-CSRFToken'] = meta.getAttribute('content');
        }
    });

    function syncActiveNav() {
        var params = new URLSearchParams(window.location.search);
        var currentView = params.get('view') || (window.location.pathname.indexOf('/agents') === 0 ? 'agents' : 'patients');
        if (currentView.indexOf('agent_') === 0) {
            currentView = 'agents';
        }
        document.querySelectorAll('.sidebar .nav-link').forEach(function (link) {
            var href = link.getAttribute('href') || '';
            var view = link.getAttribute('data-view') || '';
            var isMatch = (href.indexOf('view=' + currentView) !== -1) || (view === currentView);
            link.classList.toggle('active', isMatch);
        });
    }

    // Apply persisted bedside readability, high-contrast priority mode, and triage polling interval
    function applyDisplayPreferences() {
        try {
            var savedSize = localStorage.getItem('slainte_font_size');
            if (savedSize && ['100%', '115%', '130%'].indexOf(savedSize) !== -1) {
                document.documentElement.style.fontSize = savedSize;
            }
            var savedContrast = localStorage.getItem('slainte_high_contrast') === 'true';
            document.body.classList.toggle('high-contrast-mode', savedContrast);

            var savedRate = localStorage.getItem('slainte_refresh_rate') || '15s';
            var triageEl = document.getElementById('triage-queue-content');
            if (triageEl && window.htmx) {
                var desiredTrigger = (savedRate === 'manual') ? 'refreshQueue' : ('every ' + savedRate);
                if (triageEl.getAttribute('data-applied-rate') !== desiredTrigger) {
                    triageEl.setAttribute('hx-trigger', desiredTrigger);
                    triageEl.setAttribute('data-applied-rate', desiredTrigger);
                    window.htmx.process(triageEl);
                }
            }
        } catch (e) {
            // Ignore storage errors in restricted browsing contexts
        }
    }
    window.applyDisplayPreferences = applyDisplayPreferences;

    // Restore collapsible MTS categories state across live polling swaps
    function restoreMtsCollapsibleState() {
        document.querySelectorAll('.mts-category-card').forEach(function (el) {
            var cat = el.getAttribute('data-cat');
            if (cat) {
                var saved = sessionStorage.getItem('mts_cat_' + cat + '_open');
                if (saved !== null) {
                    el.open = (saved === '1');
                }
            }
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        applyDisplayPreferences();
        syncActiveNav();
        restoreMtsCollapsibleState();
    });

    window.addEventListener('popstate', function () {
        syncActiveNav();
        var params = new URLSearchParams(window.location.search);
        var currentView = params.get('view') || (window.location.pathname === '/agents' ? 'agents' : 'patients');
        var views = {
            'triage': '/fhir/Triage',
            'agents': '/fhir/Auditor',
            'auditor': '/fhir/Auditor',
            'pipeline': '/fhir/Agent/multimodal_ingest',
            'patients': '/fhir/Patients',
            'stats': '/fhir/Demographics',
            'insights': '/fhir/Dashboard'
        };
        var targetUrl = views[currentView];
        if (!targetUrl && currentView.indexOf('agent_') === 0) {
            targetUrl = '/fhir/Agent/' + currentView.substring(6);
        }
        var content = document.getElementById('content');
        if (content && targetUrl && window.htmx) {
            window.htmx.ajax('GET', targetUrl, { target: '#content', swap: 'innerHTML' });
        }
    });

    // Save toggle changes on MTS categories
    document.addEventListener('toggle', function (e) {
        if (e.target && e.target.classList && e.target.classList.contains('mts-category-card')) {
            var cat = e.target.getAttribute('data-cat');
            if (cat) {
                sessionStorage.setItem('mts_cat_' + cat + '_open', e.target.open ? '1' : '0');
            }
        }
    }, true);

    window.expandAllCategories = function (openState) {
        document.querySelectorAll('.mts-category-card').forEach(function (el) {
            el.open = Boolean(openState);
            var cat = el.getAttribute('data-cat');
            if (cat) {
                sessionStorage.setItem('mts_cat_' + cat + '_open', openState ? '1' : '0');
            }
        });
    };

    window.collapseNonUrgent = function () {
        document.querySelectorAll('.mts-category-card').forEach(function (el) {
            var cat = parseInt(el.getAttribute('data-cat') || '0', 10);
            var shouldOpen = (cat <= 3);
            el.open = shouldOpen;
            sessionStorage.setItem('mts_cat_' + cat + '_open', shouldOpen ? '1' : '0');
        });
    };

    document.body.addEventListener('htmx:afterSwap', function () {
        applyDisplayPreferences();
        syncActiveNav();
        restoreMtsCollapsibleState();
    });

    document.body.addEventListener('htmx:responseError', function (event) {
        var target = event.detail.target;
        if (target) {
            target.innerHTML =
                '<div class="alert alert-danger mb-0">' +
                '<i class="fas fa-exclamation-triangle me-2"></i>' +
                'This section could not be loaded. Please try again.</div>';
        }
    });

    document.body.addEventListener('htmx:sendError', function (event) {
        var target = event.detail.target;
        if (target) {
            target.innerHTML =
                '<div class="alert alert-danger mb-0">' +
                '<i class="fas fa-plug me-2"></i>' +
                'Lost connection to the server. Check your network and try again.</div>';
        }
    });
})();
