<script>
  // Gerador de RF: frequência, nível (dBm) e liga/desliga da saída de RF.
  //
  // - Frequência e nível ficam "pendentes" (contorno amarelo) até aplicar (Enter)
  //   ou desfazer (Esc); o liga/desliga é enviado na hora.
  // - Com o RF desligado, alguns modelos (ex.: MG3601A) não informam o nível: o
  //   display mostra "—" e o campo guarda o último valor conhecido.
  // - Janela "ao vivo": layout largo. compact (widget "Gerador RF" dos painéis):
  //   número no tamanho escolhido (diminui se não couber) e opções avançadas
  //   (por enquanto só o tamanho do número) no ícone do canto inferior direito.
  import { api } from "./api.js";
  import { formatSI } from "./dmm.js";
  import OpcoesAvancadas from "./OpcoesAvancadas.svelte";
  import { FONT_DEFAULT } from "./painel/catalogo.js";
  import TamanhoFonte from "./TamanhoFonte.svelte";

  // driver: descrição do driver ({frequency_min/max, level_min/max}); channel: "RF"
  // reading: estado ao vivo ({frequency, level, output}) ou undefined
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

  const FREQ_UNITS = [
    ["kHz", 1e3],
    ["MHz", 1e6],
    ["GHz", 1e9],
  ];

  let busy = $state(false);
  let error = $state(null);

  // --- campos pendentes ---------------------------------------------------------
  let form = $state({ frequency: null, freqUnit: 1e6, level: null });
  let dirty = $state({ frequency: false, level: false });
  const pending = $derived(dirty.frequency || dirty.level);
  const clean = (x) => +Number(x).toPrecision(12);
  const autoUnit = (hz) => (hz >= 1e9 ? 1e9 : hz >= 1e6 ? 1e6 : 1e3);

  $effect(() => {
    if (!reading) return;
    if (!dirty.frequency && reading.frequency != null) {
      form.freqUnit = autoUnit(reading.frequency);
      form.frequency = clean(reading.frequency / form.freqUnit);
    }
    if (!dirty.level && reading.level != null) form.level = reading.level;
  });

  async function send(body) {
    busy = true;
    error = null;
    try {
      // O estado novo chega pelo WebSocket logo em seguida
      await api(`/equipment/${equipmentId}/rf/${channel}`, { method: "POST", body });
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
      frequency: dirty.frequency && form.frequency !== null ? clean(Number(form.frequency) * form.freqUnit) : null,
      level: dirty.level && form.level !== null && form.level !== "" ? Number(form.level) : null,
    };
    if (await send(body)) revert();
  }

  function revert() {
    dirty = { frequency: false, level: false };
    error = null;
  }

  function onkeydown(e) {
    if (e.key === "Enter") apply();
    if (e.key === "Escape") revert();
  }

  const field = (isDirty) =>
    `${compact ? "w-24" : "w-28"} rounded bg-slate-800 px-2 py-1 text-right font-mono outline-none ${isDirty ? "ring-1 ring-amber-400" : ""}`;
  const off = $derived(disabled || busy || !reading);

  // --- display -----------------------------------------------------------------------
  const freq = $derived(reading ? formatSI(reading.frequency, "Hz") : { text: "—", unit: "Hz" });
  const levelText = $derived(
    reading?.level != null ? (reading.level > 0 ? "+" : "") + reading.level.toFixed(1) : "—",
  );

  // --- modo compacto: tamanho do número ------------------------------------------------
  let dragSize = $state(null);
  const size = $derived(dragSize ?? fontSize);
  let rootH = $state(0);
  let rootW = $state(0);
  let controlsH = $state(0);
  const FIXED_PX = 32; // cabeçalho + margens do fundo preto
  const GAP_PX = 8;
  const fontPx = $derived.by(() => {
    if (!rootH || !rootW) return size;
    const byHeight = (rootH - controlsH - GAP_PX - FIXED_PX) / 2.15; // duas linhas
    const chars = Math.max(freq.text.length + freq.unit.length / 2, levelText.length + 1.5) + 1;
    const byWidth = ((rootW - 16) * 1.65) / (chars + 1);
    return Math.max(12, Math.min(size, byHeight, byWidth));
  });
</script>

{#snippet header()}
  <div class="flex items-center justify-between gap-2 text-xs text-slate-400">
    <span class="truncate">{channel}</span>
    <span
      class="shrink-0 rounded px-1.5 py-0.5 {reading?.output ? 'bg-green-700 text-green-100' : 'bg-slate-700 text-slate-400'}"
    >
      {reading ? (reading.output ? "RF LIGADO" : "RF desligado") : "—"}
    </span>
  </div>
{/snippet}

{#snippet frequencyField()}
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
{/snippet}

{#snippet levelField()}
  <label class="flex items-center gap-2">
    {compact ? "dBm" : "nível (dBm)"}
    <input
      class={field(dirty.level)}
      type="number"
      step="0.1"
      min={driver.level_min}
      max={driver.level_max}
      bind:value={form.level}
      oninput={() => (dirty.level = true)}
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
  <button
    class="rounded px-3 py-1 font-semibold disabled:opacity-40 {reading?.output
      ? 'bg-red-700 hover:bg-red-600'
      : 'bg-green-700 hover:bg-green-600'}"
    onclick={() => send({ output: !reading.output })}
    disabled={off}
  >
    {reading?.output ? "desligar RF" : "ligar RF"}
  </button>
{/snippet}

{#snippet controls()}
  <div class="flex flex-wrap items-center gap-x-3 gap-y-1.5">
    {@render frequencyField()}
    {@render levelField()}
  </div>
  <div class="flex flex-wrap items-center gap-2">
    {@render buttons()}
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
        <div class="text-sky-300">{freq.text}<span class="ml-[0.2em] text-[0.5em]">{freq.unit}</span></div>
        <div class="mt-[0.1em] {reading?.output ? 'text-green-300' : 'text-slate-500'}">
          {levelText}<span class="ml-[0.2em] text-[0.5em]">dBm</span>
        </div>
      </div>
    </div>

    <!-- ajustes, logo abaixo do display -->
    <div bind:clientHeight={controlsH} class="relative flex shrink-0 flex-col gap-1.5 pr-9">
      {@render controls()}
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
  <div class="flex flex-col gap-3 text-sm">
    <div class="rounded bg-black/50 p-3 font-mono">
      {@render header()}
      <div class="mt-1 text-5xl text-sky-300 tabular-nums">{freq.text} <span class="text-2xl">{freq.unit}</span></div>
      <div class="mt-1 text-5xl tabular-nums {reading?.output ? 'text-green-300' : 'text-slate-500'}">
        {levelText} <span class="text-2xl">dBm</span>
      </div>
      <div class="mt-1 text-xs text-slate-500">
        faixa {formatSI(driver.frequency_min, "Hz", 1).text}
        {formatSI(driver.frequency_min, "Hz", 1).unit} a {formatSI(driver.frequency_max, "Hz", 0).text}
        {formatSI(driver.frequency_max, "Hz", 0).unit} · {driver.level_min} a +{driver.level_max} dBm
      </div>
    </div>
    <div class="flex flex-col gap-2">
      {@render controls()}
    </div>
  </div>
{/if}
