<script>
  // Aba "Painéis": escolher, criar, editar (grade), salvar e abrir em tela cheia.
  import { api } from "../api.js";
  import { newWidget, WIDGET_TYPES } from "./catalogo.js";
  import PainelGrade from "./PainelGrade.svelte";
  import WidgetConfig from "./WidgetConfig.svelte";

  let { visible, busConnected } = $props();

  const LAST_KEY = "gpibpanel.lastPanel";

  let list = $state([]);
  let cols = $state(24); // vem do backend (grid_cols)
  let panel = $state(null); // painel aberto, como está salvo
  let draft = $state(null); // cópia em edição (null = modo usar)
  let configuring = $state(null); // id do widget com a janela de configuração aberta
  let equipment = $state({});
  let drivers = $state({});
  let error = $state(null);
  let fullscreen = $state(false);
  let fsEl;

  const editing = $derived(draft !== null);
  const shown = $derived(draft ?? panel);
  const ctx = $derived({ equipment, drivers, busConnected, setWidgetConfig });

  async function guard(fn) {
    error = null;
    try {
      await fn();
    } catch (e) {
      error = e.message;
    }
  }

  async function loadAll() {
    await guard(async () => {
      const [panels, eqs, drvs] = await Promise.all([api("/panels"), api("/equipment"), api("/drivers")]);
      cols = panels.grid_cols;
      list = panels.panels;
      equipment = Object.fromEntries(eqs.map((e) => [e.id, e]));
      drivers = Object.fromEntries(drvs.map((d) => [d.name, d]));
      if (!panel && !draft && list.length) {
        const last = Number(readLast());
        await open(list.find((p) => p.id === last)?.id ?? list[0].id);
      }
    });
  }

  function readLast() {
    try {
      return localStorage.getItem(LAST_KEY);
    } catch {
      return null;
    }
  }

  async function open(id) {
    await guard(async () => {
      panel = await api(`/panels/${id}`);
      draft = null;
      try {
        localStorage.setItem(LAST_KEY, String(id));
      } catch {}
    });
  }

  async function create() {
    const name = prompt("Nome do novo painel:");
    if (!name?.trim()) return;
    await guard(async () => {
      const p = await api("/panels", { method: "POST", body: { name } });
      await open(p.id);
      list = (await api("/panels")).panels;
      startEdit();
    });
  }

  // Ajuste feito de dentro do widget (ex.: tamanho do número do multímetro).
  // Editando: entra no rascunho (vale ao salvar). Usando: salva o painel na hora.
  async function setWidgetConfig(id, patch) {
    const target = draft ?? panel;
    const w = target?.widgets.find((x) => x.id === id);
    if (!w) return;
    Object.assign(w.config, patch);
    if (draft) return;
    await guard(async () => {
      panel = await api(`/panels/${panel.id}`, { method: "PUT", body: { name: panel.name, widgets: panel.widgets } });
    });
  }

  function startEdit() {
    draft = structuredClone($state.snapshot(panel));
  }

  function cancelEdit() {
    draft = null;
    configuring = null;
  }

  async function save() {
    await guard(async () => {
      panel = await api(`/panels/${draft.id}`, { method: "PUT", body: { name: draft.name, widgets: draft.widgets } });
      draft = null;
      list = (await api("/panels")).panels;
    });
  }

  async function removePanel() {
    if (!confirm(`Excluir o painel “${panel.name}”?`)) return;
    await guard(async () => {
      await api(`/panels/${panel.id}`, { method: "DELETE" });
      panel = null;
      draft = null;
      list = (await api("/panels")).panels;
      if (list.length) await open(list[0].id);
    });
  }

  function addWidget(type) {
    const w = newWidget(type, draft.widgets, cols);
    draft.widgets.push(w);
    configuring = w.id;
  }

  function removeWidget(id) {
    draft.widgets = draft.widgets.filter((w) => w.id !== id);
  }

  function saveConfig(config) {
    draft.widgets.find((w) => w.id === configuring).config = config;
    configuring = null;
  }

  function toggleFullscreen() {
    if (document.fullscreenElement) document.exitFullscreen();
    else fsEl?.requestFullscreen();
  }

  $effect(() => {
    const onchange = () => (fullscreen = document.fullscreenElement === fsEl);
    document.addEventListener("fullscreenchange", onchange);
    return () => document.removeEventListener("fullscreenchange", onchange);
  });

  // Recarrega ao abrir a aba (equipamentos podem ter mudado)
  $effect(() => {
    if (visible) loadAll();
  });

  const btn = "rounded border border-slate-600 px-2 py-1 text-sm hover:bg-slate-800 disabled:opacity-40";
