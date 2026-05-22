(function () {
    if (!document.documentElement.dataset.pwaEnabled) { return; }

    var banner = document.getElementById('pwa-install-banner');
    var installBtn = document.getElementById('pwa-install-btn');
    var deferredPrompt = null;
    var DISMISS_KEY = 'muninn-pwa-install-dismissed';

    function isStandalone() {
        return window.matchMedia('(display-mode: standalone)').matches
            || window.navigator.standalone === true;
    }

    function showBanner() {
        if (!banner || isStandalone()) { return; }
        if (localStorage.getItem(DISMISS_KEY) === '1') { return; }
        banner.hidden = false;
        banner.setAttribute('aria-hidden', 'false');
    }

    function hideBanner() {
        if (!banner) { return; }
        banner.hidden = true;
        banner.setAttribute('aria-hidden', 'true');
    }

    if ('serviceWorker' in navigator) {
        window.addEventListener('load', function () {
            navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function (err) {
                console.warn('Muninn PWA: service worker registration failed', err);
            });
        });
    }

    window.addEventListener('beforeinstallprompt', function (e) {
        e.preventDefault();
        deferredPrompt = e;
        showBanner();
    });

    if (installBtn) {
        installBtn.addEventListener('click', function () {
            if (!deferredPrompt) {
                hideBanner();
                return;
            }
            deferredPrompt.prompt();
            deferredPrompt.userChoice.finally(function () {
                deferredPrompt = null;
                hideBanner();
            });
        });
    }

    banner && banner.querySelectorAll('[data-pwa-dismiss]').forEach(function (el) {
        el.addEventListener('click', function () {
            localStorage.setItem(DISMISS_KEY, '1');
            hideBanner();
        });
    });

    window.addEventListener('appinstalled', function () {
        hideBanner();
        localStorage.setItem(DISMISS_KEY, '1');
    });
})();
