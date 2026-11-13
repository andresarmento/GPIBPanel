<script>
  // Um canal de gerador de funções: estado ao vivo + forma de onda, frequência,
  // amplitude (Vpp), offset, ciclo de trabalho e carga.
  //
  // - Forma de onda, carga e ciclo de trabalho são enviados na hora.
  // - Frequência, amplitude e offset ficam "pendentes" (contorno amarelo) até
  //   aplicar (Enter) ou desfazer (Esc), como na fonte.
  // - Janela "ao vivo": tudo à mostra. compact (widget "Gerador" dos painéis):
  //   número no tamanho escolhido (diminui se não couber) e carga, ciclo de
  //   trabalho e tamanho do número no ícone de opções avançadas.
  import { api } from "./api.js";
  import { formatSI } from "./dmm.js";
  import OpcoesAvancadas from "./OpcoesAvancadas.svelte";
  import { FONT_DEFAULT } from "./painel/catalogo.js";
  import TamanhoFonte from "./TamanhoFonte.svelte";

  // driver: descrição do driver ({waveforms, limits, has_output_switch, duty_min/max})
  // channel: nome do canal; reading: estado ao vivo do canal (ou undefined)
  let {
    equipmentId,
    driver,
    channel,
    reading,
    disabled = false,
    compact = false,
    fontSize = FONT_DEFAULT,
    onfontsize = null,
  } = $props();

  // Rótulos curtos dos botões (os nomes das formas são comuns a todos os geradores)
  const SHORT = { SIN: "Seno", SQU: "Quad", TRI: "Tri", RAMP: "Rampa", NOISE: "Ruído", DC: "DC" };
  const FREQ_UNITS = [
    ["Hz", 1],
    ["kHz", 1e3],
    ["MHz", 1e6],
  ];

  let busy = $state(false);
  let error = $state(null);

  const wf = $derived(driver.waveforms.find((w) => w.name === reading?.waveform));
  const lim = $derived(driver.limits[reading?.load ?? "50"]);

  // --- campos pendentes (frequência, amplitude, offset) ----------------------
  let form = $state({ frequency: null, freqUnit: 1e3, amplitude: null, offset: null });
  let dirty = $state({ frequency: false, amplitude: false, offset: false });
  const pending = $derived(dirty.frequency || dirty.amplitude || dirty.offset);

  // Unidade da frequência que deixa o número "redondo" (ex.: 2500 Hz → 2.5 kHz)
  const autoUnit = (hz) => (hz >= 1e6 ? 1e6 : hz >= 1e3 ? 1e3 : 1);
  const clean = (x) => +Number(x).toPrecision(10);

  $effect(() => {
    if (!reading) return;
    if (!dirty.frequency && reading.frequency != null) {
      form.freqUnit = autoUnit(reading.frequency);
      form.frequency = clean(reading.frequency / form.freqUnit);
    }
    if (!dirty.amplitude) form.amplitude = reading.amplitude;
    if (!dirty.offset) form.offset = reading.offset;
  });

  async function send(body) {
    busy = true;
    error = null;
    try {
      // O estado novo chega pelo WebSocket logo em seguida
      await api(`/equipment/${equipmentId}/fgen/${channel}`, { method: "POST", body });
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
    const num = (ok, v) => (ok && v !== null && v !== "" ? Number(v) : null);
    const body = {
      frequency: dirty.frequency && form.frequency !== null ? clean(Number(form.frequency) * form.freqUnit) : null,
      amplitude: num(dirty.amplitude, form.amplitude),
      offset: num(dirty.offset, form.offset),
    };
    if (await send(body)) revert();
  }

  function revert() {
    dirty = { frequency: false, amplitude: false, offset: false };
    error = null;
  }

  function onkeydown(e) {
    if (e.key === "Enter") apply();
    if (e.key === "Escape") revert();
  }

  const fmt = (x, d) => (x === undefined || x === null ? "—" : Number(x).toFixed(d));
  const field = (isDirty) =>
    `${compact ? "w-24" : "w-28"} rounded bg-slate-800 px-2 py-1 text-right font-mono outline-none ${isDirty ? "ring-1 ring-amber-400" : ""}`;
  const off = $derived(disabled || busy || !reading);

  // --- display ----------------------------------------------------------------
  // Número principal: frequência; em DC, o nível (offset); no ruído, a amplitude.
  const main = $derived.by(() => {
    if (!reading) return { text: "—", unit: "", color: "text-sky-300" };
    if (reading.waveform === "DC") {
      return { text: (reading.offset >= 0 ? "+" : "") + fmt(reading.offset, 4), unit: "V", color: "text-amber-300" };
    }
    if (reading.frequency == null) return { text: fmt(reading.amplitude, 4), unit: "Vpp", color: "text-green-300" };
    return { ...formatSI(reading.frequency, "Hz"), color: "text-sky-300" };
  });
  // Linha de baixo: amplitude e offset (quando o número principal é a frequência)
  const showSecond = $derived(reading && reading.waveform !== "DC" && reading.frequency != null);
  const ampText = $derived(fmt(reading?.amplitude, 4));
  const offText = $derived(reading ? (reading.offset >= 0 ? "+" : "") + fmt(reading.offset, 4) : "—");
  const loadText = $derived(reading ? (reading.load === "50" ? "50 Ω" : "alta Z") : "—");

  // --- modo compacto: tamanho do número ----------------------------------------
  let dragSize = $state(null);
  const size = $derived(dragSize ?? fontSize);
  let rootH = $state(0);
  let rootW = $state(0);
  let controlsH = $state(0);
  const FIXED_PX = 32; // cabeçalho + margens do fundo preto
  const GAP_PX = 8;
  const SECOND = 0.6; // a linha de amplitude/offset tem 60% do tamanho do número principal
  const fontPx = $derived.by(() => {
    if (!rootH || !rootW) return size;
    const lines = showSecond ? 1 + SECOND * 1.15 : 1;
    const byHeight = (rootH - controlsH - GAP_PX - FIXED_PX) / (lines * 1.05);
    const mainChars = main.text.length + main.unit.length / 2 + 1;
    const secondChars = showSecond ? (ampText.length + offText.length + 6) * SECOND : 0;
    const byWidth = ((rootW - 16) * 1.65) / (Math.max(mainChars, secondChars) + 1);
    return Math.max(12, Math.min(size, byHeight, byWidth));
  });
</script>

{#snippet header()}
  <div class="flex items-center justify-between gap-2 text-xs text-slate-400">
    <span class="truncate">
      {channel} · {wf?.label ?? reading?.waveform ?? "—"}{reading?.duty != null ? ` · ciclo ${fmt(reading.duty, 1)}%` : ""}
    </span>
    <span class="shrink-0 rounded bg-slate-700 px-1.5 text-slate-300" title="Carga esperada na saída">{loadText}</span>
  </div>
{/snippet}

{#snippet advanced()}
  <label class="flex items-center justify-between gap-3" title="A carga não muda o sinal: muda a escala dos valores e os limites">
    carga
    <select
      class="w-36 rounded bg-slate-800 px-2 py-1"
      value={reading?.load ?? ""}
      onchange={(e) => send({ load: e.currentTarget.value })}
      disabled={off}
    >
      <option value="50">50 Ω</option>
      <option value="HIGHZ">alta impedância</option>
    </select>
  </label>
  <label class="flex items-center justify-between gap-3">
    ciclo de trabalho (%)
    <input
      class="w-36 rounded bg-slate-800 px-2 py-1 text-right font-mono"
      type="number"
      step="1"
      min={driver.duty_min}
      max={driver.duty_max}
      value={reading?.duty ?? ""}
      placeholder={wf?.duty ? "" : "só quadrada"}
      onchange={(e) => send({ duty: Number(e.currentTarget.value) })}
      disabled={off || !wf?.duty}
    />
  </label>
{/snippet}

{#snippet waveIcon(name)}
  <!-- desenho da forma de onda (24×14) -->
  <svg viewBox="0 0 24 14" class="h-3.5 w-6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round">
    {#if name === "SIN"}
      <path d="M1 7 Q6.5 -4 12 7 T23 7" />
    {:else if name === "SQU"}
      <path d="M1 11 H6 V3 H12 V11 H18 V3 H23" />
    {:else if name === "TRI"}
      <path d="M1 11 L6.5 3 L12 11 L17.5 3 L23 11" />
    {:else if name === "RAMP"}
      <path d="M1 11 L11 3 V11 L21 3 V11" />
    {:else if name === "NOISE"}
      <path d="M1 7 L3 3 L4 10 L6 5 L7 12 L9 2 L11 9 L12 6 L14 11 L15 4 L17 8 L18 3 L20 10 L21 6 L23 7" stroke-width="1.2" />
    {:else if name === "DC"}
      <path d="M1 4 H23" />
      <path d="M1 11 H23" stroke-dasharray="2 2" stroke-width="1" opacity="0.5" />
    {:else}
      <text x="12" y="11" font-size="9" text-anchor="middle" fill="currentColor" stroke="none">{name}</text>
    {/if}
  </svg>
{/snippet}

{#snippet waveformButtons()}
  <div class="flex flex-wrap gap-1">
    {#each driver.waveforms as w (w.name)}
      <button
        class="rounded px-1.5 py-1.5 {w.name === reading?.waveform
          ? 'bg-sky-700 text-white'
          : 'bg-slate-800 text-slate-300 hover:bg-slate-700'} disabled:opacity-40"
        title={w.label}
        aria-label={w.label}
        onclick={() => send({ waveform: w.name })}
        disabled={off}
      >
        {@render waveIcon(w.name)}
      </button>
    {/each}
  </div>
{/snippet}

{#snippet frequencyField()}
  {#if wf?.max_frequency != null || (!wf && reading?.frequency != null)}
    <label class="flex items-center gap-2">
      {compact ? "Freq" : "frequência"}
      <span class="flex items-center gap-1">
        <input
          class={field(dirty.frequency)}
          type="number"
          step="0.1"
          min="0"
          bind:value={form.frequency}
          oninput={() => (dirty.frequency = true)}
          {onkeydown}
          disabled={off}
        />
        <select
          class="rounded bg-slate-800 px-1 py-1 outline-none {dirty.frequency ? 'ring-1 ring-amber-400' : ''}"
          bind:value={form.freqUnit}
          onchange={() => (dirty.frequency = true)}
          {onkeydown}
          disabled={off}
        >
          {#each FREQ_UNITS as [label, factor]}
            <option value={factor}>{label}</option>
          {/each}
        </select>
      </span>
    </label>
  {/if}
{/snippet}

{#snippet levelFields()}
  {#if wf?.amplitude !== false}
    <label class="flex items-center gap-2">
      {compact ? "Vpp" : "amplitude (Vpp)"}
      <input
        class={field(dirty.amplitude)}
        type="number"
        step="0.1"
        min={lim?.amplitude_min}
        max={lim?.amplitude_max}
        bind:value={form.amplitude}
        oninput={() => (dirty.amplitude = true)}
        {onkeydown}
        disabled={off}
      />
    </label>
  {/if}
  <label class="flex items-center gap-2">
    {reading?.waveform === "DC" ? (compact ? "V" : "nível DC (V)") : compact ? "offset" : "offset (V)"}
    <input
      class={field(dirty.offset)}
      type="number"
      step="0.1"
      min={-(lim?.offset_max ?? 0)}
      max={lim?.offset_max}
      bind:value={form.offset}
      oninput={() => (dirty.offset = true)}
      {onkeydown}
      disabled={off}
    />
  </label>
{/snippet}

{#snippet buttons()}
  <button
    class="rounded bg-sky-700 px-3 py-1 hover:bg-sky-600 disabled:opacity-40"
    onclick={apply}
    disabled={off || !pending}
    title="Enter aplica · Esc desfaz"
  >
    aplicar
  </button>
  {#if pending}
    <button class="text-slate-400 hover:text-slate-200" onclick={revert}>desfazer</button>
  {/if}
  {#if driver.has_output_switch}
    <button
      class="rounded px-3 py-1 font-semibold disabled:opacity-40 {reading?.output
        ? 'bg-red-700 hover:bg-red-600'
        : 'bg-green-700 hover:bg-green-600'}"
      onclick={() => send({ output: !reading.output })}
      disabled={off}
    >
      {reading?.output ? "desligar" : "ligar"}
    </button>
  {/if}
{/snippet}

{#snippet controls()}
  <!-- 1ª linha: frequência e formas de onda; 2ª linha: amplitude, offset e aplicar -->
  <div class="flex flex-wrap items-center gap-x-3 gap-y-1.5">
    {@render frequencyField()}
    {@render waveformButtons()}
  </div>
  <div class="flex flex-wrap items-center gap-x-3 gap-y-1.5">
    {@render levelFields()}
    <div class="flex items-center gap-2">
      {@render buttons()}
    </div>
  </div>
  {#if error}
    <p class="text-red-400">✗ {error}</p>
  {/if}
{/snippet}

{#if compact}
  <div bind:clientHeight={rootH} bind:clientWidth={rootW} class="flex h-full flex-col gap-2 text-sm">
    <!-- display: o fundo preto abraça os números -->
    <div class="shrink-0 rounded bg-black/50 px-2 py-1.5 font-mono">
      {@render header()}
      <div class="mt-0.5 whitespace-nowrap leading-none tabular-nums" style="font-size: {fontPx}px;">
        <div class={main.color}>{main.text}<span class="ml-[0.2em] text-[0.5em]">{main.unit}</span></div>
        {#if showSecond}
          <div class="mt-[0.15em] flex justify-between gap-[1em]" style="font-size: {SECOND}em;">
            <span class="text-green-300">{ampText}<span class="ml-[0.2em] text-[0.6em]">Vpp</span></span>
            <span class="text-amber-300"
              ><span class="mr-[0.3em] text-[0.6em] text-slate-400">offset</span>{offText}<span
                class="ml-[0.2em] text-[0.6em]">V</span
              ></span
            >
          </div>
        {/if}
      </div>
    </div>

    <!-- ajustes, logo abaixo do display -->
    <div bind:clientHeight={controlsH} class="relative flex shrink-0 flex-col gap-1.5 pr-9">
      {@render controls()}
      <OpcoesAvancadas title="Opções avançadas (carga, ciclo de trabalho, tamanho do número)">
        {@render advanced()}
        {#if onfontsize}
          <TamanhoFonte
            value={size}
            oninput={(v) => (dragSize = v)}
            onchange={(v) => {
              onfontsize(v);
              dragSize = null;
            }}
          />
        {/if}
      </OpcoesAvancadas>
    </div>
  </div>
{:else}
  <div class="flex flex-col gap-3 text-sm">
    <!-- display -->
    <div class="rounded bg-black/50 p-3 font-mono">
      {@render header()}
      <div class="mt-1 text-5xl tabular-nums {main.color}">{main.text} <span class="text-2xl">{main.unit}</span></div>
      {#if showSecond}
        <div class="mt-1 flex justify-between gap-4 text-2xl tabular-nums">
          <span class="text-green-300">{ampText} <span class="text-base">Vpp</span></span>
          <span class="text-amber-300"
            ><span class="mr-1 text-base text-slate-400">offset</span>{offText} <span class="text-base">V</span></span
          >
        </div>
      {/if}
      {#if !driver.has_output_switch}
        <div class="mt-1 text-xs text-slate-500">saída sempre ativa (este modelo não tem liga/desliga)</div>
      {/if}
    </div>

    <!-- ajustes, abaixo do display -->
    <div class="flex flex-col gap-2">
      {@render controls()}
      <div class="flex flex-wrap gap-x-6 gap-y-2 border-t border-slate-700/70 pt-2">
        {@render advanced()}
      </div>
    </div>
  </div>
{/if}
