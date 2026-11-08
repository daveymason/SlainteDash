// Shared HTMX wiring, responsive tablet/mobile clinical drawer & global display preferences.

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

    function setMobileDrawerOpen(isOpen) {
        var sidebar = document.querySelector('nav.sidebar');
        var backdrop = document.getElementById('sidebarBackdrop');
        var mainContent = document.querySelector('.main-content');
        var menuBtn = document.getElementById('mobileMenuBtn');
        var dockBtn = document.getElementById('mobileDockMoreBtn');
        if (!sidebar) {
            return;
        }
        sidebar.classList.toggle('drawer-open', Boolean(isOpen));
        if (backdrop) {
            backdrop.classList.toggle('active', Boolean(isOpen));
        }
        if (menuBtn) {
            menuBtn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        }
        if (dockBtn) {
            dockBtn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        }
        if (mainContent && window.innerWidth < 992) {
            mainContent.inert = Boolean(isOpen);
        } else if (mainContent) {
            mainContent.inert = false;
        }
    }
    window.setMobileDrawerOpen = setMobileDrawerOpen;

    function wireMobileDrawer() {
        var menuBtn = document.getElementById('mobileMenuBtn');
        var dockBtn = document.getElementById('mobileDockMoreBtn');
        var closeBtn = document.getElementById('mobileDrawerCloseBtn');
        var backdrop = document.getElementById('sidebarBackdrop');
        var sidebar = document.querySelector('nav.sidebar');

        if (menuBtn && !menuBtn.dataset.wired) {
            menuBtn.dataset.wired = '1';
            menuBtn.addEventListener('click', function () {
                var openNow = sidebar && sidebar.classList.contains('drawer-open');
                setMobileDrawerOpen(!openNow);
            });
        }
        if (dockBtn && !dockBtn.dataset.wired) {
            dockBtn.dataset.wired = '1';
            dockBtn.addEventListener('click', function () {
                var openNow = sidebar && sidebar.classList.contains('drawer-open');
                setMobileDrawerOpen(!openNow);
            });
        }
        if (closeBtn && !closeBtn.dataset.wired) {
            closeBtn.dataset.wired = '1';
            closeBtn.addEventListener('click', function () {
                setMobileDrawerOpen(false);
            });
        }
        if (backdrop && !backdrop.dataset.wired) {
            backdrop.dataset.wired = '1';
            backdrop.addEventListener('click', function () {
                setMobileDrawerOpen(false);
            });
        }
        if (sidebar && !sidebar.dataset.wired) {
            sidebar.dataset.wired = '1';
            sidebar.addEventListener('click', function (ev) {
                var link = ev.target && ev.target.closest ? ev.target.closest('.nav-link') : null;
                if (link && window.innerWidth < 992) {
                    setMobileDrawerOpen(false);
                }
            });
        }
    }

    document.addEventListener('keydown', function (ev) {
        if (ev.key === 'Escape') {
            setMobileDrawerOpen(false);
        }
    });

    window.addEventListener('resize', function () {
        if (window.innerWidth >= 992) {
            setMobileDrawerOpen(false);
        }
    });

    function syncActiveNav() {
        var params = new URLSearchParams(window.location.search);
        var currentView = params.get('view') || (window.location.pathname.indexOf('/agents') === 0 ? 'agents' : 'patients');
        if (currentView.indexOf('agent_') === 0) {
            currentView = 'agents';
        }
        document.querySelectorAll('.sidebar .nav-link, .mobile-bottom-dock a.dock-link').forEach(function (link) {
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
        wireMobileDrawer();
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
        wireMobileDrawer();
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

    // Microfeedback & Loading Spinners: replace button icons with spinners during actions
    document.body.addEventListener('htmx:beforeRequest', function (event) {
        var elt = event.detail.elt;
        if (!elt) return;

        var btns = [];
        if (elt.tagName === 'BUTTON' || (elt.classList && elt.classList.contains('btn'))) {
            btns.push(elt);
        } else if (elt.tagName === 'FORM') {
            elt.querySelectorAll('button[type="submit"], .btn[type="submit"], button:not([type="button"]), .btn-primary, .btn-danger').forEach(function (b) {
                btns.push(b);
            });
        } else if (elt.closest) {
            var b = elt.closest('button, .btn');
            if (b) btns.push(b);
        }

        btns.forEach(function (btn) {
            btn.classList.add('is-loading');
            btn.setAttribute('aria-busy', 'true');

            // If button does not already have an indicator spinner in markup, inject one dynamically in place of the icon
            var existingSpinner = btn.querySelector('.spinner-border');
            if (!existingSpinner) {
                var icon = btn.querySelector('i, svg.svg-inline--fa');
                var sp = document.createElement('span');
                sp.className = 'spinner-border spinner-border-sm me-1 dynamic-htmx-spinner';
                sp.setAttribute('role', 'status');
                sp.setAttribute('aria-hidden', 'true');

                if (icon && icon.parentNode) {
                    icon.style.setProperty('display', 'none', 'important');
                    icon.parentNode.insertBefore(sp, icon);
                } else {
                    btn.insertBefore(sp, btn.firstChild);
                }
            }
        });
    });

    function restoreButtonStates(elt) {
        if (!elt) return;
        var btns = [];
        if (elt.tagName === 'BUTTON' || (elt.classList && elt.classList.contains('btn'))) {
            btns.push(elt);
        } else if (elt.tagName === 'FORM') {
            elt.querySelectorAll('button, .btn').forEach(function (b) { btns.push(b); });
        } else if (elt.closest) {
            var b = elt.closest('button, .btn');
            if (b) btns.push(b);
        }

        btns.forEach(function (btn) {
            btn.classList.remove('is-loading');
            btn.removeAttribute('aria-busy');
            btn.querySelectorAll('.dynamic-htmx-spinner').forEach(function (sp) {
                sp.remove();
            });
            btn.querySelectorAll('i, svg.svg-inline--fa').forEach(function (ic) {
                ic.style.removeProperty('display');
            });
        });
    }

    document.body.addEventListener('htmx:afterRequest', function (event) {
        restoreButtonStates(event.detail.elt);
    });
    document.body.addEventListener('htmx:responseError', function (event) {
        restoreButtonStates(event.detail.elt);
    });
    document.body.addEventListener('htmx:sendError', function (event) {
        restoreButtonStates(event.detail.elt);
    });
    document.body.addEventListener('htmx:abort', function (event) {
        restoreButtonStates(event.detail.elt);
    });
    document.body.addEventListener('htmx:timeout', function (event) {
        restoreButtonStates(event.detail.elt);
    });
})();
