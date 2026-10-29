/* StudySync UI — theme, menus, liquid-glass highlights, toasts, countdown. No libraries. */
(() => {
  'use strict';
  const root = document.documentElement;
  root.classList.add('js');
  const KEY = 'studysync-theme';
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const finePointer = window.matchMedia('(pointer: fine)').matches;

  /* ---- theme switch (dark = black/cobalt/lime, light = beige/sage/burgundy) ---- */
  const toggle = document.querySelector('[data-theme-toggle]');
  const current = () => (root.getAttribute('data-theme') === 'dark' ? 'dark' : 'light');
  function applyTheme(theme, persist) {
    root.setAttribute('data-theme', theme);
    if (persist) { try { localStorage.setItem(KEY, theme); } catch (_) { /* storage blocked */ } }
    if (toggle) {
      toggle.setAttribute('aria-checked', String(theme === 'dark'));
      toggle.setAttribute('aria-label', theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
    }
  }
  applyTheme(current(), false);
  toggle?.addEventListener('click', () => applyTheme(current() === 'dark' ? 'light' : 'dark', true));

  /* ---- mobile nav ---- */
  const nav = document.getElementById('site-nav');
  const burger = nav?.querySelector('.nav-burger');
  burger?.addEventListener('click', () => {
    const open = nav.classList.toggle('is-open');
    burger.setAttribute('aria-expanded', String(open));
    burger.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
  });

  /* ---- account menu ---- */
  document.querySelectorAll('[data-menu]').forEach(menu => {
    const trigger = menu.querySelector('[data-menu-trigger]');
    const set = open => { menu.dataset.open = String(open); trigger.setAttribute('aria-expanded', String(open)); };
    trigger.addEventListener('click', e => { e.stopPropagation(); set(menu.dataset.open !== 'true'); });
    document.addEventListener('click', e => { if (!menu.contains(e.target)) set(false); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') { set(false); } });
  });

  /* ---- liquid glass: pointer-tracked specular highlight ---- */
  if (!reduceMotion && finePointer) {
    document.addEventListener('pointermove', e => {
      const glass = e.target.closest?.('.glass');
      if (!glass) return;
      const r = glass.getBoundingClientRect();
      glass.style.setProperty('--mx', `${((e.clientX - r.left) / r.width * 100).toFixed(1)}%`);
      glass.style.setProperty('--my', `${((e.clientY - r.top) / r.height * 100).toFixed(1)}%`);
    }, { passive: true });
  }

  /* ---- reveal on scroll ---- */
  const reveals = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window && !reduceMotion) {
    const io = new IntersectionObserver(entries => entries.forEach(en => {
      if (en.isIntersecting) { en.target.classList.add('is-in'); io.unobserve(en.target); }
    }), { threshold: .08, rootMargin: '0px 0px -40px 0px' });
    reveals.forEach((el, i) => { el.style.transitionDelay = `${Math.min(i % 6, 5) * 60}ms`; io.observe(el); });
  } else { reveals.forEach(el => el.classList.add('is-in')); }

  /* ---- toasts: auto dismiss ---- */
  document.querySelectorAll('.toast').forEach(toast => {
    const close = () => { toast.classList.add('is-leaving'); setTimeout(() => toast.remove(), 400); };
    toast.querySelector('.toast-close')?.addEventListener('click', close);
    setTimeout(close, 6500);
  });

  /* ---- select feedback + active filter chips ---- */
  document.querySelectorAll('[data-filter-select]').forEach(select => {
    const shell = select.closest('.select-shell');
    const update = () => { if (shell) shell.dataset.selected = select.value ? 'true' : 'false'; };
    select.addEventListener('change', update); update();
  });
  const form = document.getElementById('discovery-form');
  const summary = document.getElementById('active-filter-summary');
  if (form && summary) {
    ['kind', 'subject', 'date', 'time', 'location', 'when', 'capacity', 'sort', 'q'].forEach(name => {
      const field = form.elements.namedItem(name);
      if (!field || !field.value) return;
      const text = field.tagName === 'SELECT' ? field.selectedOptions[0]?.textContent : field.value;
      const label = { q: 'Keyword', kind: 'Category', sort: 'Sort' }[name] || name[0].toUpperCase() + name.slice(1);
      const chip = document.createElement('span');
      chip.className = 'chip'; chip.textContent = `${label}: ${text}`;
      summary.appendChild(chip);
    });
  }
  /* collapse filters on small screens */
  const filters = document.getElementById('study-filters');
  const fToggle = filters?.querySelector('.filters-toggle');
  if (filters && fToggle) {
    if (window.matchMedia('(max-width: 640px)').matches) { filters.classList.add('is-collapsed'); fToggle.setAttribute('aria-expanded', 'false'); }
    fToggle.addEventListener('click', () => {
      const collapsed = filters.classList.toggle('is-collapsed');
      fToggle.setAttribute('aria-expanded', String(!collapsed));
    });
  }

  /* ---- bookings tabs ---- */
  const tabs = document.querySelectorAll('[data-tab]');
  if (tabs.length) {
    tabs.forEach(tab => tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.toggle('is-on', t === tab));
      document.querySelectorAll('[data-tab-panel]').forEach(p => { p.hidden = p.dataset.tabPanel !== tab.dataset.tab; });
    }));
  }

  /* ---- countdown to next session ---- */
  document.querySelectorAll('[data-countdown]').forEach(el => {
    const target = new Date(el.dataset.countdown);
    const out = el.querySelector('span');
    const tick = () => {
      const ms = target - new Date();
      if (isNaN(ms) || ms <= 0) { out.textContent = 'Now'; return; }
      const d = Math.floor(ms / 864e5), h = Math.floor(ms % 864e5 / 36e5), m = Math.floor(ms % 36e5 / 6e4);
      out.textContent = d ? `${d}d ${h}h` : `${h}h ${m}m`;
    };
    tick(); setInterval(tick, 30000);
  });

  /* ---- command palette (Ctrl/Cmd+K) ---- */
  const palette = document.getElementById('palette');
  const pInput = document.getElementById('palette-input');
  const pList = document.getElementById('palette-results');
  const pEmpty = document.getElementById('palette-empty');
  if (palette && pInput && pList) {
    let timer, seq = 0, active = -1;
    const items = () => [...pList.querySelectorAll('a')];
    const mark = i => { const a = items(); if (!a.length) return; active = (i + a.length) % a.length; a.forEach((el, n) => el.classList.toggle('is-active', n === active)); a[active].scrollIntoView({ block: 'nearest' }); };
    const openP = () => { palette.hidden = false; pInput.value = ''; pList.replaceChildren(); if (pEmpty) pEmpty.hidden = true; pInput.focus(); search(''); };
    const closeP = () => { palette.hidden = true; };
    async function search(q) {
      const id = ++seq;
      try {
        const res = await fetch(`${pInput.dataset.searchUrl}?q=${encodeURIComponent(q)}`, { headers: { Accept: 'application/json' }, credentials: 'same-origin' });
        if (!res.ok || id !== seq) return;
        const data = await res.json();
        pList.replaceChildren(...data.results.map(r => {
          const li = document.createElement('li'), a = document.createElement('a'), t = document.createElement('span'), s = document.createElement('small');
          a.href = r.url; t.textContent = r.title; s.textContent = r.subtitle || r.type || ''; a.append(t, s); li.append(a); return li;
        }));
        if (pEmpty) pEmpty.hidden = data.results.length > 0;
        active = -1; if (data.results.length) mark(0);
      } catch (_) { /* offline: ignore */ }
    }
    document.querySelectorAll('[data-palette-open]').forEach(b => b.addEventListener('click', openP));
    document.addEventListener('keydown', e => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); palette.hidden ? openP() : closeP(); }
      else if (!palette.hidden && e.key === 'Escape') closeP();
      else if (!palette.hidden && e.key === 'ArrowDown') { e.preventDefault(); mark(active + 1); }
      else if (!palette.hidden && e.key === 'ArrowUp') { e.preventDefault(); mark(active - 1); }
      else if (!palette.hidden && e.key === 'Enter') { const a = items()[active]; if (a) { e.preventDefault(); location.href = a.href; } }
    });
    palette.addEventListener('click', e => { if (e.target === palette) closeP(); });
    pInput.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => search(pInput.value.trim()), 150); });
  }

  /* ---- chat: scroll to latest ---- */
  document.querySelectorAll('[data-chat]').forEach(el => { el.scrollTop = el.scrollHeight; });

  /* ---- confirm prompts ---- */
  document.querySelectorAll('button[data-confirm]').forEach(btn => {
    btn.addEventListener('click', e => { if (!window.confirm(btn.dataset.confirm)) e.preventDefault(); });
  });
})();
