<script>
  // Janela de configuração de um widget. Chama onsave(config) ou oncancel().
  import { untrack } from "svelte";
  import { QUANTITIES } from "../live.svelte.js";
  import { CHART_WINDOWS, WIDGET_TYPES } from "./catalogo.js";

  let { widget, ctx, onsave, oncancel } = $props();

  const type = untrack(() => WIDGET_TYPES[widget.type]);
  let cfg = $state(untrack(() => ({ ...structuredClone(type.config), ...structuredClone($state.snapshot(widget.config)) })));

  const supplies = $derived(Object.values(ctx.equipment).filter((e) => e.type === "power_supply"));
  const channels = $derived(ctx.drivers[ctx.equipment[cfg.equipment_id]?.driver]?.channels ?? []);
  const quantities = $derived(
    widget.type === "display" ? Object.entries(QUANTITIES) : Object.entries(QUANTITIES).filter(([k]) => !k.endsWith("_set")),
  );

  // Primeiro equipamento/canal já escolhidos, para o caso comum (uma fonte só)
  if (type.needsEquipment && cfg.equipment_id == null && untrack(() => supplies.length)) {
    cfg.equipment_id = untrack(() => supplies[0].id);
  }
  $effect(() => {
    if (type.needsEquipment && !channels.some((c) => c.name === cfg.channel)) cfg.channel = channels[0]?.name;
  });

  function save(e) {
    e.preventDefault();
    const out = $state.snapshot(cfg);
    if (out.decimals === "" || out.decimals === undefined) out.decimals = null;
    if (out.decimals !== null && out.decimals !== undefined) out.decimals = Number(out.decimals);
    onsave(out);
  }

  const input = "rounded bg-slate-800 px-2 py-1";
</script>

<div
  class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
  role="presentation"
  onkeydown={(e) => e.key === "Escape" && oncancel()}
>
  <form class="w-full max-w-md rounded border border-slate-600 bg-slate-900 p-4 text-sm shadow-xl" onsubmit={save}>
    <h3 class="mb-3 font-semibold">Configurar: {type.label}</h3>

    <div class="flex flex-col gap-3">
      {#if type.needsEquipment}
        {#if supplies.length}
          <label class="flex flex-col gap-1">
            equipamento
            <select class={input} bind:value={cfg.equipment_id}>
              {#each supplies as eq}
                <option value={eq.id}>{eq.name} ({eq.driver} @ {eq.address})</option>
              {/each}
            </select>
          </label>
          {#if channels.length > 1}
            <label class="flex flex-col gap-1">
              canal
              <select class={input} bind:value={cfg.channel}>
                {#each channels as c}
                  <option value={c.name}>{c.name}</option>
                {/each}
              </select>
            </label>
          {/if}
        {:else}
          <p class="text-amber-400">Nenhuma fonte cadastrada. Cadastre na aba Equipamentos.</p>
        {/if}
      {/if}

      {#if widget.type === "display" || widget.type === "chart"}
        <label class="flex flex-col gap-1">
          grandeza
          <select class={input} bind:value={cfg.quantity}>
            {#each quantities as [key, info]}
              <option value={key}>{info.label} ({info.unit})</option>
            {/each}
          </select>
        </label>
      {/if}

      {#if widget.type === "display"}
        <label class="flex flex-col gap-1">
          casas decimais
          <input
            class="{input} w-24"
            type="number"
            min="0"
            max="6"
            placeholder={String(QUANTITIES[cfg.quantity]?.decimals ?? 3)}
            bind:value={cfg.decimals}
          />
        </label>
      {/if}

      {#if widget.type === "chart"}
        <label class="flex flex-col gap-1">
          janela de tempo
          <select class={input} bind:value={cfg.window_s}>
            {#each CHART_WINDOWS as [s, label]}
              <option value={s}>{label}</option>
            {/each}
          </select>
        </label>
        <p class="text-xs text-slate-500">
          O gráfico mostra as leituras desde que a página foi aberta (até 30 min). Para ver tensão e corrente
          juntas, use dois gráficos lado a lado.
        </p>
      {/if}

      {#if type.needsEquipment}
        <label class="flex flex-col gap-1">
          título (opcional)
          <input class={input} bind:value={cfg.label} placeholder="automático" maxlength="60" />
        </label>
      {/if}

      {#if widget.type === "text"}
        <label class="flex flex-col gap-1">
          texto
          <textarea class={input} rows="2" bind:value={cfg.text}></textarea>
        </label>
        <div class="flex gap-3">
          <label class="flex flex-col gap-1">
            tamanho
            <select class={input} bind:value={cfg.size}>
              <option value="sm">pequeno</option>
              <option value="md">normal</option>
              <option value="lg">grande</option>
              <option value="xl">muito grande</option>
              <option value="2xl">enorme</option>
            </select>
          </label>
          <label class="flex flex-col gap-1">
            alinhamento
            <select class={input} bind:value={cfg.align}>
              <option value="left">esquerda</option>
              <option value="center">centro</option>
              <option value="right">direita</option>
            </select>
          </label>
        </div>
      {/if}
    </div>

    <div class="mt-4 flex gap-2">
      <button type="submit" class="rounded bg-sky-700 px-3 py-1 hover:bg-sky-600">ok</button>
      <button type="button" class="rounded border border-slate-600 px-3 py-1 hover:bg-slate-800" onclick={oncancel}>
        cancelar
      </button>
    </div>
  </form>
</div>
