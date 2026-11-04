(async () => {
  const user = await initPage();
  if (!user) return;
  let items = [];

  function render() {
    const q = $('#search').value.trim().toLowerCase();
    const list = items.filter(b => !q || (b.name + ' ' + (b.interests || '')).toLowerCase().includes(q));
    $('#grid').innerHTML = list.length ? list.map(b => `
      <div class="card b-card">
        <div class="row spread">
          <div class="row"><div class="avatar">${esc(b.name.trim()[0].toUpperCase())}</div>
            <div><div style="font-weight:700">${esc(b.name)}</div><div class="muted small">${esc(fmtDate(b.date_of_birth))}</div></div></div>
          <span class="pill birthday">Turns ${b.age}</span>
        </div>
        ${b.email ? `<div class="muted small" style="margin-top:10px">✉ ${esc(b.email)}</div>` : '<div class="muted small" style="margin-top:10px">No email · you will be reminded</div>'}
        ${b.interests ? `<div class="small" style="margin-top:6px">❤ ${esc(b.interests)}</div>` : ''}
        ${b.timezone ? `<div class="muted small" style="margin-top:6px">🌍 ${esc(b.timezone)}</div>` : ''}
        <div class="countdown">${b.days_left === 0 ? '🎉 Today!' : b.days_left === 1 ? 'Tomorrow' : b.days_left + ' days left'}</div>
        <div class="row" style="margin-top:12px">
          <button class="btn secondary sm" data-act="edit" data-id="${b.id}">Edit</button>
          <button class="btn danger sm" data-act="delete" data-id="${b.id}">Remove</button></div>
      </div>`).join('') : '<div class="card empty" style="grid-column:1/-1">No birthdays tracked yet.</div>';
  }

  async function load() {
    try { items = await api('/birthdays'); render(); } catch (err) { toast(err.message, 'error'); }
  }

  $('#grid').onclick = async e => {
    const btn = e.target.closest('[data-act]');
    if (!btn) return;
    const b = items.find(x => x.id === +btn.dataset.id);
    if (btn.dataset.act === 'edit') birthdayModal({ birthday: b, user, onSaved: load });
    else if (await confirmDialog(`Remove ${b.name}'s birthday?`, 'Remove')) {
      try { await api(`/birthdays/${b.id}`, { method: 'DELETE' }); toast('Removed', 'success'); load(); } catch (err) { toast(err.message, 'error'); }
    }
  };
  $('#search').addEventListener('input', render);
  $('#addBirthday').onclick = () => birthdayModal({ user, onSaved: load });
  load();
})();
