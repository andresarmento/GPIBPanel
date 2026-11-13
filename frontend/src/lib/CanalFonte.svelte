<script>
  // Um canal de fonte: leituras ao vivo + ajuste de faixa, tensão, corrente e saída.
  //
  // - Janela "ao vivo": layout largo (display ao lado dos ajustes).
  // - compact (widget "Fonte" dos painéis): display em cima, ajustes logo abaixo;
  //   números no tamanho escolhido (diminuem se não couberem) e opções avançadas
  //   (por enquanto só o tamanho do número) no ícone do canto inferior direito.
  import { api } from "./api.js";
  import OpcoesAvancadas from "./OpcoesAvancadas.svelte";
  import { FONT_DEFAULT } from "./painel/catalogo.js";
  import TamanhoFonte from "./TamanhoFonte.svelte";

  // spec: canal vindo do driver ({name, ranges}); reading: leitura ao vivo do canal (ou undefined)
  // fontSize: tamanho dos números em px (modo compacto); onfontsize(v): salva a escolha (widget)
  let {
    equipmentId,
    spec,
    reading,
    disabled = false,
    compact = false,
    fontSize = FONT_DEFAULT,
    onfontsize = null,
  } = $props();

  // Setas/rodinha dos campos de tensão e corrente mudam de 0,1 em 0,1 (primeira casa
  // decimal); valores mais finos são digitados.
  // Campos editáveis. Enquanto o usuário não mexe, acompanham o valor programado na fonte;
  // depois de editados ("pendentes"), ficam como estão até aplicar (Enter) ou desfazer (Esc).
  let form = $state({ range: "", voltage: null, current: null });
  let dirty = $state({ range: false, voltage: false, current: false });
  let busy = $state(false);
  let error = $state(null);

  const pending = $derived(dirty.range || dirty.voltage || dirty.current);
  const range = $derived(spec.ranges.find((r) => r.name === (dirty.range ? form.range : reading?.range)));

  $effect(() => {
    if (!reading) return;
    if (!dirty.range) form.range = reading.range;
    if (!dirty.voltage) form.voltage = reading.voltage_set;
    if (!dirty.current) form.current = reading.current_set;
  });

  async function send(body) {
    busy = true;
    error = null;
    try {
      await api(`/equipment/${equipmentId}/psu/${spec.name}`, { method: "POST", body });
      return true;
    } catch (e) {
      error = e.message;
      return false;
    } finally {
      busy = false;
    }
  }

  async function apply() {
    if (!pending) return;
    const body = {
      range: dirty.range ? form.range : null,
      voltage: dirty.voltage && form.voltage !== null ? Number(form.voltage) : null,
      current: dirty.current && form.current !== null ? Number(form.current) : null,
    };
    // O estado novo chega pelo WebSocket logo em seguida
    if (await send(body)) dirty = { range: false, voltage: false, current: false };
  }

  function revert() {
    dirty = { range: false, voltage: false, current: false };
    error = null;
  }

  function onkeydown(e) {
    if (e.key === "Enter") apply();
    if (e.key === "Escape") revert();
  }

  const fmt = (x, d) => (x === undefined || x === null ? "—" : Number(x).toFixed(d));
  const field = (isDirty) =>
    `${compact ? "w-24" : "w-28"} rounded bg-slate-800 px-2 py-1 text-right font-mono outline-none ${isDirty ? "ring-1 ring-amber-400" : ""}`;

  const vText = $derived(fmt(reading?.voltage, 3));
  const aText = $derived(fmt(reading?.current, 4));
  // Potência entregue (V × A medidos), mostrada na linha da corrente no widget
  const pText = $derived(reading ? fmt(reading.voltage * reading.current, 3) : "—");

  // --- modo compacto: tamanho dos números -------------------------------------
  // O tamanho escolhido não muda ao redimensionar o widget; se não couber no espaço
  // que sobra depois dos ajustes, diminui só o necessário. Display e ajustes ficam
  // juntos no alto; a sobra vai para baixo.
  let dragSize = $state(null); // valor enquanto o controle deslizante está sendo arrastado
  const size = $derived(dragSize ?? fontSize);
  let rootH = $state(0);
  let rootW = $state(0);
  let controlsH = $state(0);
  const FIXED_PX = 32 + 16; // cabeçalho + linha "programado" + margens do fundo preto
  const GAP_PX = 8;
  const fontPx = $derived.by(() => {
    if (!rootH || !rootW) return size;
    const byHeight = (rootH - controlsH - GAP_PX - FIXED_PX) / 2.1; // duas linhas (V e A)
    // largura em "caracteres": a linha da corrente também leva a potência (mesmo tamanho)
    const chars = Math.max(vText.length + 0.5, aText.length + 0.5 + 1 + pText.length + 0.5);
    const byWidth = ((rootW - 16) * 1.65) / (chars + 2);
    return Math.max(12, Math.min(size, byHeight, byWidth));
  });
</script>

