/* API client with a token interceptor: attaches the JWT to every request and
   bounces to the login page when the server answers 401. */
const API_BASE = '/api';

const Auth = {
  get token() { return localStorage.getItem('rc_token'); },
  set(token) { localStorage.setItem('rc_token', token); },
  clear() { localStorage.removeItem('rc_token'); },
};

function formatError(detail) {
  if (Array.isArray(detail)) {
    return detail.map(d => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`).join('; ');
  }
  return typeof detail === 'string' ? detail : JSON.stringify(detail);
}

async function api(path, { method = 'GET', body, auth = true } = {}) {
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (auth && Auth.token) headers['Authorization'] = 'Bearer ' + Auth.token;

  const res = await fetch(API_BASE + path, {
    method, headers, body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && auth) {
    Auth.clear();
    location.href = '/index.html';
    throw new Error('Session expired. Please sign in again.');
  }
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = formatError((await res.json()).detail); } catch (_) { /* not JSON */ }
    throw new Error(detail || 'Request failed');
  }
  return res.status === 204 ? null : res.json();
}
