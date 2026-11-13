<script>
  import { api } from "./api.js";
  import EquipamentoForm from "./EquipamentoForm.svelte";

  let { connected } = $props();

  let items = $state([]);
  let drivers = $state([]);
  let editing = $state(null); // null = fechado, "new" = novo, ou o equipamento em edição
  let checks = $state({}); // id -> resultado de /check (ou { error })
  let error = $state(null);

  // Endereços usados por mais de um equipamento (não pode haver dois ligados no mesmo barramento)
  const dupAddresses = $derived(
    new Set(items.map((e) => e.address).filter((a, i, all) => all.indexOf(a) !== i)),
  );

  async function load() {
    error = null;
    try {
      [items, drivers] = await Promise.all([api("/equipment"), api("/drivers")]);
    } catch (e) {
      error = e.message;
    }
  }

  async function remove(eq) {
    if (!confirm(`Excluir “${eq.name}”?`)) return;
    try {
      await api(`/equipment/${eq.id}`, { method: "DELETE" });
      delete checks[eq.id];
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  async function check(eq) {
    checks[eq.id] = { busy: true };
    try {
      checks[eq.id] = await api(`/equipment/${eq.id}/check`, { method: "POST" });
    } catch (e) {
      checks[eq.id] = { error: e.message };
    }
  }

  function saved() {
    editing = null;
    load();
  }

  load();
</script>

<section class="rounded border border-slate-700 p-4">
  <div class="mb-3 flex items-center justify-between">
    <h2 class="font-semibold">Equipamentos</h2>
    {#if editing === null}
      <button class="rounded bg-sky-700 px-3 py-1 text-sm hover:bg-sky-600" onclick={() => (editing = "new")}>
        + novo
      </button>
    {/if}
  </div>

  {#if error}
    <p class="mb-2 text-sm text-red-400">✗ {error}</p>
  {/if}

  {#if editing !== null}
    {#key editing}
      <div class="mb-4">
        <EquipamentoForm
          equipment={editing === "new" ? null : editing}
          {drivers}
          {connected}
          onsaved={saved}
          oncancel={() => (editing = null)}
        />
      </div>
    {/key}
  {/if}

  <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
    {#each items as eq (eq.id)}
      {@const c = checks[eq.id]}
      <div class="flex flex-col overflow-hidden rounded border border-slate-700 bg-slate-800/40">
        <div class="flex h-36 items-center justify-center bg-black/40">
          {#if eq.image_url}
            <img src={eq.image_url} alt={eq.name} class="h-full w-full object-contain" />
          {:else}
            <span class="text-sm text-slate-500">sem foto</span>
          {/if}
        </div>
        <div class="flex flex-1 flex-col gap-1 p-3 text-sm">
          <div class="font-semibold">{eq.name}</div>
          <div class="text-slate-400">
            {eq.driver} · endereço
            <span class={dupAddresses.has(eq.address) ? "text-amber-400" : ""} title={dupAddresses.has(eq.address) ? "Outro equipamento usa o mesmo endereço" : ""}>
              {eq.address}{dupAddresses.has(eq.address) ? " ⚠" : ""}
            </span>
          </div>
          {#if eq.notes}
            <div class="whitespace-pre-line text-slate-400">{eq.notes}</div>
          {/if}

          {#if c}
            <div class="text-xs">
              {#if c.busy}
                <span class="text-slate-400">verificando…</span>
              {:else if c.error}
                <span class="text-red-400">✗ {c.error}</span>
              {:else if !c.online}
                <span class="text-red-400">● sem resposta no endereço {eq.address}</span>
              {:else if c.matches}
                <span class="text-green-400">● online</span>
                <span class="font-mono text-slate-500">{c.idn.raw}</span>
              {:else}
                <span class="text-amber-400">● respondeu, mas é outro modelo:</span>
                <span class="font-mono text-slate-500">{c.idn.raw}</span>
              {/if}
            </div>
          {/if}

          <div class="mt-auto flex gap-3 pt-2 text-sm">
            <button class="text-sky-400 hover:text-sky-300" onclick={() => (editing = eq)}>editar</button>
            <button
              class="text-sky-400 hover:text-sky-300 disabled:text-slate-600"
              onclick={() => check(eq)}
              disabled={!connected || c?.busy}
              title={connected ? "Pergunta *IDN? no endereço cadastrado" : "Conecte o barramento"}
            >
              verificar
            </button>
            <button class="ml-auto text-slate-400 hover:text-red-400" onclick={() => remove(eq)}>excluir</button>
          </div>
        </div>
      </div>
    {:else}
      <p class="text-sm text-slate-400">Nenhum equipamento cadastrado ainda.</p>
    {/each}
  </div>
</section>
