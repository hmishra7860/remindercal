(async () => {
  const user = await initPage();
  if (!user) return;

  const data = { reminders: [], birthdays: [] };
  let calendar;

  async function load() {
    [data.reminders, data.birthdays] = await Promise.all([api('/reminders'), api('/birthdays')]);
    const today = new Date(), in7 = addDays(today, 7), in30 = addDays(today, 30);
    const todayS = ymd(today);
    const next7 = expandEvents(data.reminders, [], today, in7);
    $('#sTotal').textContent = data.reminders.length;
    $('#sToday').textContent = next7.filter(e => e.date === todayS).length;
    $('#sUpcoming').textContent = next7.length;
    $('#sBdays').textContent = data.birthdays.filter(b => b.days_left <= 30).length;

    const upcoming = expandEvents(data.reminders, data.birthdays, today, in30)
      .filter(e => e.date > todayS || (e.date === todayS && (e.type === 'birthday' || !e.time || e.time >= new Date().toTimeString().slice(0, 5))))
      .slice(0, 8);
    $('#upcoming').innerHTML = upcoming.length ? upcoming.map(e => `
      <div class="upcoming-item"><div class="t">${esc(e.title)}</div>
        <div class="muted small">${esc(fmtDate(e.date))}${e.time ? ' · ' + esc(e.time) : ''}${e.age ? ' · turns ' + e.age : ''}</div></div>`).join('')
      : '<div class="empty">Nothing coming up</div>';

    if (calendar) calendar.render();
  }

  calendar = new Calendar($('#calendar'), {
    getData: () => data,
    onDayClick: day => reminderModal({ defaults: { date: day }, user, onSaved: load }),
    onEventClick: ev => ev.type === 'birthday'
      ? birthdayModal({ birthday: ev.ref, user, onSaved: load })
      : reminderModal({ reminder: ev.ref, user, onSaved: load }),
  });

  $('#addReminder').onclick = () => reminderModal({ user, onSaved: load });
  $('#addBirthday').onclick = () => birthdayModal({ user, onSaved: load });
  try { await load(); } catch (err) { toast(err.message, 'error'); }
})();
