/* ReminderCal service worker: native Web Push banners. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));

self.addEventListener('push', event => {
  let data = { title: 'ReminderCal', body: 'You have a reminder', url: '/dashboard.html' };
  try { data = { ...data, ...event.data.json() }; } catch (_) { /* plain text payload */ }
  event.waitUntil(self.registration.showNotification(data.title, {
    body: data.body,
    icon: '/icon.svg',
    badge: '/icon.svg',
    data: { url: data.url },
    requireInteraction: false,
  }));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/dashboard.html';
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
    for (const c of list) { if ('focus' in c) { c.navigate(url); return c.focus(); } }
    return self.clients.openWindow(url);
  }));
});
