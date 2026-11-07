/* StudySync service worker: caches static files, shows an offline page. Never caches logged-in pages or API calls. */
const VERSION = "studysync-{{ version }}";
const PRECACHE = {{ urls_json|safe }};
const OFFLINE = "{{ offline_url }}";

self.addEventListener("install", event => {
  event.waitUntil(caches.open(VERSION).then(cache => cache.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith("studysync-") && k !== VERSION).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith("/static/")) {            // static files: serve cache, refresh in the background
    event.respondWith(caches.open(VERSION).then(async cache => {
      const hit = await cache.match(req);
      const fresh = fetch(req).then(res => { if (res.ok) cache.put(req, res.clone()); return res; }).catch(() => hit);
      return hit || fresh;
    }));
    return;
  }

  if (req.mode === "navigate") {                         // pages: always network; offline page only when the network fails
    event.respondWith(fetch(req).catch(() => caches.match(OFFLINE)));
  }
});
