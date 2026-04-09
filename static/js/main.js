(function () {
    'use strict';

    // =========================================================================
    // CSRF Token Handling for AJAX Requests
    // =========================================================================

    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    function getCSRFToken() {
        var token = getCookie('csrftoken');
        if (!token) {
            var metaTag = document.querySelector('meta[name="csrf-token"]');
            if (metaTag) {
                token = metaTag.getAttribute('content');
            }
        }
        if (!token) {
            var hiddenInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
            if (hiddenInput) {
                token = hiddenInput.value;
            }
        }
        return token;
    }

    function csrfSafeMethod(method) {
        return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
    }

    function setupAjaxCSRF() {
        var originalFetch = window.fetch;
        window.fetch = function (url, options) {
            options = options || {};
            var method = (options.method || 'GET').toUpperCase();
            if (!csrfSafeMethod(method)) {
                options.headers = options.headers || {};
                if (options.headers instanceof Headers) {
                    if (!options.headers.has('X-CSRFToken')) {
                        var token = getCSRFToken();
                        if (token) {
                            options.headers.set('X-CSRFToken', token);
                        }
                    }
                } else {
                    if (!options.headers['X-CSRFToken']) {
                        var csrfToken = getCSRFToken();
                        if (csrfToken) {
                            options.headers['X-CSRFToken'] = csrfToken;
                        }
                    }
                }
            }
            return originalFetch.call(this, url, options);
        };

        if (typeof XMLHttpRequest !== 'undefined') {
            var originalOpen = XMLHttpRequest.prototype.open;
            var originalSend = XMLHttpRequest.prototype.send;

            XMLHttpRequest.prototype.open = function (method, url) {
                this._method = method;
                return originalOpen.apply(this, arguments);
            };

            XMLHttpRequest.prototype.send = function () {
                if (this._method && !csrfSafeMethod(this._method.toUpperCase())) {
                    var token = getCSRFToken();
                    if (token) {
                        this.setRequestHeader('X-CSRFToken', token);
                    }
                }
                return originalSend.apply(this, arguments);
            };
        }
    }

    // =========================================================================
    // Form Validation Helpers
    // =========================================================================

    function validateRequired(field) {
        var value = field.value.trim();
        if (value === '') {
            showFieldError(field, 'This field is required.');
            return false;
        }
        clearFieldError(field);
        return true;
    }

    function validateEmail(field) {
        var value = field.value.trim();
        if (value === '') {
            return true;
        }
        var emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailPattern.test(value)) {
            showFieldError(field, 'Please enter a valid email address.');
            return false;
        }
        clearFieldError(field);
        return true;
    }

    function validatePhone(field) {
        var value = field.value.trim();
        if (value === '') {
            return true;
        }
        var phonePattern = /^[+]?[\d\s\-().]{7,20}$/;
        if (!phonePattern.test(value)) {
            showFieldError(field, 'Please enter a valid phone number.');
            return false;
        }
        clearFieldError(field);
        return true;
    }

    function validateMinLength(field, minLength) {
        var value = field.value.trim();
        if (value !== '' && value.length < minLength) {
            showFieldError(field, 'Must be at least ' + minLength + ' characters.');
            return false;
        }
        clearFieldError(field);
        return true;
    }

    function showFieldError(field, message) {
        clearFieldError(field);
        field.classList.add('is-invalid');
        var errorDiv = document.createElement('div');
        errorDiv.className = 'invalid-feedback';
        errorDiv.textContent = message;
        field.parentNode.appendChild(errorDiv);
    }

    function clearFieldError(field) {
        field.classList.remove('is-invalid');
        var existingError = field.parentNode.querySelector('.invalid-feedback');
        if (existingError) {
            existingError.remove();
        }
    }

    function setupFormValidation() {
        var forms = document.querySelectorAll('form[data-validate]');
        forms.forEach(function (form) {
            form.addEventListener('submit', function (event) {
                var isValid = true;
                var requiredFields = form.querySelectorAll('[required]');
                requiredFields.forEach(function (field) {
                    if (!validateRequired(field)) {
                        isValid = false;
                    }
                });

                var emailFields = form.querySelectorAll('input[type="email"]');
                emailFields.forEach(function (field) {
                    if (!validateEmail(field)) {
                        isValid = false;
                    }
                });

                var phoneFields = form.querySelectorAll('input[type="tel"], input[data-validate-phone]');
                phoneFields.forEach(function (field) {
                    if (!validatePhone(field)) {
                        isValid = false;
                    }
                });

                var minLengthFields = form.querySelectorAll('[data-min-length]');
                minLengthFields.forEach(function (field) {
                    var minLen = parseInt(field.getAttribute('data-min-length'), 10);
                    if (!validateMinLength(field, minLen)) {
                        isValid = false;
                    }
                });

                if (!isValid) {
                    event.preventDefault();
                    event.stopPropagation();
                    var firstInvalid = form.querySelector('.is-invalid');
                    if (firstInvalid) {
                        firstInvalid.focus();
                    }
                }
            });

            var inputs = form.querySelectorAll('input, select, textarea');
            inputs.forEach(function (input) {
                input.addEventListener('input', function () {
                    clearFieldError(input);
                });
            });
        });
    }

    // =========================================================================
    // Confirmation Dialogs for Delete Actions
    // =========================================================================

    function setupDeleteConfirmations() {
        document.addEventListener('click', function (event) {
            var target = event.target.closest('[data-confirm-delete]');
            if (!target) {
                return;
            }

            var message = target.getAttribute('data-confirm-delete') || 'Are you sure you want to delete this item? This action cannot be undone.';
            if (!window.confirm(message)) {
                event.preventDefault();
                event.stopPropagation();
                return false;
            }
        });

        document.addEventListener('submit', function (event) {
            var form = event.target;
            if (!form.hasAttribute('data-confirm-delete-form')) {
                return;
            }

            var message = form.getAttribute('data-confirm-delete-form') || 'Are you sure you want to delete this item? This action cannot be undone.';
            if (!window.confirm(message)) {
                event.preventDefault();
                event.stopPropagation();
            }
        });
    }

    // =========================================================================
    // Sidebar Toggle for Mobile
    // =========================================================================

    function setupSidebarToggle() {
        var sidebarToggleBtn = document.getElementById('sidebar-toggle');
        var sidebar = document.getElementById('sidebar');
        var sidebarOverlay = document.getElementById('sidebar-overlay');

        if (!sidebarToggleBtn || !sidebar) {
            return;
        }

        function openSidebar() {
            sidebar.classList.add('sidebar-open');
            if (sidebarOverlay) {
                sidebarOverlay.classList.add('active');
            }
            document.body.classList.add('sidebar-active');
            sidebarToggleBtn.setAttribute('aria-expanded', 'true');
        }

        function closeSidebar() {
            sidebar.classList.remove('sidebar-open');
            if (sidebarOverlay) {
                sidebarOverlay.classList.remove('active');
            }
            document.body.classList.remove('sidebar-active');
            sidebarToggleBtn.setAttribute('aria-expanded', 'false');
        }

        function toggleSidebar() {
            if (sidebar.classList.contains('sidebar-open')) {
                closeSidebar();
            } else {
                openSidebar();
            }
        }

        sidebarToggleBtn.addEventListener('click', function (event) {
            event.preventDefault();
            toggleSidebar();
        });

        if (sidebarOverlay) {
            sidebarOverlay.addEventListener('click', function () {
                closeSidebar();
            });
        }

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && sidebar.classList.contains('sidebar-open')) {
                closeSidebar();
            }
        });

        window.addEventListener('resize', function () {
            if (window.innerWidth >= 992 && sidebar.classList.contains('sidebar-open')) {
                closeSidebar();
            }
        });
    }

    // =========================================================================
    // Auto-Dismiss Flash Messages
    // =========================================================================

    function setupFlashMessages() {
        var alerts = document.querySelectorAll('.alert[data-auto-dismiss]');
        alerts.forEach(function (alert) {
            var delay = parseInt(alert.getAttribute('data-auto-dismiss'), 10);
            if (isNaN(delay) || delay <= 0) {
                delay = 5000;
            }

            setTimeout(function () {
                dismissAlert(alert);
            }, delay);
        });

        var defaultAlerts = document.querySelectorAll('.alert.alert-dismissible:not([data-no-auto-dismiss])');
        defaultAlerts.forEach(function (alert) {
            if (alert.hasAttribute('data-auto-dismiss')) {
                return;
            }
            setTimeout(function () {
                dismissAlert(alert);
            }, 5000);
        });
    }

    function dismissAlert(alert) {
        if (!alert || !alert.parentNode) {
            return;
        }

        alert.style.transition = 'opacity 0.3s ease-out';
        alert.style.opacity = '0';

        setTimeout(function () {
            if (alert.parentNode) {
                alert.parentNode.removeChild(alert);
            }
        }, 300);
    }

    // =========================================================================
    // Dynamic Filter Form Submission
    // =========================================================================

    function setupFilterForms() {
        var filterForms = document.querySelectorAll('form[data-filter-form]');
        filterForms.forEach(function (form) {
            var selects = form.querySelectorAll('select[data-auto-submit]');
            selects.forEach(function (select) {
                select.addEventListener('change', function () {
                    cleanAndSubmitFilterForm(form);
                });
            });

            var searchInputs = form.querySelectorAll('input[data-auto-submit]');
            var debounceTimers = {};
            searchInputs.forEach(function (input) {
                var inputId = input.id || input.name || Math.random().toString(36);
                input.addEventListener('input', function () {
                    if (debounceTimers[inputId]) {
                        clearTimeout(debounceTimers[inputId]);
                    }
                    debounceTimers[inputId] = setTimeout(function () {
                        cleanAndSubmitFilterForm(form);
                    }, 500);
                });
            });

            form.addEventListener('submit', function (event) {
                event.preventDefault();
                cleanAndSubmitFilterForm(form);
            });

            var resetBtn = form.querySelector('[data-filter-reset]');
            if (resetBtn) {
                resetBtn.addEventListener('click', function (event) {
                    event.preventDefault();
                    var inputs = form.querySelectorAll('input, select');
                    inputs.forEach(function (input) {
                        if (input.type === 'hidden' && input.name === 'csrfmiddlewaretoken') {
                            return;
                        }
                        if (input.tagName === 'SELECT') {
                            input.selectedIndex = 0;
                        } else {
                            input.value = '';
                        }
                    });
                    cleanAndSubmitFilterForm(form);
                });
            }
        });
    }

    function cleanAndSubmitFilterForm(form) {
        var formData = new FormData(form);
        var params = new URLSearchParams();

        for (var pair of formData.entries()) {
            var key = pair[0];
            var value = pair[1];
            if (key === 'csrfmiddlewaretoken') {
                continue;
            }
            if (value !== '' && value !== null && value !== undefined) {
                params.append(key, value);
            }
        }

        var action = form.getAttribute('action') || window.location.pathname;
        var queryString = params.toString();
        var url = queryString ? action + '?' + queryString : action;

        window.location.href = url;
    }

    // =========================================================================
    // Utility: Tooltip Initialization (if Bootstrap is available)
    // =========================================================================

    function setupTooltips() {
        if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
            var tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
            tooltipTriggerList.forEach(function (tooltipTriggerEl) {
                new bootstrap.Tooltip(tooltipTriggerEl);
            });
        }
    }

    // =========================================================================
    // Utility: Popover Initialization (if Bootstrap is available)
    // =========================================================================

    function setupPopovers() {
        if (typeof bootstrap !== 'undefined' && bootstrap.Popover) {
            var popoverTriggerList = document.querySelectorAll('[data-bs-toggle="popover"]');
            popoverTriggerList.forEach(function (popoverTriggerEl) {
                new bootstrap.Popover(popoverTriggerEl);
            });
        }
    }

    // =========================================================================
    // Initialize Everything on DOMContentLoaded
    // =========================================================================

    function init() {
        setupAjaxCSRF();
        setupFormValidation();
        setupDeleteConfirmations();
        setupSidebarToggle();
        setupFlashMessages();
        setupFilterForms();
        setupTooltips();
        setupPopovers();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();