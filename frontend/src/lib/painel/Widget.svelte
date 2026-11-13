<script>
  // Um widget do painel: assina as leituras do equipamento e mostra o conteúdo do tipo.
  import CanalFonte from "../CanalFonte.svelte";
  import { formatReading, formatSI } from "../dmm.js";
  import Gerador from "../Gerador.svelte";
  import GeradorRF from "../GeradorRF.svelte";
  import {
    channelReading,
    dmmReading,
    live,
    liveStatus,
    pollLabel,
    quantitiesFor,
    quantityValue,
    watch,
  } from "../live.svelte.js";
  import Multimetro from "../Multimetro.svelte";
  import { FONT_DEFAULT, TYPE_LABELS, WIDGET_TYPES } from "./catalogo.js";
  import WDisplay from "./WDisplay.svelte";
  import WGrafico from "./WGrafico.svelte";
  import WSaida from "./WSaida.svelte";
  import WTexto from "./WTexto.svelte";

  // ctx: { equipment: {id: eq}, drivers: {nome: driver}, busConnected }
  let { widget, ctx, visible, editing } = $props();

  // Cores do multímetro (display e linha do gráfico)
  const DMM = { text: "text-sky-300", line: "#0284c7" };

  const type = $derived(WIDGET_TYPES[widget.type]);
  const cfg = $derived(widget.config);
  const eqId = $derived(type.needsEquipment ? (cfg.equipment_id ?? null) : null);

  // Vários widgets do mesmo equipamento compartilham a mesma leitura no backend
  $effect(() => {
    if (visible && eqId !== null) return watch(eqId);
  });

  const eq = $derived(eqId !== null ? ctx.equipment[eqId] : undefined);
  const driver = $derived(eq ? ctx.drivers[eq.driver] : undefined);
  const isDmm = $derived(driver?.type === "multimeter");
  const msg = $derived(eqId !== null ? live.states[eqId] : undefined);
  const status = $derived(liveStatus(msg));
  const showsQuantity = $derived(widget.type === "display" || widget.type === "chart");

  // --- fonte e gerador (por canal) ---
  const channel = $derived(cfg.channel ?? driver?.channels?.[0]?.name);
  const spec = $derived(driver?.channels?.find((c) => c.name === channel));
  const reading = $derived(channelReading(msg, channel));
  const table = $derived(quantitiesFor(driver?.type) ?? {});
  const q = $derived(table[cfg.quantity] ?? Object.values(table)[0] ?? { label: "", unit: "", decimals: 3 });

  // --- multímetro ---
  // A função vem da leitura ao vivo; enquanto não chega, fica a última conhecida
  const dmm = $derived(dmmReading(msg));
  let lastFunction = $state(null);
  $effect(() => {
    if (dmm) lastFunction = dmm.function;
  });
  const fn = $derived(isDmm ? driver.functions.find((f) => f.name === (dmm?.function ?? lastFunction)) : undefined);
  const dmmQ = $derived({ label: fn?.label ?? "Leitura", unit: fn?.unit ?? "", line: DMM.line, si: true });

  const title = $derived(
    cfg.label ||
      [
        eq?.name,
        !isDmm && (driver?.channels?.length ?? 0) > 1 ? channel : null,
        showsQuantity ? (isDmm ? fn?.label : q.label) : null,
      ]
        .filter(Boolean)
        .join(" · "),
  );

  const problem = $derived.by(() => {
    if (!type.needsEquipment) return null;
    if (eqId === null) return "Configure o equipamento (⚙ no modo edição).";
    if (!eq) return "O equipamento deste widget não existe mais.";
    if (!type.accepts.includes(driver?.type)) {
      return `${eq.name} não é ${type.accepts.map((t) => TYPE_LABELS[t]).join(" nem ")}.`;
    }
    if (driver.channels && !spec) return `${eq.name} não tem o canal ${channel}.`;
    return null;
  });

  // Display: texto já formatado
  const shown = $derived.by(() => {
    if (isDmm) {
      const f = formatReading(dmm, fn?.unit ?? "", cfg.decimals);
      return { ...f, color: dmm?.overload ? "text-red-400" : DMM.text, ok: !!dmm };
    }
    const v = quantityValue(reading, cfg.quantity);
    if (q.si) return { ...formatSI(v, q.unit, cfg.decimals), color: q.text, ok: !!reading };
    const text = v === undefined || v === null ? "—" : Number(v).toFixed(cfg.decimals ?? q.decimals);
    return { text, unit: q.unit, color: q.text, ok: !!reading };
  });

  // Gráfico: de onde tirar o valor de cada leitura do histórico
  const pick = $derived.by(() => {
    if (isDmm) {
      const name = fn?.name;
      // Só a função atual: leituras de outra função (ou em sobrecarga) interrompem a linha
      return (data) => (data.function === name && !data.overload ? data.value : undefined);
    }
    const ch = channel;
    const quantity = table[cfg.quantity] ? cfg.quantity : Object.keys(table)[0];
    return (data) =>
      quantityValue(
        data.channels?.find((c) => c.channel === ch),
        quantity,
      );
  });

  const disabled = $derived(!ctx.busConnected || editing);
  // Rodapé discreto: intervalo de leitura do equipamento (ajustado no cadastro)
  const pollText = $derived(pollLabel(msg?.poll_ms ?? eq?.poll_ms));
