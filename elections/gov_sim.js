// In-page scenario simulator for governors.html. Inlined by build_governor.py; SIM is the data it injects.
// simulate() mirrors simulate() in governor_model.py: per simulation, one national, one regional and one per-race
// Student-t error. The levers add a uniform swing, scale every error and fix race outcomes.
// A fixed seed means the same draws are reused on every run, so a change in output comes from the lever, not noise.

function mulberry32(a) {
  return function () {
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// o: {swing, err, locks: {state: 'C'|'O'}}. C = the challenger (usually the Democrat) wins, O = the opponent wins.
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
  const wins = new Float64Array(nR), reg = new Float64Array(S.regions.length), hist = new Float64Array(51);
  let maj = 0, sum = 0;
  for (let s = 0; s < S.n; s++) {
    const nat = t() * S.national_sd * o.err + o.swing;
    for (let g = 0; g < reg.length; g++) reg[g] = t() * S.regional_sd * o.err;
    let d = S.hold.D;
    for (let j = 0; j < nR; j++) {
      const r = races[j];
      const drawn = r.mean + nat + reg[r.reg] + t() * r.sd * o.err > 0;  // draw even when locked, to keep draws aligned
      const win = lock[j] ? lock[j] === 'C' : drawn;
      if (win) wins[j]++;
      if ((win ? r.chp : r.opp) === 'D') d++;
    }
    if (d >= S.majority) maj++;
    hist[d]++; sum += d;
  }
  const n = S.n, pct = q => { let c = 0; for (let k = 0; k <= 50; k++) { c += hist[k]; if (c >= q * n) return k; } };
  return { D: maj / n, exp: sum / n, med: pct(0.5), lo: pct(0.1), hi: pct(0.9), hist: Array.from(hist, v => v / n), p: Array.from(wins, v => v / n) };
}

// Democratic governors if every race goes to whoever leads after the swing (no noise), with locks applied.
function leaders(S, o) {
  let d = S.hold.D;
  S.races.forEach(r => {
    const l = o.locks[r.st], win = l ? l === 'C' : r.mean + o.swing > 0;
    if ((win ? r.chp : r.opp) === 'D') d++;
  });
  return d;
}

if (typeof module !== 'undefined') module.exports = { simulate, leaders };

if (typeof document !== 'undefined') (function () {
  const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  const DEFAULT = { swing: 0, err: 1, locks: {} };
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
      (h.get('calls') || '').split(',').filter(Boolean).forEach(x => {
        const [st, v] = x.split(':');
        if ($(`.lrow[data-st="${CSS.escape(st)}"]`) && (v === 'C' || v === 'O')) o.locks[st] = v;
      });
    } catch (e) { /* malformed hash: keep defaults */ }
  }
  function writeHash() {
    const h = [];
    if (o.swing) h.push('swing=' + o.swing);
    if (o.err !== 1) h.push('err=' + o.err);
    const calls = Object.entries(o.locks).map(([s, v]) => encodeURIComponent(s) + ':' + v).join(',');
    if (calls) h.push('calls=' + calls);
    try { history.replaceState(null, '', h.length ? '#' + h.join('&') : location.pathname); } catch (e) { }
  }

  function chart(res) {
    const W = 760, H = 230, L = 36, B = 34, T = 24, M = SIM.majority;
    let k0 = M - 6, k1 = M + 6;
    res.hist.forEach((v, k) => { if (v >= 0.0005) { k0 = Math.min(k0, k); k1 = Math.max(k1, k); } });
    const bw = (W - L - 8) / (k1 - k0 + 1), ymax = Math.max(...res.hist.slice(k0, k1 + 1), 0.01);
    let out = '';
    [0.05, 0.1, 0.2, 0.4, 1].filter(f => f <= ymax).slice(-2).forEach(f => {
      const y = H - B - (H - B - T) * f / ymax;
      out += `<line class="grid" x1="${L}" x2="${W - 8}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}"></line><text x="${L - 4}" y="${(y + 4).toFixed(1)}" text-anchor="end">${Math.round(f * 100)}%</text>`;
    });
    for (let k = k0; k <= k1; k++) {
      const v = res.hist[k], h = (H - B - T) * v / ymax, x = L + (k - k0) * bw;
      const tip = `${k} D governors · ${(v * 100).toFixed(1)}% of simulations · ${k >= M ? 'Democratic majority' : k === 25 ? '25-25 split' : 'Republican majority'}`;
      out += `<rect class="bar ${k >= M ? 'dem' : 'rep'}" x="${(x + 1).toFixed(1)}" y="${(H - B - h).toFixed(1)}" width="${(bw - 2).toFixed(1)}" height="${h.toFixed(1)}" rx="2"></rect>`
           + `<rect class="hit" x="${x.toFixed(1)}" y="${T}" width="${bw.toFixed(1)}" height="${H - B - T}" data-tip="${tip}"></rect>`;
      if ((k1 - k0 > 24 ? k % 2 === 0 : true)) out += `<text x="${(x + bw / 2).toFixed(1)}" y="${H - B + 16}" text-anchor="middle">${k}</text>`;
    }
    const xm = L + (M - 0.5 - k0) * bw;
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Distribution of Democratic governors for your scenario">${out}
      <line class="axis" x1="${L}" x2="${W - 8}" y1="${H - B}" y2="${H - B}"></line>
      <line class="majority" x1="${xm.toFixed(1)}" x2="${xm.toFixed(1)}" y1="${T - 20}" y2="${H - B}"></line>
      <text class="lbl" x="${(xm + 4).toFixed(1)}" y="${T - 10}">26 = majority</text>
      <text x="${(W + L) / 2}" y="${H - 2}" text-anchor="middle">Democratic governors</text></svg>`;
  }

  function render() {
    const res = simulate(SIM, o), ld = leaders(SIM, o);
    $('#sim-swing-out').textContent = swingTxt(o.swing);
    $('#sim-err-out').textContent = o.err === 0 ? 'None: leaders win' : '×' + o.err;
    $('#sim-swing').value = o.swing; $('#sim-err').value = o.err;
    $('#sim-pd').innerHTML = pct(res.D) + delta(res.D * 100, base.D * 100, 0, ' pts');
    $('#sim-exp').innerHTML = res.med + delta(res.med, base.med, 0, '');  // median seats
    $('#sim-range').textContent = res.lo + '–' + res.hi;
    $('#sim-lead').textContent = `${ld}–${50 - ld}`;
    $('#sim-chart').innerHTML = chart(res);
    const nLocked = Object.keys(o.locks).length;
    $('#sim-status').textContent = (o.swing || o.err !== 1 || nLocked)
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
