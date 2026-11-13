<script>
  // Gráfico de UMA grandeza ao longo do tempo (sem dois eixos Y: para V e A juntos,
  // use dois gráficos lado a lado). Dados: histórico em memória desde que a página abriu.
  import { exponent, prefixed } from "../dmm.js";
  import { getHistory } from "../live.svelte.js";

  // q: {label, unit, line, decimals, si}; si = escala com prefixo (m, µ, k...) conforme os valores.
  // pick(data): o valor a desenhar de uma leitura (msg.data), ou undefined para interromper a linha.
  let { eqId, q, pick, windowS, msg } = $props();
  const M = { l: 58, r: 12, t: 10, b: 22 }; // margens do desenho

  let width = $state(0);
  let height = $state(0);
  let now = $state(Date.now());
  let hover = $state(null); // ponto sob o mouse

  // O eixo do tempo anda mesmo sem leituras novas (ex.: pausado)
  $effect(() => {
    const timer = setInterval(() => (now = Date.now()), 1000);
    return () => clearInterval(timer);
  });

  const plotW = $derived(Math.max(width - M.l - M.r, 10));
  const plotH = $derived(Math.max(height - M.t - M.b, 10));

  // Pontos dentro da janela: {t, v} ou null (interrupção da linha)
  const view = $derived.by(() => {
    msg; // dependência: recalcula a cada leitura nova
    const end = Math.max(now, (msg?.time ?? 0) * 1000);
    const start = end - windowS * 1000;
    const pts = [];
    for (const p of getHistory(eqId)) {
      if (p.t < start) continue;
      if (p.data === null) {
        if (pts.length && pts[pts.length - 1] !== null) pts.push(null);
        continue;
      }
      const v = pick(p.data);
      if (v === undefined || !Number.isFinite(v)) {
        if (pts.length && pts[pts.length - 1] !== null) pts.push(null);
      } else pts.push({ t: p.t, v });
    }
    let valid = pts.filter(Boolean);
    // Prefixo SI (ex.: mA, kΩ) escolhido pelo maior valor da janela
    const e = q.si ? exponent(Math.max(0, ...valid.map((p) => Math.abs(p.v))), q.unit) : 0;
    if (e) {
      for (let i = 0; i < pts.length; i++) if (pts[i]) pts[i] = { t: pts[i].t, v: pts[i].v / 10 ** e };
      valid = pts.filter(Boolean);
    }
    return { start, end, pts, valid, unit: q.si ? prefixed(e, q.unit) : q.unit };
  });

  // Escala Y com valores "redondos"
  function niceStep(range, count) {
    const raw = range / count;
    const mag = 10 ** Math.floor(Math.log10(raw));
    const n = raw / mag;
    return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * mag;
  }

  const yScale = $derived.by(() => {
    const vals = view.valid.map((p) => p.v);
    let lo = vals.length ? Math.min(...vals) : 0;
    let hi = vals.length ? Math.max(...vals) : 1;
    if (hi - lo < 1e-9) {
      const pad = q.si ? Math.max(Math.abs(hi) * 1e-4, 1e-6) : Math.max(Math.abs(hi) * 0.05, 5 * 10 ** -q.decimals);
      lo -= pad;
      hi += pad;
    }
    const step = niceStep(hi - lo, Math.max(2, Math.floor(plotH / 45)));
    lo = Math.floor(lo / step + 1e-9) * step;
    hi = Math.ceil(hi / step - 1e-9) * step;
    const ticks = [];
    for (let v = lo; v <= hi + step / 2; v += step) ticks.push(v);
    const decimals = Math.max(0, Math.min(6, -Math.floor(Math.log10(step) + 1e-9)));
    return { lo, hi, ticks, decimals };
  });

  const x = (t) => M.l + ((t - view.start) / (view.end - view.start)) * plotW;
  const y = (v) => M.t + (1 - (v - yScale.lo) / (yScale.hi - yScale.lo)) * plotH;

  // Muitos pontos por pixel: guarda só o mínimo e o máximo de cada coluna (mantém picos)
  function decimate(pts) {
    if (pts.length <= plotW * 2) return pts;
    const out = [];
    let col = null;
    let lo = null;
    let hi = null;
    const flush = () => {
      if (lo) out.push(...(lo === hi ? [lo] : lo.t < hi.t ? [lo, hi] : [hi, lo]));
      lo = hi = null;
    };
    for (const p of pts) {
      if (p === null) {
        flush();
        out.push(null);
        col = null;
        continue;
      }
      const c = Math.floor(x(p.t));
      if (c !== col) {
        flush();
        col = c;
      }
      if (!lo || p.v < lo.v) lo = p;
      if (!hi || p.v > hi.v) hi = p;
    }
    flush();
    return out;
  }

  const path = $derived.by(() => {
    let d = "";
    let pen = false;
    for (const p of decimate(view.pts)) {
      if (p === null) {
        pen = false;
        continue;
      }
      d += `${pen ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`;
      pen = true;
    }
    return d;
  });

  const xTicks = $derived.by(() => {
    const n = Math.max(2, Math.min(5, Math.floor(plotW / 110)));
    return Array.from({ length: n + 1 }, (_, i) => view.start + (i * (view.end - view.start)) / n);
  });

  const fmtTime = (t, seconds = true) =>
    new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: seconds ? "2-digit" : undefined });

  function onmove(e) {
    const pts = view.valid;
    if (!pts.length) return (hover = null);
    const rect = e.currentTarget.getBoundingClientRect();
    const t = view.start + ((e.clientX - rect.left - M.l) / plotW) * (view.end - view.start);
    // busca binária do ponto mais próximo no tempo
    let a = 0;
    let b = pts.length - 1;
    while (b - a > 1) {
      const m = (a + b) >> 1;
      if (pts[m].t < t) a = m;
      else b = m;
    }
    hover = Math.abs(pts[a].t - t) <= Math.abs(pts[b].t - t) ? pts[a] : pts[b];
  }

  const fmtValue = (v) => (q.si ? String(+v.toPrecision(7)) : v.toFixed(q.decimals));

  const last = $derived(view.valid[view.valid.length - 1]);
