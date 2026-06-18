// Service Worker de SIMON (#11): recibe Web Push y muestra la notificación.
self.addEventListener('install', (e) => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));

self.addEventListener('push', (event) => {
  let data = { title: 'SIMON', body: 'Notificación', severidad: 'info' };
  try { if (event.data) data = { ...data, ...event.data.json() }; } catch (_) {}
  const opts = {
    body: data.body,
    icon: '/favicon-64.png',
    badge: '/favicon-64.png',
    tag: 'simon',
    data: { url: '/incidencias' },
  };
  event.waitUntil(self.registration.showNotification(data.title, opts));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((cl) => {
      for (const c of cl) { if ('focus' in c) return c.focus(); }
      return self.clients.openWindow(url);
    })
  );
});
