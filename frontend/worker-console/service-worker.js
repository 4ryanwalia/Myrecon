const CACHE = "myrecon-worker-console-v2";
const SHELL = [
  "/worker-console/",
  "/worker-console/index.html",
  "/worker-console/app.js",
  "/worker-console/styles.css",
  "/worker-console/manifest.webmanifest",
  "/worker-console/icon-192.png",
  "/worker-console/icon-512.png",
  "/assets/js/env.js",
  "/assets/js/config.js",
  "/assets/js/account.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(
    keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)),
  )).then(() => self.clients.claim()));
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET" || new URL(event.request.url).origin !== self.location.origin) return;
  event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request)));
});
