// Appli ÔGravel : fonctionne même avec un réseau faible.
// Pages et icônes en cache ; les données (sorties, parcours) toujours
// demandées en ligne d'abord, avec la dernière version connue en secours.
const CACHE = 'ogravel-v2';
const COQUILLE = ['./', './index.html', './manifest.webmanifest', './icon-192.png', './icon-512.png', './apple-touch-icon.png', './logo.jpg'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(COQUILLE)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(k => Promise.all(k.filter(n => n !== CACHE).map(n => caches.delete(n)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;
  if (url.pathname.endsWith('.mp4')) return;  // vidéos de fond : lues directement sur le site
  const donnees = url.pathname.endsWith('.json');
  if (donnees || e.request.mode === 'navigate') {
    // cache: 'no-cache' : toujours vérifier auprès du site, pour voir tout de suite les mises à jour.
    e.respondWith(fetch(e.request, {cache: 'no-cache'}).then(r => {
      const copie = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copie)); return r;
    }).catch(() => caches.match(e.request, {ignoreSearch: true}).then(r => r || caches.match('./index.html'))));
  } else {
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
  }
});
