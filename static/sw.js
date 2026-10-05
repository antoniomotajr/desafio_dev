const CACHE='mota-suite-secure-v1';
const STATIC_ASSETS=[
  '/static/app.css',
  '/static/app.js',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png'
];

self.addEventListener('install',event=>{
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE).then(cache=>cache.addAll(STATIC_ASSETS))
  );
});

self.addEventListener('activate',event=>{
  event.waitUntil(
    caches.keys()
      .then(keys=>Promise.all(
        keys
          .filter(key=>key!==CACHE)
          .map(key=>caches.delete(key))
      ))
      .then(()=>self.clients.claim())
  );
});

self.addEventListener('fetch',event=>{
  const request=event.request;
  const url=new URL(request.url);

  if(request.method!=='GET')return;

  // Nunca cacheia APIs, backups, exports ou páginas com token.
  if(
    url.pathname.startsWith('/api/')
    ||url.pathname.startsWith('/export/')
    ||url.pathname==='/backup'
    ||url.searchParams.has('token')
  ){
    event.respondWith(fetch(request));
    return;
  }

  // Assets estáticos: cache-first.
  if(url.pathname.startsWith('/static/')){
    event.respondWith(
      caches.match(request)
        .then(hit=>hit||fetch(request))
    );
    return;
  }

  // HTML: sempre rede. Evita exibir dashboard antigo/sensível do cache.
  event.respondWith(fetch(request));
});
