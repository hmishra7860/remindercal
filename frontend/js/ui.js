/* Shared UI helpers: shell/navigation, notification bell, modals, toasts, formatting. */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/* ---------- dates ---------- */
const pad = n => String(n).padStart(2, '0');
const ymd = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const parseYmd = s => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); };
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
const fmtDate = s => parseYmd(s).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
const fmtTime = t => (t || '').slice(0, 5);
const fmtDateTime = iso => new Date(iso).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

function timeZones() {
  try { return Intl.supportedValuesOf('timeZone'); } catch (_) {
    return ['UTC', 'Asia/Kolkata', 'America/New_York', 'America/Los_Angeles', 'Europe/London', 'Europe/Berlin', 'Asia/Tokyo', 'Australia/Sydney'];
  }
}
function tzOptions(selected, { blank } = {}) {
  const list = timeZones();
  let html = blank ? `<option value="">${esc(blank)}</option>` : '';
  if (selected && !list.includes(selected)) html += `<option selected>${esc(selected)}</option>`;
  return html + list.map(z => `<option value="${esc(z)}" ${z === selected ? 'selected' : ''}>${esc(z)}</option>`).join('');
}

/* ---------- toast / modal ---------- */
function toast(msg, type = 'info') {
  let box = $('#toasts');
  if (!box) { box = document.createElement('div'); box.id = 'toasts'; document.body.appendChild(box); }
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  el.textContent = msg;
  box.appendChild(el);
  setTimeout(() => el.remove(), 4500);
}

function openModal(html) {
  const overlay = document.createElement('div');
  overlay.className = 'overlay';
  overlay.innerHTML = `<div class="modal">${html}</div>`;
  const close = () => { overlay.remove(); document.removeEventListener('keydown', onKey); };
  const onKey = e => { if (e.key === 'Escape') close(); };
  overlay.addEventListener('mousedown', e => { if (e.target === overlay) close(); });
  document.addEventListener('keydown', onKey);
  document.body.appendChild(overlay);
  return { el: overlay.firstElementChild, close };
}

function confirmDialog(message, okLabel = 'Delete') {
  return new Promise(resolve => {
    const m = openModal(`<h2>Are you sure?</h2><p class="muted">${esc(message)}</p>
      <div class="actions"><button class="btn secondary" data-no>Cancel</button><button class="btn danger" data-yes>${esc(okLabel)}</button></div>`);
    $('[data-no]', m.el).onclick = () => { m.close(); resolve(false); };
    $('[data-yes]', m.el).onclick = () => { m.close(); resolve(true); };
  });
}

/* ---------- shell ---------- */
const NAV = [
  ['dashboard', '📊', 'Dashboard', '/dashboard.html'],
  ['reminders', '🔔', 'Reminders', '/reminders.html'],
  ['birthdays', '🎂', 'Birthdays', '/birthdays.html'],
  ['settings', '⚙️', 'Settings', '/settings.html'],
];

async function initPage() {
  if (!Auth.token) { location.href = '/index.html'; return null; }
  const root = $('#shell');
  const page = root.dataset.page, title = root.dataset.title;
  const content = root.innerHTML;
  root.innerHTML = `
    <aside class="sidebar" id="sidebar">
      <div class="brand">🔔 ReminderCal</div>
      <nav class="nav">${NAV.map(([k, i, l, h]) => `<a href="${h}" class="${k === page ? 'active' : ''}"><span>${i}</span>${l}</a>`).join('')}</nav>
    </aside>
    <div class="main">
      <header class="topbar">
        <div class="row"><button class="menu-btn" id="menuBtn">☰</button><h1>${esc(title)}</h1></div>
        <div class="right">
          <button class="bell" id="bell" title="Notifications">🔔<span class="badge hidden" id="bellBadge">0</span></button>
          <span class="user-chip" id="userChip"></span>
          <button class="btn secondary sm" id="logoutBtn">Sign out</button>
        </div>
      </header>
      <div class="bell-panel hidden" id="bellPanel"></div>
      <main class="content">${content}</main>
    </div>`;
  $('#menuBtn').onclick = () => $('#sidebar').classList.toggle('open');
  $('#logoutBtn').onclick = () => { Auth.clear(); location.href = '/index.html'; };

  registerServiceWorker();
  const user = await api('/auth/profile');
  $('#userChip').textContent = user.full_name;
  initBell();
  return user;
}

function registerServiceWorker() {
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
}

/* ---------- in-app bell (polls every 30s) ---------- */
let lastUnread = null;
function initBell() {
  const panel = $('#bellPanel');
  $('#bell').onclick = async e => {
    e.stopPropagation();
    panel.classList.toggle('hidden');
    if (!panel.classList.contains('hidden')) renderBell(await refreshBell());
  };
  document.addEventListener('click', e => { if (!panel.contains(e.target)) panel.classList.add('hidden'); });
  refreshBell();
  setInterval(refreshBell, 30000);
}

async function refreshBell() {
  try {
    const data = await api('/notifications/inbox');
    const badge = $('#bellBadge');
    badge.textContent = data.unread > 99 ? '99+' : data.unread;
    badge.classList.toggle('hidden', data.unread === 0);
    if (lastUnread !== null && data.unread > lastUnread && data.items[0]) toast('🔔 ' + data.items[0].title);
    lastUnread = data.unread;
    return data;
  } catch (_) { return { unread: 0, items: [] }; }
}

function renderBell(data) {
  const panel = $('#bellPanel');
  panel.innerHTML = `<header><span>Notifications</span><button class="btn secondary sm" id="markAll">Mark all read</button></header>` +
    (data.items.length ? data.items.map(n => `<div class="bell-item ${n.is_read ? '' : 'unread'}">
      <div class="t">${esc(n.title)}</div>${n.body ? `<div class="b">${esc(n.body)}</div>` : ''}<div class="when">${fmtDateTime(n.created_at)}</div></div>`).join('')
      : '<div class="empty">You\'re all caught up 🎉</div>');
  $('#markAll').onclick = async () => { await api('/notifications/inbox/read', { method: 'POST', body: {} }); lastUnread = 0; renderBell(await refreshBell()); };
}
