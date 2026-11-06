// In-page scenario simulator for senate.html. Inlined by build_senate.py; SIM is the data it injects.
// simulate() mirrors simulate() in senate_model.py: per simulation, one national, one regional and one per-race
// Student-t error. The levers add a uniform swing, scale every error, fix race outcomes and pick the caucus rule.
// A fixed seed means the same draws are reused on every run, so a change in output comes from the lever, not noise.

function mulberry32(a) {
  return function () {
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function simulate(S, o) {
  const rnd = mulberry32(2026);
  let spare = null;
  const gauss = () => {
    if (spare !== null) { const z = spare; spare = null; return z; }
    const u = 1 - rnd(), v = rnd(), r = Math.sqrt(-2 * Math.log(u));
    spare = r * Math.sin(2 * Math.PI * v);
    return r * Math.cos(2 * Math.PI * v);
  };
  // Unit-variance Student-t; chi-square with even df is -2·ln of a product of df/2 uniforms.
  const df = S.t_df, scale = Math.sqrt((df - 2) / df);
  const t = () => {
    let p = 1;
    for (let j = 0; j < df / 2; j++) p *= 1 - rnd();
    return gauss() / Math.sqrt(-2 * Math.log(p) / df) * scale;
  };
  const races = S.races, nR = races.length;
  const lock = races.map(r => o.locks[r.st] || null);
  const wins = new Float64Array(nR), reg = new Float64Array(S.regions.length), hist = new Float64Array(101);
  let pD = 0, pR = 0, pU = 0, sum = 0;
  for (let s = 0; s < S.n; s++) {
    const nat = t() * S.national_sd * o.err + o.swing;
    for (let g = 0; g < reg.length; g++) reg[g] = t() * S.regional_sd * o.err;
    let d = S.hold.D, i = 0;
    for (let j = 0; j < nR; j++) {
      const r = races[j];
      const drawn = r.mean + nat + reg[r.reg] + t() * r.sd * o.err > 0;  // draw even when locked, to keep draws aligned
      if (lock[j] ? lock[j] === 'C' : drawn) { wins[j]++; if (r.chp === 'D') d++; else i++; }
    }
    const dd = d + (o.caucus === 'D' ? i : 0), rr = 100 - d - i + (o.caucus === 'R' ? i : 0);
    if (dd >= 51) pD++; else if (rr >= 50) pR++; else pU++;
    const side = o.caucus === 'R' ? d : d + i;  // seats charted: D plus independents unless they side with R
    hist[side]++; sum += side;
  }
  const n = S.n, pct = q => { let c = 0; for (let k = 0; k <= 100; k++) { c += hist[k]; if (c >= q * n) return k; } };
  return { D: pD / n, R: pR / n, U: pU / n, exp: sum / n, med: pct(0.5), lo: pct(0.1), hi: pct(0.9),
           hist: Array.from(hist, v => v / n), p: Array.from(wins, v => v / n) };
}

// Seats if every race goes to whoever leads after the swing (no noise), with locks applied.
function leaders(S, o) {
  let d = S.hold.D, i = 0;
  S.races.forEach(r => {
    const l = o.locks[r.st], win = l ? l === 'C' : r.mean + o.swing > 0;
    if (win) { if (r.chp === 'D') d++; else i++; }
  });
  return { D: d, I: i, R: 100 - d - i };
}

if (typeof module !== 'undefined') module.exports = { simulate, leaders };

if (typeof document !== 'undefined') (function () {
  const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  const DEFAULT = { swing: 0, err: 1, caucus: 'sep', locks: {} };
  let o = JSON.parse(JSON.stringify(DEFAULT));
  const base = simulate(SIM, DEFAULT);
  const pct = p => p >= 0.995 ? '>99%' : p <= 0.005 ? '<1%' : Math.round(p * 100) + '%';
  const swingTxt = v => v === 0 ? 'None' : (v > 0 ? 'D+' : 'R+') + Math.abs(v);
  // Change vs. the no-lever run, hidden when it rounds to zero at the shown precision.
  const delta = (v, b, digits, unit) => {
    const d = +(v - b).toFixed(digits);
    return d === 0 ? '' : `<em class="${d > 0 ? 'up' : 'dn'}">${d > 0 ? '+' : '−'}${Math.abs(d).toFixed(digits)}${unit}</em>`;
  };

  function readHash() {
    try {
      const h = new URLSearchParams(location.hash.slice(1));
      if (h.has('swing')) o.swing = +h.get('swing') || 0;
      if (h.has('err')) o.err = +h.get('err');
      if (h.has('caucus')) o.caucus = h.get('caucus');
      (h.get('calls') || '').split(',').filter(Boolean).forEach(x => {
        const [st, v] = x.split(':');
        if ($(`.lrow[data-st="${CSS.escape(st)}"]`) && (v === 'C' || v === 'R')) o.locks[st] = v;
      });
    } catch (e) { /* malformed hash: keep defaults */ }
  }
  function writeHash() {
    const calls = Object.entries(o.locks).map(([s, v]) => s + ':' + v).join(',');
    const h = new URLSearchParams();
    if (o.swing) h.set('swing', o.swing);
    if (o.err !== 1) h.set('err', o.err);
    if (o.caucus !== 'sep') h.set('caucus', o.caucus);
    if (calls) h.set('calls', calls);
    try { history.replaceState(null, '', h.toString() ? '#' + h.toString().replace(/%3A/g, ':').replace(/%2C/g, ',') : location.pathname); } catch (e) { }
  }

  function chart(res) {
    const W = 760, H = 220, L = 36, B = 34, T = 14;
    let k0 = 44, k1 = 58;
    res.hist.forEach((v, k) => { if (v >= 0.0005) { k0 = Math.min(k0, k); k1 = Math.max(k1, k); } });
    const bw = (W - L - 8) / (k1 - k0 + 1), ymax = Math.max(...res.hist.slice(k0, k1 + 1), 0.01);
    let out = '';
    [0.05, 0.1, 0.2, 0.4, 1].filter(f => f <= ymax).slice(-2).forEach(f => {
      const y = H - B - (H - B - T) * f / ymax;
      out += `<line class="grid" x1="${L}" x2="${W - 8}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}"></line><text x="${L - 4}" y="${(y + 4).toFixed(1)}" text-anchor="end">${Math.round(f * 100)}%</text>`;
    });
    for (let k = k0; k <= k1; k++) {
      const v = res.hist[k], h = (H - B - T) * v / ymax, x = L + (k - k0) * bw;
      const tip = `${k} seats · ${(v * 100).toFixed(1)}% of simulations · ${k >= 51 ? (o.caucus === 'sep' ? 'Democrats + independents hold 51+' : 'Democratic control') : k === 50 ? '50-50: VP Vance gives Republicans control' : 'Republican majority'}`;
      out += `<rect class="bar ${k >= 51 ? 'dem' : 'rep'}" x="${(x + 1).toFixed(1)}" y="${(H - B - h).toFixed(1)}" width="${(bw - 2).toFixed(1)}" height="${h.toFixed(1)}" rx="2"></rect>`
           + `<rect class="hit" x="${x.toFixed(1)}" y="${T}" width="${bw.toFixed(1)}" height="${H - B - T}" data-tip="${tip}"></rect>`;
      if (k % 2 === 0) out += `<text x="${(x + bw / 2).toFixed(1)}" y="${H - B + 16}" text-anchor="middle">${k}</text>`;
    }
    const x51 = L + (50.5 - k0) * bw;
    const xlab = o.caucus === 'R' ? 'Democratic seats (independents with Republicans)' : 'Democratic + independent seats';
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Seat distribution for your scenario">${out}
      <line class="axis" x1="${L}" x2="${W - 8}" y1="${H - B}" y2="${H - B}"></line>
      <line class="majority" x1="${x51.toFixed(1)}" x2="${x51.toFixed(1)}" y1="${T - 6}" y2="${H - B}"></line>
      <text class="lbl" x="${(x51 + 4).toFixed(1)}" y="${T + 4}">51 = Democratic control</text>
      <text x="${(W + L) / 2}" y="${H - 2}" text-anchor="middle">${xlab}</text></svg>`;
  }

  function render() {
    const res = simulate(SIM, o), ld = leaders(SIM, o);
    $('#sim-swing-out').textContent = swingTxt(o.swing);
    $('#sim-err-out').textContent = o.err === 0 ? 'None: leaders win' : '×' + o.err.toFixed(2).replace(/0$/, '');
    $('#sim-swing').value = o.swing; $('#sim-err').value = o.err;
    $$('#sim-caucus button').forEach(b => b.setAttribute('aria-pressed', b.dataset.v === o.caucus));
    $('#sim-pd').innerHTML = pct(res.D) + delta(res.D * 100, base.D * 100, 0, ' pts');
    $('#sim-pr').innerHTML = pct(res.R) + delta(res.R * 100, base.R * 100, 0, ' pts');
    $('#sim-pu').innerHTML = pct(res.U);
    $('#sim-pu-card').hidden = o.caucus !== 'sep';
    $('#sim-exp').innerHTML = res.med + delta(res.med, base.med, 0, '');  // median seats
    $('#sim-range').textContent = res.lo + '–' + res.hi;
    $('#sim-lead').textContent = `${ld.D}–${ld.R}` + (ld.I ? ` +${ld.I} I` : '');
    $('#sim-chart').innerHTML = chart(res);
    const nLocked = Object.keys(o.locks).length;
    $('#sim-status').textContent = (o.swing || o.err !== 1 || o.caucus !== 'sep' || nLocked)
      ? `Your scenario${nLocked ? ` · ${nLocked} race${nLocked > 1 ? 's' : ''} called by you` : ''}. Changes are shown against the model with no levers set.`
      : 'No levers set: this is the model forecast (re-simulated in your browser, so it can differ from the headline by about a point).';
    SIM.races.forEach((r, j) => {
      const row = $(`.lrow[data-st="${CSS.escape(r.st)}"]`), p = res.p[j];
      if (!row) return;  // only too-close-to-call races have a row
      row.querySelector('.pbar .ch').style.width = (p * 100).toFixed(1) + '%';
      row.querySelector('.pbar .rp').style.width = ((1 - p) * 100).toFixed(1) + '%';
      row.querySelector('.lp').textContent = p >= 0.5 ? `${r.ch} ${pct(p)}` : `${r.rp} ${pct(1 - p)}`;  // quote the leader
      row.classList.toggle('locked', !!o.locks[r.st]);
      row.querySelectorAll('.seg button').forEach(b => b.setAttribute('aria-pressed', (o.locks[r.st] || '') === b.dataset.v));
    });
    writeHash();
  }

  let pending = false;
  const schedule = () => { if (!pending) { pending = true; requestAnimationFrame(() => { pending = false; render(); }); } };
  $('#sim-swing').addEventListener('input', e => { o.swing = +e.target.value; schedule(); });
  $('#sim-err').addEventListener('input', e => { o.err = +e.target.value; schedule(); });
  $$('#sim-caucus button').forEach(b => b.addEventListener('click', () => { o.caucus = b.dataset.v; schedule(); }));
  $$('.lrow .seg button').forEach(b => b.addEventListener('click', () => {
    const st = b.closest('.lrow').dataset.st;
    if (b.dataset.v) o.locks[st] = b.dataset.v; else delete o.locks[st];
    schedule();
  }));
  $$('[data-preset]').forEach(b => b.addEventListener('click', () => { o.swing = +b.dataset.preset; schedule(); }));
  $('#sim-reset').addEventListener('click', () => { o = JSON.parse(JSON.stringify(DEFAULT)); schedule(); });
  const tip = document.getElementById('tip');
  $('#sim-chart').addEventListener('mousemove', e => {
    const el = e.target.closest('.hit');
    if (!el) { tip.style.display = 'none'; return; }
    tip.textContent = el.dataset.tip; tip.style.display = 'block';
    tip.style.left = Math.min(e.clientX + 12, innerWidth - tip.offsetWidth - 8) + 'px'; tip.style.top = (e.clientY - 30) + 'px';
  });
  $('#sim-chart').addEventListener('mouseleave', () => tip.style.display = 'none');
  readHash();
  render();
})();
