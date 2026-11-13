<script>
  // Card de um equipamento em tempo real (janela "ao vivo"): status e controles.
  // O intervalo de leitura só é mostrado aqui; ele é ajustado no cadastro.
  import CanalFonte from "./CanalFonte.svelte";
  import Gerador from "./Gerador.svelte";
  import GeradorRF from "./GeradorRF.svelte";
  import Multimetro from "./Multimetro.svelte";
  import { channelReading, live, liveStatus, pollLabel, watch } from "./live.svelte.js";

  // equipment: cadastro; driver: descrição do driver (GET /api/drivers); visible: aba aberta
  let { equipment, driver, visible, busConnected } = $props();

  // $derived do id: recarregar o cadastro (objeto novo, mesmo id) não reinicia a leitura
  const id = $derived(equipment.id);

  // Só recebe (e o backend só lê) enquanto a aba está visível
  $effect(() => {
    if (visible) return watch(id);
  });

  const msg = $derived(live.states[id]);
  const pollMs = $derived(msg?.poll_ms ?? equipment.poll_ms);
  const slow = $derived(msg?.ok && pollMs > 0 && msg.cycle_ms > pollMs);

  const status = $derived(liveStatus(msg, pollMs));

  const time = (t) => new Date(t * 1000).toLocaleTimeString();
</script>

<section class="rounded border border-slate-700 bg-slate-800/30">
  <header class="flex flex-wrap items-center gap-3 border-b border-slate-700 p-3">
    {#if equipment.image_url}
      <img src={equipment.image_url} alt="" class="h-10 w-14 rounded bg-black/40 object-contain" />
    {/if}
    <div>
      <div class="font-semibold">{equipment.name}</div>
      <div class="text-xs text-slate-400">{equipment.driver} · endereço {equipment.address}</div>
    </div>

    <div class="flex items-center gap-2 text-sm">
      <span class="inline-block h-2.5 w-2.5 rounded-full {status[0]}"></span>
      <span class="text-slate-300">{status[1]}</span>
    </div>

  </header>

  <div class="flex flex-col gap-4 p-3">
    {#if slow}
      <p class="text-sm text-amber-400">
        A leitura completa leva {msg.cycle_ms} ms, mais que o intervalo escolhido: o instrumento está
        sendo lido o mais rápido que consegue (≈ {(1000 / msg.cycle_ms).toFixed(1)} leituras/s).
      </p>
    {/if}
    {#if msg?.error && msg.status !== "disconnected"}
      <p class="text-sm text-red-400">✗ {msg.error}</p>
    {/if}

    {#if driver?.type === "power_supply"}
      {#each driver.channels as spec (spec.name)}
        <CanalFonte
          equipmentId={equipment.id}
          {spec}
          reading={channelReading(msg, spec.name)}
          disabled={!busConnected || msg?.type === "removed"}
        />
      {/each}
    {:else if driver?.type === "function_generator"}
      {#each driver.channels as c (c.name)}
        <Gerador
          equipmentId={equipment.id}
          {driver}
          channel={c.name}
          reading={channelReading(msg, c.name)}
          disabled={!busConnected || msg?.type === "removed"}
        />
      {/each}
    {:else if driver?.type === "rf_generator"}
      {#each driver.channels as c (c.name)}
        <GeradorRF
          equipmentId={equipment.id}
          {driver}
          channel={c.name}
          reading={channelReading(msg, c.name)}
          disabled={!busConnected || msg?.type === "removed"}
        />
      {/each}
    {:else if driver?.type === "multimeter"}
      <Multimetro
        equipmentId={equipment.id}
        {driver}
        reading={msg?.ok ? msg.data : undefined}
        disabled={!busConnected || msg?.type === "removed"}
      />
    {:else}
      <p class="text-sm text-slate-400">Ainda não há componente de controle para o driver {equipment.driver}.</p>
    {/if}
  </div>

  <footer class="flex flex-wrap gap-x-3 border-t border-slate-700/60 px-3 py-1 text-xs text-slate-500">
    <span title="Ajuste no cadastro do equipamento (editar)">{pollLabel(pollMs)}</span>
    {#if msg?.type === "state"}
      <span class={slow ? "text-amber-400" : ""} title="Tempo real de cada leitura completa">
        {slow ? "⚠ " : ""}cada leitura leva {msg.cycle_ms} ms
      </span>
      <span class="ml-auto">última {time(msg.time)}</span>
    {/if}
  </footer>
</section>
