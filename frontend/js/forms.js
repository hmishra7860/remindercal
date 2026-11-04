/* Create/edit modals shared by the dashboard, reminders and birthdays pages. */

function reminderModal({ reminder = null, defaults = {}, user, onSaved }) {
  const r = reminder || {};
  const v = (k, d = '') => (r[k] ?? defaults[k] ?? d);
  const m = openModal(`
    <h2>${reminder ? 'Edit reminder' : 'New reminder'}</h2>
    <form id="rForm">
      <div class="field"><label>Title</label><input type="text" name="title" required maxlength="200" value="${esc(v('title'))}"></div>
      <div class="field"><label>Description</label><textarea name="description" maxlength="2000">${esc(v('description'))}</textarea></div>
      <div class="form-grid">
        <div class="field"><label>Category</label><select name="category">${['Work', 'Personal', 'Finance', 'Health'].map(c => `<option ${c === v('category', 'Personal') ? 'selected' : ''}>${c}</option>`).join('')}</select></div>
        <div class="field"><label>Recurrence</label><select name="recurrence">
          ${[['none', 'Does not repeat'], ['daily', 'Daily'], ['weekly', 'Weekly'], ['monthly', 'Monthly'], ['yearly', 'Yearly'], ['rolling', 'Keep in touch (rolling)']].map(([k, l]) => `<option value="${k}" ${k === v('recurrence', 'none') ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
        <div class="field"><label>Date</label><input type="date" name="date" required value="${esc(v('date', ymd(new Date())))}"></div>
        <div class="field"><label>Time</label><input type="time" name="time" value="${esc(fmtTime(v('time', pad(user.reminder_timing) + ':00')))}"></div>
      </div>
      <div class="field hidden" id="rollingBox"><label>Repeat every (days after you mark it done)</label><input type="number" name="rolling_interval_days" min="1" max="3650" value="${esc(v('rolling_interval_days', 14))}">
        <div class="hint">e.g. "Call Mom every 14 days": the next reminder is scheduled from when you click "Mark as Done".</div></div>
      <div class="field"><label>Timezone</label><select name="timezone">${tzOptions(v('timezone', user.timezone))}</select></div>
      <div class="field"><label>Send to someone else (optional)</label><input type="email" name="recipient_email" placeholder="friend@example.com" value="${esc(v('recipient_email'))}">
        <div class="hint">Requires your SMTP settings. Leave empty to remind yourself.</div></div>
      <div class="field"><label>Custom message (optional)</label><textarea name="custom_message" maxlength="2000" placeholder="Personal note shown in a highlighted box in the email">${esc(v('custom_message'))}</textarea></div>
      <div class="actions"><button type="button" class="btn secondary" data-cancel>Cancel</button><button class="btn" type="submit">${reminder ? 'Save changes' : 'Create reminder'}</button></div>
    </form>`);

  const form = $('#rForm', m.el);
  const toggle = () => $('#rollingBox', m.el).classList.toggle('hidden', form.recurrence.value !== 'rolling');
  form.recurrence.onchange = toggle; toggle();
  $('[data-cancel]', m.el).onclick = m.close;

  form.onsubmit = async e => {
    e.preventDefault();
    const f = new FormData(form);
    const body = {
      title: f.get('title'), description: f.get('description') || null, category: f.get('category'),
      recurrence: f.get('recurrence'), date: f.get('date'), time: f.get('time') || null,
      timezone: f.get('timezone'), recipient_email: f.get('recipient_email') || null,
      custom_message: f.get('custom_message') || null,
      rolling_interval_days: f.get('recurrence') === 'rolling' ? Number(f.get('rolling_interval_days')) : null,
    };
    try {
      await api(reminder ? `/reminders/${reminder.id}` : '/reminders', { method: reminder ? 'PUT' : 'POST', body });
      m.close(); toast(reminder ? 'Reminder updated' : 'Reminder created', 'success'); onSaved && onSaved();
    } catch (err) { toast(err.message, 'error'); }
  };
}

function birthdayModal({ birthday = null, user, onSaved }) {
  const b = birthday || {};
  const m = openModal(`
    <h2>${birthday ? 'Edit birthday' : 'Add birthday'}</h2>
    <form id="bForm">
      <div class="form-grid">
        <div class="field"><label>Name</label><input type="text" name="name" required maxlength="120" value="${esc(b.name)}"></div>
        <div class="field"><label>Date of birth</label><input type="date" name="date_of_birth" required value="${esc(b.date_of_birth)}"></div>
      </div>
      <div class="field"><label>Email (optional)</label><input type="email" name="email" placeholder="They'll receive a birthday wish from your address" value="${esc(b.email)}">
        <div class="hint">Without an email, ReminderCal reminds <em>you</em> on their birthday.</div></div>
      <div class="field"><label>Their timezone</label><select name="timezone">${tzOptions(b.timezone || '', { blank: `Same as mine (${user.timezone})` })}</select>
        <div class="hint">The wish is delivered at your preferred hour in their local time.</div></div>
      <div class="field"><label>Interests (optional)</label><input type="text" name="interests" maxlength="1000" placeholder="Football, jazz, hiking..." value="${esc(b.interests)}"></div>
      <div class="field"><label>Custom message (optional)</label><textarea name="custom_message" maxlength="2000" placeholder="Personal note added to the birthday email">${esc(b.custom_message)}</textarea></div>
      <div class="actions"><button type="button" class="btn secondary" data-cancel>Cancel</button><button class="btn" type="submit">${birthday ? 'Save changes' : 'Add birthday'}</button></div>
    </form>`);
  $('[data-cancel]', m.el).onclick = m.close;
  $('#bForm', m.el).onsubmit = async e => {
    e.preventDefault();
    const f = new FormData(e.target);
    const body = {
      name: f.get('name'), date_of_birth: f.get('date_of_birth'), email: f.get('email') || null,
      timezone: f.get('timezone') || null, interests: f.get('interests') || null, custom_message: f.get('custom_message') || null,
    };
    try {
      await api(birthday ? `/birthdays/${birthday.id}` : '/birthdays', { method: birthday ? 'PUT' : 'POST', body });
      m.close(); toast(birthday ? 'Birthday updated' : 'Birthday added', 'success'); onSaved && onSaved();
    } catch (err) { toast(err.message, 'error'); }
  };
}
