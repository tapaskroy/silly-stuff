// In-page scenario simulator for house.html. Inlined by build_house.py; SIM is the data it injects.
// Mirrors simulate() in house_model.py: per simulation, one national, one regional and one per-district Student-t
// error. The unit draws are generated once with a fixed seed and reused on every run, so a change in output comes
// from the lever, not from noise, and a re-run over 400+ districts is only additions and comparisons.

function mulberry32(a) {
  return function () {
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function draws(S) {
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
  const n = S.n, G = S.regions.length, L = S.races.length;
  const nat = new Float32Array(n), reg = new Float32Array(n * G), loc = new Float32Array(n * L);
  for (let i = 0; i < n; i++) nat[i] = t();
  for (let i = 0; i < n * G; i++) reg[i] = t();
  for (let i = 0; i < n * L; i++) loc[i] = t();
  return { nat, reg, loc };
}

// o: {swing, err, reg: [per-region extra swing], locks: {district: 'D'|'R'}}
function simulate(S, Z, o) {
  const n = S.n, G = S.regions.length, R = S.races, L = R.length;
  const mean = Float64Array.from(R, r => r.mean), sd = Float64Array.from(R, r => r.sd * o.err);
  const ri = Int8Array.from(R, r => r.reg), isD = Uint8Array.from(R, r => r.chp === 'D');
  const lock = Int8Array.from(R, r => o.locks[r.d] === 'D' ? 1 : o.locks[r.d] === 'R' ? -1 : 0);
  const wins = new Float64Array(L), hist = new Float64Array(436), rv = new Float64Array(G);
  let maj = 0, sum = 0;
  for (let s = 0; s < n; s++) {
    const nat = o.swing + o.err * Z.nat[s] * S.national_sd;
    for (let g = 0; g < G; g++) rv[g] = nat + o.reg[g] + o.err * Z.reg[s * G + g] * S.regional_sd;
    let d = S.fixed_d;
    const off = s * L;
    for (let j = 0; j < L; j++) {
      const win = lock[j] ? lock[j] > 0 : mean[j] + rv[ri[j]] + Z.loc[off + j] * sd[j] > 0;
      if (win) { wins[j]++; d += isD[j]; }
    }
    if (d >= S.majority) maj++;
    hist[d]++; sum += d;
  }
  const pct = q => { let c = 0; for (let k = 0; k < 436; k++) { c += hist[k]; if (c >= q * n) return k; } };
  return { D: maj / n, exp: sum / n, med: pct(0.5), lo: pct(0.1), hi: pct(0.9), hist: Array.from(hist, v => v / n), p: Array.from(wins, v => v / n) };
}

// Democratic seats if every district goes to whoever leads after the swings (no noise), with locks applied.
function leaders(S, o) {
  let d = S.fixed_d;
  S.races.forEach(r => {
    const l = o.locks[r.d], win = l ? l === 'D' : r.mean + o.swing + o.reg[r.reg] > 0;
    if (win && r.chp === 'D') d++;
  });
  return d;
}

if (typeof module !== 'undefined') module.exports = { draws, simulate, leaders };

if (typeof document !== 'undefined') (function () {
  const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  const G = SIM.regions.length;
  const fresh = () => ({ swing: 0, err: 1, reg: new Array(G).fill(0), locks: {} });
  let o = fresh();
  const Z = draws(SIM);
  const base = simulate(SIM, Z, fresh());
  const idx = Object.fromEntries(SIM.races.map((r, j) => [r.d, j]));
  const pct = p => p >= 0.995 ? '>99%' : p <= 0.005 ? '<1%' : Math.round(p * 100) + '%';
  const swingTxt = v => v === 0 ? 'None' : (v > 0 ? 'D+' : 'R+') + Math.abs(v);
  // Change vs. the no-lever run, hidden when it rounds to zero at the shown precision.
  const delta = (v, b, digits, unit) => {
    const d = +(v - b).toFixed(digits);
    return d === 0 ? '' : `<em class="${d > 0 ? 'up' : 'dn'}">${d > 0 ? '+' : '−'}${Math.abs(d).toFixed(digits)}${unit}</em>`;
  };
  const stateExp = (st, p) => SIM.fixed_by_state[st] + SIM.races.reduce((a, r, j) => a + (r.st === st && r.chp === 'D' ? p[j] : 0), 0);

  function readHash() {
    try {
      const h = new URLSearchParams(location.hash.slice(1));
      if (h.has('swing')) o.swing = +h.get('swing') || 0;
      if (h.has('err')) o.err = +h.get('err');
      if (h.has('reg')) h.get('reg').split(',').forEach((v, g) => { if (g < G) o.reg[g] = +v || 0; });
      (h.get('calls') || '').split(',').filter(Boolean).forEach(x => {
        const [d, v] = x.split(':');
        if ($(`.lrow[data-d="${CSS.escape(d)}"]`) && (v === 'D' || v === 'R')) o.locks[d] = v;
      });
    } catch (e) { /* malformed hash: keep defaults */ }
  }
  function writeHash() {
    const h = [];
    if (o.swing) h.push('swing=' + o.swing);
    if (o.err !== 1) h.push('err=' + o.err);
    if (o.reg.some(v => v)) h.push('reg=' + o.reg.join(','));
    const calls = Object.entries(o.locks).map(([d, v]) => d + ':' + v).join(',');
    if (calls) h.push('calls=' + calls);
    try { history.replaceState(null, '', h.length ? '#' + h.join('&') : location.pathname); } catch (e) { }
  }

  function chart(res) {
    const W = 760, H = 230, L = 36, B = 34, T = 24, M = SIM.majority;
    let s0 = M - 15, s1 = M + 15;
    res.hist.forEach((v, k) => { if (v >= 0.0005) { s0 = Math.min(s0, k); s1 = Math.max(s1, k); } });
    // Bins of 3 aligned so one bin starts at 218: no bar mixes the two majorities.
    const bins = [];
    for (let k = s0 - (((s0 - M) % 3) + 3) % 3; k <= s1; k += 3) bins.push(k);
    const vals = bins.map(a => res.hist[a] + (res.hist[a + 1] || 0) + (res.hist[a + 2] || 0));
    const bw = (W - L - 8) / bins.length, ymax = Math.max(...vals, 0.01);
    let out = '';
    [0.05, 0.1, 0.2, 0.4, 1].filter(f => f <= ymax).slice(-2).forEach(f => {
      const y = H - B - (H - B - T) * f / ymax;
      out += `<line class="grid" x1="${L}" x2="${W - 8}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}"></line><text x="${L - 4}" y="${(y + 4).toFixed(1)}" text-anchor="end">${Math.round(f * 100)}%</text>`;
    });
    bins.forEach((a, i) => {
      const v = vals[i], h = (H - B - T) * v / ymax, x = L + i * bw, side = a >= M ? 'dem' : 'rep';
      const tip = `${a}–${a + 2} D seats · ${(v * 100).toFixed(1)}% of simulations · ${a >= M ? 'Democratic' : 'Republican'} majority`;
      out += `<rect class="bar ${side}" x="${(x + 1).toFixed(1)}" y="${(H - B - h).toFixed(1)}" width="${Math.max(bw - 2, 1).toFixed(1)}" height="${h.toFixed(1)}" rx="2"></rect>`
           + `<rect class="hit" x="${x.toFixed(1)}" y="${T}" width="${bw.toFixed(1)}" height="${H - B - T}" data-tip="${tip}"></rect>`;
      if (i % Math.ceil(bins.length / 12) === 0) out += `<text x="${(x + bw / 2).toFixed(1)}" y="${H - B + 16}" text-anchor="middle">${a}</text>`;
    });
    const xm = L + bins.indexOf(M) * bw;
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Seat distribution for your scenario">${out}
      <line class="axis" x1="${L}" x2="${W - 8}" y1="${H - B}" y2="${H - B}"></line>
      <line class="majority" x1="${xm.toFixed(1)}" x2="${xm.toFixed(1)}" y1="${T - 20}" y2="${H - B}"></line>
      <text class="lbl" x="${(xm + 4).toFixed(1)}" y="${T - 10}">218 = majority</text>
      <text x="${(W + L) / 2}" y="${H - 2}" text-anchor="middle">Democratic seats (bins of 3)</text></svg>`;
  }

  function render() {
    const res = simulate(SIM, Z, o), ld = leaders(SIM, o);
    $('#sim-swing-out').textContent = swingTxt(o.swing);
    $('#sim-err-out').textContent = o.err === 0 ? 'None: leaders win' : '×' + o.err;
    $('#sim-swing').value = o.swing; $('#sim-err').value = o.err;
    $$('.sim-reg').forEach(el => { const g = +el.dataset.g; el.value = o.reg[g]; el.parentElement.querySelector('output').textContent = swingTxt(o.reg[g]); });
    $('#sim-pd').innerHTML = pct(res.D) + delta(res.D * 100, base.D * 100, 0, ' pts');
    $('#sim-pr').innerHTML = pct(1 - res.D) + delta((1 - res.D) * 100, (1 - base.D) * 100, 0, ' pts');
    $('#sim-exp').innerHTML = res.med + delta(res.med, base.med, 0, '');  // median seats
    $('#sim-range').textContent = res.lo + '–' + res.hi;
    $('#sim-lead').textContent = `${ld}–${435 - ld}`;
    $('#sim-chart').innerHTML = chart(res);
    const nLocked = Object.keys(o.locks).length, regSet = o.reg.some(v => v);
    $('#sim-status').textContent = (o.swing || o.err !== 1 || regSet || nLocked)
      ? `Your scenario${nLocked ? ` · ${nLocked} district${nLocked > 1 ? 's' : ''} called by you` : ''}. Changes are shown against the model with no levers set.`
      : 'No levers set: this is the model forecast (re-simulated in your browser, so it can differ from the headline by about a point).';
    $$('.lrow').forEach(row => {
      const d = row.dataset.d, p = res.p[idx[d]];
      row.querySelector('.pbar .ch').style.width = (p * 100).toFixed(1) + '%';
      row.querySelector('.pbar .rp').style.width = ((1 - p) * 100).toFixed(1) + '%';
      row.querySelector('.lp').textContent = p >= 0.5 ? 'D ' + pct(p) : 'R ' + pct(1 - p);  // quote the leader
      row.classList.toggle('locked', !!o.locks[d]);
      row.querySelectorAll('.seg button').forEach(b => b.setAttribute('aria-pressed', (o.locks[d] || '') === b.dataset.v));
    });
    $$('.sblock').forEach(blk => {
      const st = blk.dataset.st, ds = [...blk.querySelectorAll('.lrow')].map(r => r.dataset.d);
      const calls = ds.map(d => o.locks[d] || '');
      const all = calls.every(c => c === calls[0]) ? calls[0] : null;  // null = mixed
      blk.querySelectorAll('.sseg button').forEach(b => b.setAttribute('aria-pressed', all === b.dataset.v));
      const e = stateExp(st, res.p), e0 = stateExp(st, base.p);
      blk.querySelector('.sexp').innerHTML = `expected D seats ${Math.floor(e)}${delta(Math.floor(e), Math.floor(e0), 0, '')} of ${SIM.seats_by_state[st]}`;
      const nl = calls.filter(Boolean).length;
      blk.querySelector('.scalled').textContent = nl ? `· ${nl} called` : '';
    });
    writeHash();
  }

  let pending = false;
  const schedule = () => { if (!pending) { pending = true; requestAnimationFrame(() => { pending = false; render(); }); } };
  $('#sim-swing').addEventListener('input', e => { o.swing = +e.target.value; schedule(); });
  $('#sim-err').addEventListener('input', e => { o.err = +e.target.value; schedule(); });
  $$('.sim-reg').forEach(el => el.addEventListener('input', () => { o.reg[+el.dataset.g] = +el.value; schedule(); }));
  $$('[data-preset]').forEach(b => b.addEventListener('click', () => { o.swing = +b.dataset.preset; schedule(); }));
  $$('.lrow .seg button').forEach(b => b.addEventListener('click', () => {
    const d = b.closest('.lrow').dataset.d;
    if (b.dataset.v) o.locks[d] = b.dataset.v; else delete o.locks[d];
    schedule();
  }));
  $$('.sseg button').forEach(b => b.addEventListener('click', e => {
    e.preventDefault();  // the buttons sit in a <summary>; don't toggle the block
    b.closest('.sblock').querySelectorAll('.lrow').forEach(row => {
      if (b.dataset.v) o.locks[row.dataset.d] = b.dataset.v; else delete o.locks[row.dataset.d];
    });
    schedule();
  }));
  $('#sim-reset').addEventListener('click', () => { o = fresh(); schedule(); });
  $('#sim-expand').addEventListener('click', () => {
    const open = !$$('.sblock').every(b => b.open);
    $$('.sblock').forEach(b => b.open = open);
  });
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
