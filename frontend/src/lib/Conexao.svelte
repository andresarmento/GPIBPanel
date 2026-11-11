<script>
  import { api } from "./api.js";

  // status: o que GET /api/bus devolve; onchange: avisa o App quando muda
  let { status, onchange } = $props();

  let ports = $state([]);
  let selected = $state("sim"); // "sim" ou o nome da porta (COM3...)
  let baudrate = $state(115200);
  let busy = $state(false);
  let error = $state(null);

  async function loadPorts() {
    try {
      ports = await api("/bus/ports");
    } catch (e) {
      error = e.message;
    }
  }

  async function connect() {
    busy = true;
    error = null;
    try {
      const body =
        selected === "sim" ? { kind: "sim" } : { kind: "ar488", port: selected, baudrate: Number(baudrate) };
      onchange(await api("/bus/connect", { method: "POST", body }));
    } catch (e) {
      error = e.message;
    } finally {
      busy = false;
    }
  }

  async function disconnect() {
    busy = true;
    error = null;
    try {
      onchange(await api("/bus/disconnect", { method: "POST" }));
    } catch (e) {
      error = e.message;
    } finally {
      busy = false;
    }
  }

  loadPorts();
</script>

<section class="rounded border border-slate-700 p-4">
  <h2 class="mb-3 font-semibold">Conexão</h2>

  {#if status?.connected}
    <div class="flex flex-wrap items-center gap-3">
      <span class="rounded bg-green-700 px-2 py-0.5 text-sm">conectado</span>
      <span class="text-sm">
        {status.kind === "sim" ? "Simulador" : `AR488 em ${status.port} (${status.baudrate} baud)`}
      </span>
      <span class="text-sm text-slate-400">{status.version}</span>
      <button
        class="rounded border border-slate-600 px-2 py-0.5 text-sm hover:bg-slate-800 disabled:opacity-50"
        onclick={disconnect}
        disabled={busy}
      >
        desconectar
      </button>
    </div>
    {#if status.instruments}
      <p class="mt-2 text-sm text-slate-400">
        Instrumentos simulados:
        {#each Object.entries(status.instruments) as [addr, model]}
          <span class="mr-2">{model} @ {addr}</span>
        {/each}
      </p>
    {/if}
  {:else}
    <div class="flex flex-wrap items-center gap-3">
      <select class="rounded bg-slate-800 px-2 py-1 text-sm" bind:value={selected}>
        <option value="sim">Simulado (sem hardware)</option>
        {#each ports as p}
          <option value={p.device}>{p.device} — {p.description}</option>
        {/each}
      </select>
      {#if selected !== "sim"}
        <label class="text-sm">
          baud
          <input class="w-24 rounded bg-slate-800 px-2 py-1" type="number" bind:value={baudrate} />
        </label>
      {/if}
      <button
        class="rounded bg-sky-700 px-3 py-1 text-sm hover:bg-sky-600 disabled:opacity-50"
        onclick={connect}
        disabled={busy}
      >
        {busy ? "conectando…" : "conectar"}
      </button>
      <button class="text-sm text-slate-400 hover:text-slate-200" onclick={loadPorts}>
        atualizar portas
      </button>
    </div>
  {/if}

  {#if error}
    <p class="mt-2 text-sm text-red-400">{error}</p>
  {/if}
</section>
