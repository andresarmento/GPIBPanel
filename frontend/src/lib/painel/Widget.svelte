<script>
  // Um widget do painel: assina as leituras do equipamento e mostra o conteúdo do tipo.
  import CanalFonte from "../CanalFonte.svelte";
  import { channelReading, live, liveStatus, QUANTITIES, quantityValue, watch } from "../live.svelte.js";
  import { WIDGET_TYPES } from "./catalogo.js";
  import WDisplay from "./WDisplay.svelte";
  import WGrafico from "./WGrafico.svelte";
  import WSaida from "./WSaida.svelte";
  import WTexto from "./WTexto.svelte";

  // ctx: { equipment: {id: eq}, drivers: {nome: driver}, busConnected }
  let { widget, ctx, visible, editing } = $props();

  const type = $derived(WIDGET_TYPES[widget.type]);
  const cfg = $derived(widget.config);
  const eqId = $derived(type.needsEquipment ? (cfg.equipment_id ?? null) : null);

  // Vários widgets do mesmo equipamento compartilham a mesma leitura no backend
  $effect(() => {
    if (visible && eqId !== null) return watch(eqId);
  });

  const eq = $derived(eqId !== null ? ctx.equipment[eqId] : undefined);
  const driver = $derived(eq ? ctx.drivers[eq.driver] : undefined);
  const channel = $derived(cfg.channel ?? driver?.channels?.[0]?.name);
  const spec = $derived(driver?.channels?.find((c) => c.name === channel));
  const msg = $derived(eqId !== null ? live.states[eqId] : undefined);
  const reading = $derived(channelReading(msg, channel));
  const status = $derived(liveStatus(msg));
  const q = $derived(QUANTITIES[cfg.quantity] ?? QUANTITIES.voltage);
  const showsQuantity = $derived(widget.type === "display" || widget.type === "chart");

  const title = $derived(
    cfg.label ||
      [eq?.name, (driver?.channels?.length ?? 0) > 1 ? channel : null, showsQuantity ? q.label : null]
        .filter(Boolean)
        .join(" · "),
  );

  const problem = $derived.by(() => {
    if (!type.needsEquipment) return null;
    if (eqId === null) return "Configure o equipamento (⚙ no modo edição).";
    if (!eq) return "O equipamento deste widget não existe mais.";
    if (driver?.type !== "power_supply") return `${eq.name} não é uma fonte.`;
    if (!spec) return `${eq.name} não tem o canal ${channel}.`;
    return null;
  });

  const disabled = $derived(!ctx.busConnected || editing);
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

    <div class="min-h-0 flex-1 {widget.type === 'psu_channel' ? 'overflow-auto p-2' : ''}">
      {#if problem}
        <p class="p-2 text-sm text-slate-400">{problem}</p>
      {:else if widget.type === "psu_channel"}
        <CanalFonte equipmentId={eqId} {spec} {reading} {disabled} />
      {:else if widget.type === "display"}
        <WDisplay
          {title}
          {q}
          value={quantityValue(reading, cfg.quantity)}
          decimals={cfg.decimals ?? q.decimals}
          {status}
          ok={!!reading}
        />
      {:else if widget.type === "output_button"}
        <WSaida equipmentId={eqId} {channel} {reading} {disabled} />
      {:else if widget.type === "chart"}
        <WGrafico {eqId} {channel} quantity={cfg.quantity ?? "voltage"} windowS={cfg.window_s ?? 300} {msg} />
      {/if}
    </div>
  </div>
{/if}
