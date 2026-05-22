/* Muninn PWA — caches static assets only; HTML/API always use network. */
var CACHE = 'muninn-static-v2';

self.addEventListener('install', function (event) {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE).then(function (cache) {
            return cache.addAll([
                '/static/style.css',
                '/static/pwa-icon-192.png',
                '/static/pwa-icon-512.png',
            ]);
        })
    );
});

self.addEventListener('activate', function (event) {
    event.waitUntil(
        caches.keys().then(function (keys) {
            return Promise.all(
                keys.filter(function (k) { return k !== CACHE; }).map(function (k) {
                    return caches.delete(k);
                })
            );
        }).then(function () { return self.clients.claim(); })
    );
});

self.addEventListener('fetch', function (event) {
    if (event.request.method !== 'GET') { return; }
    var url = new URL(event.request.url);
    if (url.origin !== self.location.origin) { return; }
    if (!url.pathname.startsWith('/static/')) { return; }

    event.respondWith(
        caches.match(event.request).then(function (cached) {
            var network = fetch(event.request).then(function (response) {
                if (response && response.status === 200) {
                    var copy = response.clone();
                    caches.open(CACHE).then(function (cache) {
                        cache.put(event.request, copy);
                    });
                }
                return response;
            });
            return cached || network;
        })
    );
});
