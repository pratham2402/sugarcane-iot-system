// Service Worker — Farmer App Day 11
// Caches a minimal app shell. JS/CSS bundles are cached by browser HTTP cache.

const CACHE_VERSION = "farmer-app-v3";
const APP_SHELL = [
  "/",
  "/index.html",
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/icon-maskable-512.png",
];

// Install — pre-cache safe shell files
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then(async (cache) => {
      // Try to cache each file individually so one failure doesn't break all
      await Promise.all(
        APP_SHELL.map((url) =>
          cache.add(url).catch((err) => {
            console.warn(`[SW] Could not cache ${url}:`, err.message);
          })
        )
      );
    })
  );
  self.skipWaiting();
});

// Activate — clean up old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys
          .filter((key) => key !== CACHE_VERSION)
          .map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// Fetch strategy:
// - API and cross-origin requests: never intercept
// - Same-origin GETs: network-first with cache fallback
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  if (event.request.method !== "GET") return;

  // Skip API calls and external (Pi tunnel, Cloudflare, Google) calls
  if (
    url.pathname.startsWith("/api/") ||
    url.origin !== self.location.origin
  ) {
    return;
  }

  // Network-first for same-origin static files
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Only cache successful responses
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE_VERSION).then((cache) => {
            cache.put(event.request, copy).catch(() => {});
          });
        }
        return response;
      })
      .catch(() =>
        caches.match(event.request).then((cached) => cached || caches.match("/index.html"))
      )
  );
});