(async () => {
  const user = await initPage();
  if (!user) return;
  let items = [];

  const REPEAT = { none: 'Once', daily: 'Daily', weekly: 'Weekly', monthly: 'Monthly', yearly: 'Yearly' };
  const repeatLabel = r => r.recurrence === 'rolling' ? `Every ${r.rolling_interval_days}d after done` : REPEAT[r.recurrence];

  function render() {
    const q = $('#search').value.trim().toLowerCase(), cat = $('#catFilter').value, st = $('#statusFilter').value;
    const list = items.filter(r => (!cat || r.category === cat) && (!st || r.status === st) &&
      (!q || (r.title + ' ' + (r.description || '')).toLowerCase().includes(q)));
    $('#rows').innerHTML = list.length ? list.map(r => `
      <tr>
        <td><div style="font-weight:600">${esc(r.title)}</div>
          <div class="row" style="margin-top:4px"><span class="pill ${esc(r.category)}">${esc(r.category)}</span>
          ${r.recipient_email ? `<span class="muted small">→ ${esc(r.recipient_email)}</span>` : ''}</div>
          ${r.custom_message ? `<div class="muted small" style="margin-top:4px">“${esc(r.custom_message)}”</div>` : ''}</td>
        <td>${esc(fmtDate(r.date))}<div class="muted small">${esc(fmtTime(r.time))} · ${esc(r.timezone)}</div></td>
        <td>${esc(repeatLabel(r))}</td>
        <td><span class="pill ${esc(r.status)}">${esc(r.status)}</span>${r.snooze_until ? `<div class="muted small">Snoozed → ${esc(fmtDateTime(r.snooze_until))}</div>` : ''}</td>
        <td><div class="row">
          <button class="btn green sm" data-act="done" data-id="${r.id}">Done</button>
          <button class="btn secondary sm" data-act="snooze" data-id="${r.id}">Snooze 1h</button>
          <button class="btn secondary sm" data-act="edit" data-id="${r.id}">Edit</button>
          <button class="btn danger sm" data-act="delete" data-id="${r.id}">Delete</button></div></td>
      </tr>`).join('') : '<tr><td colspan="5"><div class="empty">No reminders yet. Create your first one!</div></td></tr>';
  }

  async function load() {
    try { items = await api('/reminders'); render(); } catch (err) { toast(err.message, 'error'); }
  }

  $('#rows').onclick = async e => {
    const btn = e.target.closest('[data-act]');
    if (!btn) return;
    const id = +btn.dataset.id, r = items.find(x => x.id === id);
    try {
      if (btn.dataset.act === 'edit') reminderModal({ reminder: r, user, onSaved: load });
      else if (btn.dataset.act === 'delete') {
        if (await confirmDialog(`Delete "${r.title}"?`)) { await api(`/reminders/${id}`, { method: 'DELETE' }); toast('Deleted', 'success'); load(); }
      } else {
        const res = await api(`/reminders/${id}/${btn.dataset.act}`, { method: 'POST' });
        toast(res.message, 'success'); load();
      }
    } catch (err) { toast(err.message, 'error'); }
  };

  ['search', 'catFilter', 'statusFilter'].forEach(id => $('#' + id).addEventListener('input', render));
  $('#addReminder').onclick = () => reminderModal({ user, onSaved: load });
  load();
})();
