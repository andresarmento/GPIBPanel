<script>
  // Multímetro: leitura ao vivo + escolha de função, faixa e opções avançadas (NPLC...).
  // Cada ajuste é enviado na hora (não há campos pendentes como na fonte).
  //
  // - Janela "ao vivo": tudo à mostra.
  // - compact (widget dos painéis): número no tamanho escolhido (diminui se não couber);
  //   as opções avançadas ficam num balão aberto pelo ícone no canto inferior direito.
  import { api } from "./api.js";
  import { formatReading, rangeLabel, SHORT } from "./dmm.js";
  import { FONT_DEFAULT } from "./painel/catalogo.js";
  import OpcoesAvancadas from "./OpcoesAvancadas.svelte";
  import TamanhoFonte from "./TamanhoFonte.svelte";

  // driver: descrição do driver ({functions, nplc_min, nplc_max}); reading: msg.data (ou undefined)
  // fontSize: tamanho do número em px (modo compacto); onfontsize(v): salva a escolha (widget)
  let {
    equipmentId,
    driver,
    reading,
    disabled = false,
    compact = false,
    fontSize = FONT_DEFAULT,
    onfontsize = null,
  } = $props();

  const NPLC = [
    [0.01, "0,01 (rápido)"],
    [0.1, "0,1"],
    [1, "1 (normal)"],
    [10, "10 (preciso)"],
  ];

  let busy = $state(false);
  let error = $state(null);
  let dragSize = $state(null); // valor enquanto o controle deslizante está sendo arrastado
  const size = $derived(dragSize ?? fontSize);

  // Modo compacto: o número tem o tamanho escolhido (não muda ao redimensionar o widget);
  // se não couber no espaço que sobra depois dos controles, diminui só o necessário.
  // O fundo preto, os botões e a faixa ficam juntos no alto; a sobra vai para baixo.
  let rootH = $state(0);
  let rootW = $state(0);
  let controlsH = $state(0);
  const HEADER_PX = 32; // cabeçalho do display + margens do fundo preto
  const GAP_PX = 8;
  const fontPx = $derived.by(() => {
    if (!rootH || !rootW) return size;
    const byHeight = rootH - controlsH - GAP_PX - HEADER_PX;
    const byWidth = ((rootW - 16) * 1.65) / (shown.text.length + shown.unit.length / 2 + 2);
    return Math.max(12, Math.min(size, byHeight, byWidth));
  });

  const fn = $derived(driver.functions.find((f) => f.name === reading?.function));
  const nplcOptions = $derived.by(() => {
    const opts = NPLC.filter(([v]) => v >= driver.nplc_min && v <= driver.nplc_max);
    const cur = reading?.nplc;
    return cur == null || opts.some(([v]) => v === cur) ? opts : [...opts, [cur, String(cur)]];
  });

  async function send(body) {
    busy = true;
    error = null;
    try {
      // O estado novo chega pelo WebSocket logo em seguida
      await api(`/equipment/${equipmentId}/dmm`, { method: "POST", body });
    } catch (e) {
      error = e.message;
    } finally {
      busy = false;
    }
  }

  const shown = $derived(formatReading(reading, fn?.unit ?? ""));
  const off = $derived(disabled || busy || !reading);
</script>

{#snippet advancedOptions()}
  <label
    class="flex items-center justify-between gap-3"
    title="Tempo de integração em ciclos da rede: mais = mais lento e mais preciso"
  >
    velocidade (NPLC)
    <select
      class="w-36 rounded bg-slate-800 px-2 py-1"
      value={reading?.nplc ?? ""}
      onchange={(e) => send({ nplc: Number(e.currentTarget.value) })}
      disabled={off || !fn?.nplc}
    >
      {#if !fn?.nplc}
        <option value="">—</option>
      {/if}
      {#each nplcOptions as [v, label]}
        <option value={v}>{label}</option>
      {/each}
    </select>
  </label>
{/snippet}

<div
  bind:clientHeight={rootH}
  bind:clientWidth={rootW}
  class="relative flex {compact ? 'h-full flex-col gap-2' : 'flex-wrap gap-4'}"
>
  <!-- display -->
  {#snippet displayHeader()}
    <div class="flex items-center justify-between gap-2 text-xs text-slate-400">
      <span class="truncate">{fn?.label ?? "—"}{reading?.nplc != null ? ` · NPLC ${reading.nplc}` : ""}</span>
      {#if reading}
        <span class="shrink-0 rounded bg-slate-700 px-1.5 text-slate-300">
          {reading.auto ? "AUTO" : "MANUAL"}{reading.range != null ? ` · ${rangeLabel(reading.range, fn?.unit ?? "")}` : ""}
        </span>
      {/if}
    </div>
  {/snippet}

  {#if compact}
    <!-- o fundo preto abraça o número e cresce ou encolhe junto com ele -->
    <div class="shrink-0 rounded bg-black/50 px-2 py-1.5 font-mono">
      {@render displayHeader()}
      <div
        class="mt-0.5 whitespace-nowrap leading-none tabular-nums {reading?.overload ? 'text-red-400' : 'text-sky-300'}"
        style="font-size: {fontPx}px;"
      >
        {shown.text}<span class="ml-[0.2em] text-[0.5em]">{shown.unit}</span>
      </div>
    </div>
  {:else}
    <div class="min-w-72 flex-1 rounded bg-black/50 p-3 font-mono">
      {@render displayHeader()}
      <div class="mt-1 text-5xl tabular-nums {reading?.overload ? 'text-red-400' : 'text-sky-300'}">
        {shown.text} <span class="text-2xl">{shown.unit}</span>
      </div>
    </div>
  {/if}

  <!-- ajustes -->
  <div bind:clientHeight={controlsH} class="relative flex flex-col text-sm {compact ? 'shrink-0 gap-1.5 pr-9' : 'gap-2'}">
    <div class="flex flex-wrap gap-1">
      {#each driver.functions as f (f.name)}
        <button
          class="rounded px-2 py-1 font-mono {f.name === reading?.function
            ? 'bg-sky-700 text-white'
            : 'bg-slate-800 hover:bg-slate-700'} disabled:opacity-40"
          title={f.label}
          onclick={() => send({ function: f.name })}
          disabled={off}
        >
          {SHORT[f.name] ?? f.name}
        </button>
      {/each}
    </div>

    <label class="flex items-center gap-3 {compact ? '' : 'justify-between'}">
      faixa
      <select
        class="w-36 rounded bg-slate-800 px-2 py-1"
        value={reading ? (reading.auto ? "AUTO" : String(reading.range)) : ""}
        onchange={(e) => send({ range: e.currentTarget.value === "AUTO" ? "AUTO" : Number(e.currentTarget.value) })}
        disabled={off || !fn?.ranges.length}
      >
        <option value="AUTO">automática</option>
        {#each fn?.ranges ?? [] as r}
          <option value={String(r)}>{rangeLabel(r, fn.unit)}</option>
        {/each}
      </select>
    </label>

    {#if !compact}
      <div class="border-t border-slate-700/70 pt-2">
        {@render advancedOptions()}
      </div>
    {/if}

    {#if error}
      <p class="max-w-72 text-red-400">✗ {error}</p>
    {/if}
    {#if compact}
      <OpcoesAvancadas title="Opções avançadas (NPLC, tamanho do número)">
        {@render advancedOptions()}
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
    {/if}
  </div>
</div>
