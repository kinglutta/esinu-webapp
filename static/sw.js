const CACHE_NAME = "esinu-shell-v3";
const SHELL_URLS = [
    "/",
    "/static/style.css",
    "/static/favicon.svg",
    "/static/manifest.webmanifest",
    "/static/hls.min.js",
];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => Promise.allSettled(
                SHELL_URLS.map((url) => cache.add(url))
            ))
            .then((results) => {
                const failed = results.filter((result) => result.status === "rejected");
                if (failed.length) {
                    console.warn(`ESINU service worker skipped ${failed.length} shell asset(s)`);
                }
                return self.skipWaiting();
            })
    );
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys()
            .then((keys) => Promise.all(
                keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
            ))
            .then(() => self.clients.claim())
    );
});

async function networkFirst(request) {
    try {
        const response = await fetch(request);
        if (response.ok) {
            const copy = response.clone();
            const cache = await caches.open(CACHE_NAME);
            await cache.put(request, copy);
        }
        return response;
    } catch (error) {
        const cached = await caches.match(request);
        if (cached) return cached;
        throw error;
    }
}

self.addEventListener("fetch", (event) => {
    const request = event.request;
    if (request.method !== "GET") return;

    const url = new URL(request.url);
    if (url.origin !== self.location.origin) return;

    // Channel data and video segments must always be live.
    if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/stream/")) return;

    if (request.mode === "navigate") {
        event.respondWith(networkFirst(request).catch(() => caches.match("/")));
        return;
    }

    event.respondWith(networkFirst(request));
});
