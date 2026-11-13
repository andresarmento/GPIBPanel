<script>
  // Card de um equipamento no controle em tempo real: status, intervalo de leitura e canais.
  import { api } from "./api.js";
  import CanalFonte from "./CanalFonte.svelte";
  import { live, watch } from "./live.svelte.js";

  // equipment: cadastro; driver: descrição do driver (GET /api/drivers); visible: aba aberta
  let { equipment, driver, visible, busConnected } = $props();

  const INTERVALS = [
    [250, "250 ms"],
    [500, "500 ms"],
    [1000, "1 s"],
    [2000, "2 s"],
    [5000, "5 s"],
    [0, "pausado"],
  ];

  // $derived do id: recarregar o cadastro (objeto novo, mesmo id) não reinicia a leitura
  const id = $derived(equipment.id);

  // Só recebe (e o backend só lê) enquanto a aba está visível
  $effect(() => {
    if (visible) return watch(id);
  });

  const msg = $derived(live.states[id]);
  const pollMs = $derived(msg?.poll_ms ?? equipment.poll_ms);
  const intervals = $derived(
    INTERVALS.some(([ms]) => ms === pollMs) ? INTERVALS : [...INTERVALS, [pollMs, `${pollMs} ms`]],
  );
  const slow = $derived(msg?.ok && pollMs > 0 && msg.cycle_ms > pollMs);
  let pollError = $state(null);

  const status = $derived.by(() => {
    if (!live.connected) return ["bg-slate-500", "conectando ao backend…"];
    if (!msg) return ["bg-slate-500", "aguardando leitura…"];
    if (msg.type === "removed") return ["bg-slate-500", "equipamento excluído"];
    if (msg.status === "disconnected") return ["bg-slate-500", "barramento desconectado"];
    if (msg.status === "timeout") return ["bg-red-500", "sem resposta"];
    if (msg.status === "error") return ["bg-red-500", "erro"];
    if (pollMs === 0) return ["bg-sky-500", "pausado"];
    return ["bg-green-500 animate-pulse", "ao vivo"];
  });

  async function setPoll(e) {
    pollError = null;
    try {
      await api(`/equipment/${equipment.id}/poll`, { method: "PATCH", body: { poll_ms: Number(e.currentTarget.value) } });
    } catch (err) {
      pollError = err.message;
    }
  }

  const channelState = (name) => (msg?.ok ? msg.data.channels.find((c) => c.channel === name) : undefined);
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

    <div class="ml-auto flex items-center gap-2 text-sm">
      {#if msg?.type === "state"}
        <span class="text-xs {slow ? 'text-amber-400' : 'text-slate-500'}" title="Tempo real de cada leitura completa">
          {slow ? "⚠ " : ""}leitura {msg.cycle_ms} ms · {time(msg.time)}
        </span>
      {/if}
      <label class="flex items-center gap-1">
        intervalo
        <select class="rounded bg-slate-800 px-2 py-1" value={pollMs} onchange={setPoll}>
          {#each intervals as [ms, label]}
            <option value={ms}>{label}</option>
          {/each}
        </select>
      </label>
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
    {#if pollError}
      <p class="text-sm text-red-400">✗ {pollError}</p>
    {/if}

    {#if driver?.type === "power_supply"}
      {#each driver.channels as spec (spec.name)}
        <CanalFonte
          equipmentId={equipment.id}
          {spec}
          reading={channelState(spec.name)}
          disabled={!busConnected || msg?.type === "removed"}
        />
      {/each}
    {:else}
      <p class="text-sm text-slate-400">Ainda não há componente de controle para o driver {equipment.driver}.</p>
    {/if}
  </div>
</section>