</script>

{#if widget.type === "text"}
  <WTexto config={cfg} />
{:else}
  <div class="flex h-full flex-col overflow-hidden rounded border border-slate-700 bg-slate-800/40">
    {#if widget.type !== "display"}
      <div class="flex items-center gap-2 border-b border-slate-700/70 px-2 py-1 text-xs">
        <span class="inline-block h-2 w-2 shrink-0 rounded-full {problem ? 'bg-slate-600' : status[0]}" title={status[1]}
        ></span>
        <span class="truncate text-slate-300">{title || type.label}</span>
        {#if !problem && msg && !msg.ok && msg.type === "state"}
          <span class="ml-auto shrink-0 text-slate-500">{status[1]}</span>
        {/if}
      </div>
    {/if}

    <div class="min-h-0 flex-1 {['psu_channel', 'dmm', 'fgen', 'rfgen'].includes(widget.type) ? 'overflow-auto p-2' : ''}">
      {#if problem}
        <p class="p-2 text-sm text-slate-400">{problem}</p>
      {:else if widget.type === "psu_channel"}
        <CanalFonte
          compact
          equipmentId={eqId}
          {spec}
          {reading}
          {disabled}
          fontSize={cfg.font_size ?? FONT_DEFAULT}
          onfontsize={(v) => ctx.setWidgetConfig(widget.id, { font_size: v })}
        />
      {:else if widget.type === "fgen"}
        <Gerador
          compact
          equipmentId={eqId}
          {driver}
          {channel}
          {reading}
          {disabled}
          fontSize={cfg.font_size ?? FONT_DEFAULT}
          onfontsize={(v) => ctx.setWidgetConfig(widget.id, { font_size: v })}
        />
      {:else if widget.type === "rfgen"}
        <GeradorRF
          compact
          equipmentId={eqId}
          {driver}
          {channel}
          {reading}
          {disabled}
          fontSize={cfg.font_size ?? FONT_DEFAULT}
          onfontsize={(v) => ctx.setWidgetConfig(widget.id, { font_size: v })}
        />
      {:else if widget.type === "dmm"}
        <Multimetro
          compact
          equipmentId={eqId}
          {driver}
          reading={dmm}
          {disabled}
          fontSize={cfg.font_size ?? FONT_DEFAULT}
          onfontsize={(v) => ctx.setWidgetConfig(widget.id, { font_size: v })}
        />
      {:else if widget.type === "display"}
        <WDisplay
          {title}
          text={shown.text}
          unit={shown.unit}
          color={shown.color}
          {status}
          ok={shown.ok}
          footer={pollText}
          size={cfg.font_size ?? FONT_DEFAULT}
        />
      {:else if widget.type === "output_button"}
        <WSaida equipmentId={eqId} {channel} {reading} {disabled} />
      {:else if widget.type === "chart"}
        <WGrafico {eqId} q={isDmm ? dmmQ : q} {pick} windowS={cfg.window_s ?? 300} {msg} />
      {/if}
    </div>
    {#if !problem && widget.type !== "display" && pollText}
      <div class="shrink-0 px-2 text-right text-[10px] leading-4 text-slate-500">{pollText}</div>
    {/if}
  </div>
{/if}