{#snippet outputBadge()}
  <span
    class="shrink-0 rounded px-1.5 py-0.5 {reading?.output ? 'bg-green-700 text-green-100' : 'bg-slate-700 text-slate-400'}"
  >
    {reading ? (reading.output ? "SAÍDA LIGADA" : "saída desligada") : "—"}
  </span>
{/snippet}

{#snippet programmed()}
  programado {fmt(reading?.voltage_set, 3)} V / {fmt(reading?.current_set, 4)} A · faixa {reading?.range ?? "—"}
{/snippet}

{#snippet adjustments()}
  <label class="flex items-center gap-2 {compact ? '' : 'justify-between gap-3'}">
    faixa
    <select
      class="{compact ? 'w-32' : 'w-40'} rounded bg-slate-800 px-2 py-1 outline-none {dirty.range
        ? 'ring-1 ring-amber-400'
        : ''}"
      bind:value={form.range}
      onchange={() => (dirty.range = form.range !== reading?.range)}
      {onkeydown}
      {disabled}
    >
      {#each spec.ranges as r}
        <option value={r.name}>{compact ? r.label || r.name : `${r.name} (${r.label})`}</option>
      {/each}
    </select>
  </label>
  <label class="flex items-center gap-2 {compact ? '' : 'justify-between gap-3'}">
    {compact ? "V" : "tensão (V)"}
    <input
      class={field(dirty.voltage)}
      type="number"
      step="0.1"
      min="0"
      max={range?.max_voltage}
      bind:value={form.voltage}
      oninput={() => (dirty.voltage = true)}
      {onkeydown}
      {disabled}
    />
  </label>
  <label class="flex items-center gap-2 {compact ? '' : 'justify-between gap-3'}">
    {compact ? "A" : "corrente (A)"}
    <input
      class={field(dirty.current)}
      type="number"
      step="0.1"
      min="0"
      max={range?.max_current}
      bind:value={form.current}
      oninput={() => (dirty.current = true)}
      {onkeydown}
      {disabled}
    />
  </label>
{/snippet}

{#snippet buttons()}
  <button
    class="rounded bg-sky-700 px-3 py-1 hover:bg-sky-600 disabled:opacity-40"
    onclick={apply}
    disabled={disabled || busy || !pending}
    title="Enter aplica · Esc desfaz"
  >
    aplicar
  </button>
  {#if pending}
    <button class="text-slate-400 hover:text-slate-200" onclick={revert}>desfazer</button>
  {/if}
  <button
    class="{compact ? '' : 'ml-auto'} rounded px-3 py-1 font-semibold disabled:opacity-40 {reading?.output
      ? 'bg-red-700 hover:bg-red-600'
      : 'bg-green-700 hover:bg-green-600'}"
    onclick={() => send({ output: !reading.output })}
    disabled={disabled || busy || !reading}
  >
    {reading?.output ? "desligar" : "ligar"}
  </button>
{/snippet}

{#if compact}
  <div bind:clientHeight={rootH} bind:clientWidth={rootW} class="flex h-full flex-col gap-2 text-sm">
    <!-- display: o fundo preto abraça os números -->
    <div class="shrink-0 rounded bg-black/50 px-2 py-1.5 font-mono">
      <div class="flex items-center justify-between gap-2 text-xs text-slate-400">
        <span class="truncate">{spec.name}</span>
        {@render outputBadge()}
      </div>
      <div class="mt-0.5 whitespace-nowrap leading-none tabular-nums" style="font-size: {fontPx}px;">
        <div class="text-green-300">{vText}<span class="ml-[0.2em] text-[0.5em]">V</span></div>
        <div class="mt-[0.1em] flex items-baseline justify-between gap-[0.5em]">
          <span class="text-amber-300">{aText}<span class="ml-[0.2em] text-[0.5em]">A</span></span>
          <span class="text-sky-300" title="Potência (tensão × corrente medidas)"
            >{pText}<span class="ml-[0.2em] text-[0.5em]">W</span></span
          >
        </div>
      </div>
      <div class="mt-1 truncate text-xs text-slate-500">{@render programmed()}</div>
    </div>

    <!-- ajustes, logo abaixo do display -->
    <div bind:clientHeight={controlsH} class="relative flex shrink-0 flex-col gap-1.5 pr-9">
      <div class="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        {@render adjustments()}
      </div>
      <div class="flex flex-wrap items-center gap-2">
        {@render buttons()}
      </div>
      {#if error}
        <p class="text-red-400">✗ {error}</p>
      {/if}
      {#if onfontsize}
        <OpcoesAvancadas title="Opções avançadas (tamanho do número)">
          <TamanhoFonte
            value={size}
            oninput={(v) => (dragSize = v)}
            onchange={(v) => {
              onfontsize(v);
              dragSize = null;
            }}
          />
        </OpcoesAvancadas>
      {/if}
    </div>
  </div>
{:else}
  <div class="flex flex-wrap gap-4">
    <!-- display -->
    <div class="min-w-56 flex-1 rounded bg-black/50 p-3 font-mono">
      <div class="flex items-center justify-between text-xs text-slate-400">
        <span>{spec.name}</span>
        {@render outputBadge()}
      </div>
      <div class="mt-1 text-4xl text-green-300 tabular-nums">{vText} <span class="text-xl">V</span></div>
      <div class="text-4xl text-amber-300 tabular-nums">{aText} <span class="text-xl">A</span></div>
      <div class="mt-1 text-xs text-slate-500">{@render programmed()}</div>
    </div>

    <!-- ajustes -->
    <div class="flex flex-col gap-2 text-sm">
      {@render adjustments()}
      <div class="flex flex-wrap gap-2">
        {@render buttons()}
      </div>
      {#if error}
        <p class="max-w-72 text-red-400">✗ {error}</p>
      {/if}
    </div>
  </div>
{/if}
