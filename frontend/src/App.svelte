<script>
  import { api } from "./lib/api.js";
  import Conexao from "./lib/Conexao.svelte";
  import ConsoleGpib from "./lib/ConsoleGpib.svelte";
  import Controle from "./lib/Controle.svelte";
  import Equipamentos from "./lib/Equipamentos.svelte";
  import Paineis from "./lib/painel/Paineis.svelte";

  let health = $state(null);
  let error = $state(null);
  let bus = $state(null); // status do barramento (GET /api/bus)

  const tabs = [
    ["paineis", "Painéis"],
    ["controle", "Controle"],
    ["equipamentos", "Equipamentos"],
    ["console", "Console GPIB"],
  ];
  let tab = $state("paineis");

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
    <div class="flex max-w-5xl flex-col gap-4">
      <Conexao status={bus} onchange={(s) => (bus = s)} />

      <nav class="flex gap-1 border-b border-slate-700">
        {#each tabs as [id, label]}
          <button
            class="-mb-px rounded-t border px-3 py-1.5 text-sm {tab === id
              ? 'border-slate-700 border-b-slate-900 bg-slate-900 text-slate-100'
              : 'border-transparent text-slate-400 hover:text-slate-200'}"
            onclick={() => (tab = id)}
          >
            {label}
          </button>
        {/each}
      </nav>

      <!-- "hidden" em vez de {#if}: cada aba mantém seu estado (ex.: histórico do console) -->
      <div class:hidden={tab !== "paineis"}>
        <Paineis visible={tab === "paineis"} busConnected={!!bus?.connected} />
      </div>
      <div class:hidden={tab !== "controle"}>
        <Controle visible={tab === "controle"} busConnected={!!bus?.connected} />
      </div>
      <div class:hidden={tab !== "equipamentos"}><Equipamentos connected={bus?.connected} /></div>
      <div class:hidden={tab !== "console"}><ConsoleGpib connected={bus?.connected} /></div>
    </div>
  {/if}
</main>
