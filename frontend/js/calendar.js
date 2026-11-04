/* Expands reminders/birthdays into dated events and renders Month / Week / Day views. */

function inRange(d, start, end) { return d >= start && d <= end; }

function expandEvents(reminders, birthdays, start, end) {
  const out = [];
  start = new Date(start.getFullYear(), start.getMonth(), start.getDate());
  end = new Date(end.getFullYear(), end.getMonth(), end.getDate());

  for (const r of reminders) {
    const base = parseYmd(r.date);
    const push = d => out.push({ type: 'reminder', ref: r, date: ymd(d), time: fmtTime(r.time), title: r.title, category: r.category });
    if (r.recurrence === 'none' || r.recurrence === 'rolling') {
      if (inRange(base, start, end)) push(base);
    } else if (r.recurrence === 'daily' || r.recurrence === 'weekly') {
      const step = r.recurrence === 'daily' ? 1 : 7;
      let d = new Date(base);
      if (d < start) {
        const diff = Math.round((start - base) / 86400000);
        d = addDays(base, Math.ceil(diff / step) * step);
      }
      for (; d <= end; d = addDays(d, step)) push(d);
    } else if (r.recurrence === 'monthly') {
      for (let y = start.getFullYear(), m = start.getMonth(); new Date(y, m, 1) <= end; m++) {
        if (m > 11) { m = 0; y++; }
        const dim = new Date(y, m + 1, 0).getDate();
        const d = new Date(y, m, Math.min(base.getDate(), dim));
        if (d >= base && inRange(d, start, end)) push(d);
      }
    } else if (r.recurrence === 'yearly') {
      for (let y = start.getFullYear(); y <= end.getFullYear(); y++) {
        let d = new Date(y, base.getMonth(), base.getDate());
        if (d.getMonth() !== base.getMonth()) d = new Date(y, base.getMonth(), 28);
        if (d >= base && inRange(d, start, end)) push(d);
      }
    }
  }

  for (const b of birthdays) {
    const dob = parseYmd(b.date_of_birth);
    for (let y = start.getFullYear(); y <= end.getFullYear(); y++) {
      let d = new Date(y, dob.getMonth(), dob.getDate());
      if (d.getMonth() !== dob.getMonth()) d = new Date(y, 1, 28);
      if (inRange(d, start, end)) out.push({ type: 'birthday', ref: b, date: ymd(d), time: '', title: `🎂 ${b.name}`, category: 'birthday', age: y - dob.getFullYear() });
    }
  }
  return out.sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time));
}

class Calendar {
  constructor(el, { getData, onDayClick, onEventClick }) {
    this.el = el; this.getData = getData; this.onDayClick = onDayClick; this.onEventClick = onEventClick;
    this.view = 'month'; this.cursor = new Date();
    this.render();
  }

  range() {
    const c = this.cursor;
    if (this.view === 'month') {
      const first = new Date(c.getFullYear(), c.getMonth(), 1);
      const start = addDays(first, -first.getDay());
      return { start, end: addDays(start, 41) };
    }
    if (this.view === 'week') {
      const start = addDays(c, -c.getDay());
      return { start, end: addDays(start, 6) };
    }
    return { start: c, end: c };
  }

  title() {
    const c = this.cursor;
    if (this.view === 'month') return c.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
    if (this.view === 'week') {
      const { start, end } = this.range();
      return `${start.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })} - ${end.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })}`;
    }
    return c.toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  }

  shift(dir) {
    const c = new Date(this.cursor);
    if (this.view === 'month') c.setMonth(c.getMonth() + dir, 1);
    else c.setDate(c.getDate() + dir * (this.view === 'week' ? 7 : 1));
    this.cursor = c; this.render();
  }

  render() {
    const { start, end } = this.range();
    const { reminders, birthdays } = this.getData();
    const events = expandEvents(reminders, birthdays, start, end);
    const byDay = {};
    events.forEach(e => (byDay[e.date] ||= []).push(e));
    const todayS = ymd(new Date());

    const evHtml = (e, i) => `<div class="ev ${esc(e.category)}" data-ev="${e.date}|${i}" title="${esc(e.title)}">${e.time ? esc(e.time) + ' ' : ''}${esc(e.title)}</div>`;

    let body = '';
    if (this.view === 'month') {
      const dows = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
      body = '<div class="month">' + dows.map(d => `<div class="dow">${d}</div>`).join('');
      for (let i = 0; i < 42; i++) {
        const d = addDays(start, i), s = ymd(d), list = byDay[s] || [];
        body += `<div class="cell ${d.getMonth() !== this.cursor.getMonth() ? 'other' : ''} ${s === todayS ? 'today' : ''}" data-day="${s}">
          <span class="dn">${d.getDate()}</span>${list.slice(0, 3).map((e, k) => evHtml(e, k)).join('')}${list.length > 3 ? `<div class="more">+${list.length - 3} more</div>` : ''}</div>`;
      }
      body += '</div>';
    } else if (this.view === 'week') {
      body = '<div class="week">';
      for (let i = 0; i < 7; i++) {
        const d = addDays(start, i), s = ymd(d), list = byDay[s] || [];
        body += `<div class="col ${s === todayS ? 'today' : ''}" data-day="${s}"><h4>${d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric' })}</h4>${list.map((e, k) => evHtml(e, k)).join('')}</div>`;
      }
      body += '</div>';
    } else {
      const s = ymd(this.cursor), list = byDay[s] || [];
      body = '<div class="dayview">' + (list.length ? list.map((e, k) => `<div class="item" data-ev="${s}|${k}"><div class="time">${esc(e.time || 'All day')}</div><div><div style="font-weight:600">${esc(e.title)}</div><span class="pill ${esc(e.category)}">${esc(e.type === 'birthday' ? 'Birthday' : e.category)}</span></div></div>`).join('')
        : '<div class="empty">Nothing scheduled. Click "+ Reminder" to add something.</div>') + '</div>';
    }

    this.el.innerHTML = `<div class="cal-head">
        <div class="row"><button class="btn secondary sm" data-nav="-1">‹</button><button class="btn secondary sm" data-nav="0">Today</button><button class="btn secondary sm" data-nav="1">›</button><h2>${esc(this.title())}</h2></div>
        <div class="seg">${['month', 'week', 'day'].map(v => `<button data-view="${v}" class="${v === this.view ? 'on' : ''}">${v[0].toUpperCase() + v.slice(1)}</button>`).join('')}</div>
      </div>${body}`;

    $$('[data-nav]', this.el).forEach(b => b.onclick = () => { const n = +b.dataset.nav; if (n === 0) { this.cursor = new Date(); this.render(); } else this.shift(n); });
    $$('[data-view]', this.el).forEach(b => b.onclick = () => { this.view = b.dataset.view; this.render(); });
    $$('[data-day]', this.el).forEach(c => c.onclick = e => { if (!e.target.closest('[data-ev]')) this.onDayClick && this.onDayClick(c.dataset.day); });
    $$('[data-ev]', this.el).forEach(n => n.onclick = e => {
      e.stopPropagation();
      const [s, k] = n.dataset.ev.split('|');
      const ev = (byDay[s] || [])[+k];
      if (ev && this.onEventClick) this.onEventClick(ev);
    });
  }
}
