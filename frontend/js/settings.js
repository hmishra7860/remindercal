(async () => {
  let user = await initPage();
  if (!user) return;

  /* ---------- tabs ---------- */
  function showTab(name) {
    $$('#tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === name));
    $$('[data-panel]').forEach(p => p.classList.toggle('hidden', p.dataset.panel !== name));
    if (name === 'logs') loadLogs();
  }
  $$('#tabs button').forEach(b => b.onclick = () => showTab(b.dataset.tab));

  /* ---------- fill forms ---------- */
  function fill() {
    const pf = $('#profileForm');
    pf.full_name.value = user.full_name;
    $('#pEmail').value = user.email;
    $('#pTz').innerHTML = tzOptions(user.timezone);
    $('#pTiming').innerHTML = Array.from({ length: 24 }, (_, h) => `<option value="${h}" ${h === user.reminder_timing ? 'selected' : ''}>${pad(h)}:00</option>`).join('');

    const sf = $('#smtpForm');
    sf.smtp_host.value = user.smtp_host || '';
    sf.smtp_port.value = user.smtp_port || 587;
    sf.smtp_user.value = user.smtp_user || '';
    sf.smtp_pass.value = '';
    sf.from_email.value = user.from_email || '';
    const st = $('#smtpState');
    st.textContent = user.smtp_configured ? 'Configured' : 'Not configured';
    st.className = 'pill ' + (user.smtp_configured ? 'sent' : 'pending');

    $$('[data-pref]').forEach(c => c.checked = !!user[c.dataset.pref]);
    $('#dMethod').value = user.delivery_method;
    $('#deliveryForm').webhook_url.value = user.webhook_url || '';
    toggleWebhook();
    $('#feedUrl').value = user.feed_url;
    $('#inboundAddr').value = user.inbound_address;
  }
  const toggleWebhook = () => $('#webhookBox').classList.toggle('hidden', $('#dMethod').value === 'email');
  $('#dMethod').onchange = toggleWebhook;

  async function save(path, body, okMsg) {
    try { user = await api(path, { method: 'PUT', body }); fill(); toast(okMsg, 'success'); }
    catch (err) { toast(err.message, 'error'); }
  }

  $('#profileForm').onsubmit = e => {
    e.preventDefault();
    save('/auth/profile', { full_name: e.target.full_name.value, timezone: $('#pTz').value, reminder_timing: Number($('#pTiming').value) }, 'Profile saved');
  };

  $('#smtpForm').onsubmit = e => {
    e.preventDefault();
    const f = e.target;
    save('/auth/profile/smtp', {
      smtp_host: f.smtp_host.value, smtp_port: Number(f.smtp_port.value), smtp_user: f.smtp_user.value,
      smtp_pass: f.smtp_pass.value || null, from_email: f.from_email.value || null,
    }, 'SMTP settings saved');
  };

  $('#smtpTest').onclick = async () => {
    const btn = $('#smtpTest'); btn.disabled = true; btn.textContent = 'Sending...';
    try { const res = await api('/auth/profile/smtp/test', { method: 'POST' }); toast(res.message, 'success'); }
    catch (err) { toast(err.message, 'error'); }
    btn.disabled = false; btn.textContent = 'Send test email';
  };

  $$('[data-pref]').forEach(c => c.onchange = () => save('/auth/profile', { [c.dataset.pref]: c.checked }, 'Preference saved'));

  $('#deliveryForm').onsubmit = e => {
    e.preventDefault();
    save('/auth/profile', { delivery_method: $('#dMethod').value, webhook_url: e.target.webhook_url.value || null }, 'Delivery method saved');
  };

  /* ---------- copy / regenerate ---------- */
  $$('[data-copy]').forEach(b => b.onclick = async () => {
    const input = $('#' + b.dataset.copy);
    try { await navigator.clipboard.writeText(input.value); } catch (_) { input.select(); document.execCommand('copy'); }
    toast('Copied', 'success');
  });
  $('#regenFeed').onclick = async () => {
    if (!await confirmDialog('The old feed URL will stop working. Continue?', 'Regenerate')) return;
    try { user = await api('/auth/profile/feed-token/regenerate', { method: 'POST' }); fill(); toast('New feed URL generated', 'success'); }
    catch (err) { toast(err.message, 'error'); }
  };

  /* ---------- web push ---------- */
  const b64ToUint8 = s => {
    const pad = '='.repeat((4 - s.length % 4) % 4);
    const raw = atob((s + pad).replace(/-/g, '+').replace(/_/g, '/'));
    return Uint8Array.from(raw, c => c.charCodeAt(0));
  };
  $('#pushBtn').onclick = async () => {
    try {
      if (!('serviceWorker' in navigator) || !('PushManager' in window)) throw new Error('This browser does not support Web Push');
      if (await Notification.requestPermission() !== 'granted') throw new Error('Notification permission was denied');
      const { public_key } = await api('/push/vapid-key');
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToUint8(public_key) });
      await api('/push/subscribe', { method: 'POST', body: sub.toJSON() });
      toast('Browser notifications enabled', 'success');
      $('#pushBtn').textContent = 'Browser notifications enabled ✔';
    } catch (err) { toast(err.message, 'error'); }
  };

  /* ---------- delivery logs ---------- */
  async function loadLogs() {
    const status = $('#logStatus').value;
    try {
      const logs = await api('/notifications' + (status ? `?status=${status}` : ''));
      $('#logRows').innerHTML = logs.length ? logs.map(l => `<tr>
        <td style="white-space:nowrap">${esc(fmtDateTime(l.sent_at))}</td>
        <td><span class="pill ${l.kind === 'birthday' ? 'birthday' : ''}">${esc(l.kind)}</span></td>
        <td>${esc(l.subject || '-')}</td>
        <td>${esc(l.email)}<div class="muted small">${esc(l.channel)}</div></td>
        <td><span class="pill ${esc(l.status)}">${esc(l.status)}</span></td>
        <td class="muted small">${esc(l.message || '')}</td></tr>`).join('')
        : '<tr><td colspan="6"><div class="empty">No deliveries yet</div></td></tr>';
    } catch (err) { toast(err.message, 'error'); }
  }
  $('#logStatus').onchange = loadLogs;
  $('#logRefresh').onclick = loadLogs;

  fill();
})();
