<script>
  import { api } from "./lib/api.js";
  import Conexao from "./lib/Conexao.svelte";
  import ConsoleGpib from "./lib/ConsoleGpib.svelte";

  let health = $state(null);
  let error = $state(null);
  let bus = $state(null); // status do barramento (GET /api/bus)

  async function check() {
    error = null;
    try {
      health = await api("/health");
      bus = await api("/bus");
    } catch (e) {
      health = null;
      error = e.message;
    }
  }

  check();
</script>

<main class="min-h-screen bg-slate-900 p-8 text-slate-100">
  <h1 class="mb-4 text-2xl font-semibold">GPIBPanel</h1>

  <div class="mb-6 flex items-center gap-3">
    <span>Backend:</span>
    {#if health}
      <span class="rounded bg-green-700 px-2 py-0.5 text-sm">ok · v{health.version}</span>
    {:else if error}
      <span class="rounded bg-red-700 px-2 py-0.5 text-sm">offline ({error})</span>
    {:else}
      <span class="text-sm text-slate-400">verificando…</span>
    {/if}
    <button class="rounded border border-slate-600 px-2 py-0.5 text-sm hover:bg-slate-800" onclick={check}>
      testar de novo
    </button>
  </div>

  {#if health}
    <div class="flex max-w-4xl flex-col gap-4">
      <Conexao status={bus} onchange={(s) => (bus = s)} />
      <ConsoleGpib connected={bus?.connected} />
    </div>
  {/if}
</main>