</script>

<div class="flex flex-col gap-3">
  <!-- barra de ferramentas -->
  <div class="flex flex-wrap items-center gap-2">
    {#if editing}
      <input class="w-64 rounded bg-slate-800 px-2 py-1 font-semibold" bind:value={draft.name} maxlength="100" />
      <span class="text-sm text-slate-400">adicionar:</span>
      {#each Object.entries(WIDGET_TYPES) as [type, info]}
        <button class={btn} title={info.hint} onclick={() => addWidget(type)}>+ {info.label}</button>
      {/each}
      <div class="ml-auto flex gap-2">
        <button class="rounded bg-sky-700 px-3 py-1 text-sm hover:bg-sky-600" onclick={save}>salvar</button>
        <button class={btn} onclick={cancelEdit}>cancelar</button>
        <button class="{btn} hover:border-red-700 hover:text-red-400" onclick={removePanel}>excluir painel</button>
      </div>
    {:else}
      <select
        class="rounded bg-slate-800 px-2 py-1"
        value={panel?.id ?? ""}
        onchange={(e) => open(Number(e.currentTarget.value))}
        disabled={!list.length}
      >
        {#if !list.length}<option value="">nenhum painel</option>{/if}
        {#each list as p}
          <option value={p.id}>{p.name}</option>
        {/each}
      </select>
      <button class={btn} onclick={create}>+ novo painel</button>
      {#if panel}
        <button class={btn} onclick={startEdit}>editar</button>
        <button class={btn} onclick={toggleFullscreen}>tela cheia</button>
      {/if}
    {/if}
  </div>

  {#if error}
    <p class="text-sm text-red-400">✗ {error}</p>
  {/if}
  {#if editing}
    <p class="text-xs text-slate-500">
      Arraste para mover · canto inferior direito redimensiona · ⚙ configura · as mudanças só valem depois de salvar.
    </p>
  {:else if !busConnected && panel}
    <p class="text-sm text-slate-400">Barramento desconectado: conecte na aba Conexões para ler e controlar.</p>
  {/if}

  <!-- o painel (este elemento é o que vai para a tela cheia) -->
  <div bind:this={fsEl} class={fullscreen ? "overflow-auto bg-slate-900 p-4" : ""}>
    {#if fullscreen && shown}
      <div class="mb-3 flex items-center justify-between">
        <h2 class="text-lg font-semibold">{shown.name}</h2>
        <button class={btn} onclick={toggleFullscreen}>sair da tela cheia</button>
      </div>
    {/if}
    {#if shown}
      {#if !shown.widgets.length && !editing}
        <p class="text-sm text-slate-400">Painel vazio. Clique em “editar” para adicionar widgets.</p>
      {/if}
      {#key shown.id}
        <PainelGrade
          bind:widgets={shown.widgets}
          {cols}
          {editing}
          {ctx}
          {visible}
          onconfigure={(id) => (configuring = id)}
          onremove={removeWidget}
        />
      {/key}
    {:else if !list.length}
      <p class="text-sm text-slate-400">Nenhum painel ainda. Clique em “+ novo painel”.</p>
    {/if}
  </div>
</div>

{#if configuring && draft}
  {@const w = draft.widgets.find((x) => x.id === configuring)}
  {#if w}
    <WidgetConfig widget={w} {ctx} onsave={saveConfig} oncancel={() => (configuring = null)} />
  {/if}
{/if}