</script>

<div class="relative h-full w-full" bind:clientWidth={width} bind:clientHeight={height}>
  {#if width > 0 && height > 0}
    <svg
      {width}
      {height}
      class="block"
      role="img"
      aria-label="{q.label} ao longo do tempo"
      onpointermove={onmove}
      onpointerleave={() => (hover = null)}
    >
      <!-- grade e eixo Y (discretos) -->
      {#each yScale.ticks as v}
        <line x1={M.l} x2={M.l + plotW} y1={y(v)} y2={y(v)} stroke="#334155" stroke-opacity="0.6" stroke-width="1" />
        <text x={M.l - 6} y={y(v)} dy="0.32em" text-anchor="end" font-size="11" fill="#94a3b8" class="tabular-nums">
          {v.toFixed(yScale.decimals)}
        </text>
      {/each}
      <text x="4" y={M.t + 2} dy="0.7em" font-size="11" fill="#64748b">{view.unit}</text>

      <!-- eixo X (tempo) -->
      {#each xTicks as t, i}
        <text
          x={x(t)}
          y={height - 6}
          font-size="11"
          fill="#94a3b8"
          text-anchor={i === 0 ? "start" : i === xTicks.length - 1 ? "end" : "middle"}
        >
          {fmtTime(t, windowS < 900)}
        </text>
      {/each}

      <!-- a série -->
      <path d={path} fill="none" stroke={q.line} stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />

      <!-- leitura sob o mouse -->
      {#if hover}
        <line x1={x(hover.t)} x2={x(hover.t)} y1={M.t} y2={M.t + plotH} stroke="#94a3b8" stroke-dasharray="3 3" />
        <circle cx={x(hover.t)} cy={y(hover.v)} r="4" fill={q.line} stroke="#0f172a" stroke-width="2" />
      {/if}
    </svg>

    {#if hover}
      {@const left = x(hover.t)}
      <div
        class="pointer-events-none absolute top-2 rounded border border-slate-600 bg-slate-900/95 px-2 py-1 text-xs shadow"
        style={left > width / 2 ? `right: ${width - left + 8}px` : `left: ${left + 8}px`}
      >
        <div class="font-mono text-slate-100 tabular-nums">{fmtValue(hover.v)} {view.unit}</div>
        <div class="text-slate-400">{fmtTime(hover.t)}</div>
      </div>
    {:else if last}
      <div class="pointer-events-none absolute right-3 top-2 font-mono text-xs text-slate-300 tabular-nums">
        {fmtValue(last.v)} {view.unit}
      </div>
    {/if}

    {#if !view.valid.length}
      <div class="pointer-events-none absolute inset-0 flex items-center justify-center text-sm text-slate-500">
        aguardando leituras…
      </div>
    {/if}
  {/if}
</div>
