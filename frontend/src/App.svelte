<script>
  import { api } from "./lib/api.js";
  import Conexao from "./lib/Conexao.svelte";
  import ConsoleGpib from "./lib/ConsoleGpib.svelte";
  import Equipamentos from "./lib/Equipamentos.svelte";
  import Paineis from "./lib/painel/Paineis.svelte";

  let health = $state(null);
  let error = $state(null);
  let bus = $state(null); // status do barramento (GET /api/bus)

  const tabs = [
    ["paineis", "Painéis"],
    ["equipamentos", "Equipamentos"],
    ["console", "Console GPIB"],
    ["conexoes", "Conexões"],
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

<!-- conteúdo centralizado, até 1600 px de largura -->
<main class="mx-auto min-h-screen w-full max-w-[1600px] px-4 py-6 text-slate-100 sm:px-8">
  <h1 class="mb-4 text-2xl font-semibold">GPIBPanel</h1>

  <!-- Backend fora do ar: só aparece quando há problema -->
  {#if !health}
    <div class="mb-6 flex items-center gap-3 text-sm">
      {#if error}
        <span class="rounded bg-red-700 px-2 py-0.5">backend offline ({error})</span>
      {:else}
        <span class="text-slate-400">conectando ao backend…</span>
      {/if}
      <button class="rounded border border-slate-600 px-2 py-0.5 hover:bg-slate-800" onclick={check}>
        testar de novo
      </button>
    </div>
  {/if}

  {#if health}
    <div class="flex flex-col gap-4">
      <nav class="flex items-end gap-1 border-b border-slate-700">
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
        <!-- estado do barramento, discreto; clique leva à aba Conexões -->
        <button
          class="ml-auto mb-1 flex items-center gap-1.5 rounded px-2 py-0.5 text-xs text-slate-400 hover:bg-slate-800"
          onclick={() => (tab = "conexoes")}
          title={health ? `backend v${health.version}` : ""}
        >
          <span class="inline-block h-2 w-2 rounded-full {bus?.connected ? 'bg-green-500' : 'bg-slate-500'}"></span>
          {#if bus?.connected}
            {bus.kind === "sim" ? "simulador" : `AR488 ${bus.port}`}
          {:else}
            GPIB desconectado
          {/if}
        </button>
      </nav>

      <!-- "hidden" em vez de {#if}: cada aba mantém seu estado (ex.: histórico do console) -->
      <div class:hidden={tab !== "paineis"}>
        <Paineis visible={tab === "paineis"} busConnected={!!bus?.connected} />
      </div>
      <div class:hidden={tab !== "equipamentos"}>
        <Equipamentos connected={!!bus?.connected} visible={tab === "equipamentos"} />
      </div>
      <div class:hidden={tab !== "console"}><ConsoleGpib connected={bus?.connected} /></div>
      <div class:hidden={tab !== "conexoes"}>
        <Conexao status={bus} onchange={(s) => (bus = s)} />
      </div>
    </div>
  {/if}
</main>
