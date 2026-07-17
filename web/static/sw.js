/* IUSENTRA service worker per PWA e notifiche dispositivo.
 *
 * Non memorizza dati operativi in cache e non contiene informazioni sensibili.
 */

const DEFAULT_HREF = '/app-v2';
const NOTIFICATION_ICON = '/static/icons/icon-192.png';
const NOTIFICATION_BADGE = '/static/icons/badge-96.png';
const SW_VERSION = '2026-07-17-remote-hearing-v6';
const REMOTE_HEARING_DOMAINS = [
  'teams.microsoft.com',
  'zoom.us',
  'webex.com',
  'meet.google.com',
  'meet.jit.si',
  'gotomeeting.com',
  'global.gotomeeting.com',
  'bluejeans.com',
  'whereby.com',
  'lifesizecloud.com',
];
function safeHref(value) {
  const href = typeof value === 'string' ? value.trim() : '';
  if (!href || !href.startsWith('/') || href.startsWith('//')) return DEFAULT_HREF;
  if (/javascript:|data:|\r|\n/i.test(href)) return DEFAULT_HREF;
  return href;
}

function safeRemoteHearingUrl(value) {
  const raw = typeof value === 'string' ? value.trim() : '';
  if (!raw) return '';
  try {
    const url = new URL(raw);
    if (url.protocol !== 'https:') return '';
    const host = url.hostname.toLowerCase();
    const allowedDomain = REMOTE_HEARING_DOMAINS.some((domain) => host === domain || host.endsWith(`.${domain}`));
    return allowedDomain ? url.href : '';
  } catch (_) {
    return '';
  }
}

function parsePushPayload(event) {
  if (!event.data) return {};
  try {
    return event.data.json();
  } catch (_) {
    try {
      return JSON.parse(event.data.text());
    } catch (_) {
      return {};
    }
  }
}

self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', (event) => {
  const payload = parsePushPayload(event);
  const title = typeof payload.title === 'string' && payload.title.trim() ? payload.title : 'IUSENTRA';
  const body = typeof payload.body === 'string' && payload.body.trim()
    ? payload.body
    : 'Hai una nuova notifica nel gestionale.';
  const href = safeHref(payload.href);
  const priority = typeof payload.priority === 'string' ? payload.priority : 'normal';
  const notificationId = typeof payload.notificationId === 'string' ? payload.notificationId : '';
  const remoteHearingUrl = safeRemoteHearingUrl(payload.remoteHearingUrl);
  const primaryActionTitle = href.startsWith('/scadenziario/')
    ? 'Apri scadenza'
    : href.startsWith('/agenda/')
      ? 'Apri Agenda'
      : 'Apri dettaglio';
  const actions = remoteHearingUrl
    ? [
        { action: 'open-app', title: primaryActionTitle },
        { action: 'join-hearing', title: 'Collegati' },
      ]
    : [];

  event.waitUntil(self.registration.showNotification(title, {
    body,
    icon: NOTIFICATION_ICON,
    badge: NOTIFICATION_BADGE,
    tag: notificationId || `iusentra-${priority}`,
    actions,
    data: { href, notificationId, remoteHearingUrl, version: SW_VERSION },
    renotify: true,
    requireInteraction: priority === 'urgent',
    silent: false,
    timestamp: Date.now(),
    vibrate: priority === 'urgent' ? [160, 80, 160] : [120],
  }));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const href = safeHref(event.notification && event.notification.data && event.notification.data.href);
  const remoteHearingUrl = safeRemoteHearingUrl(
    event.notification && event.notification.data && event.notification.data.remoteHearingUrl
  );
  event.waitUntil((async () => {
    if (event.action === 'join-hearing' && remoteHearingUrl) {
      return self.clients.openWindow(remoteHearingUrl);
    }
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const targetUrl = new URL(href, self.location.origin).href;
    for (const client of windows) {
      const clientUrl = new URL(client.url);
      if (clientUrl.origin === self.location.origin) {
        if ('navigate' in client) await client.navigate(targetUrl);
        if ('focus' in client) return client.focus();
      }
    }
    return self.clients.openWindow(targetUrl);
  })());
});

self.addEventListener('fetch', () => undefined);
