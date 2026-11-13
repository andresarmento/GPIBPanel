<script>
  // Formulário de novo equipamento / edição. Chama onsaved(equipamento) ou oncancel().
  import { untrack } from "svelte";
  import { api, upload } from "./api.js";
  import { POLL_INTERVALS } from "./live.svelte.js";

  let { equipment = null, drivers, connected, onsaved, oncancel } = $props();

  // Cópia inicial dos dados recebidos (o formulário é recriado a cada abertura)
  const initial = untrack(() => equipment);
  let name = $state(initial?.name ?? "");
  let address = $state(initial?.address ?? 5);
  let driver = $state(initial?.driver ?? untrack(() => drivers[0]?.name) ?? "");
  let notes = $state(initial?.notes ?? "");
  let pollMs = $state(initial?.poll_ms ?? 1000);
  // Valor fora da lista (ex.: gravado por uma versão antiga) continua aparecendo
  const intervals = POLL_INTERVALS.some(([ms]) => ms === pollMs)
    ? POLL_INTERVALS
    : [...POLL_INTERVALS, [pollMs, `${pollMs} ms`]];

  let file = $state(null); // foto nova escolhida
  let preview = $state(initial?.image_url ?? null);
  let removeImage = $state(false);

  let busy = $state(false);
  let error = $state(null);
  let detected = $state(null);

  function pick(e) {
    file = e.currentTarget.files?.[0] ?? null;
    if (file) {
      if (preview?.startsWith("blob:")) URL.revokeObjectURL(preview);
      preview = URL.createObjectURL(file);
      removeImage = false;
    }
  }

  function clearImage() {
    file = null;
    preview = null;
    removeImage = true;
  }

  // Pergunta *IDN? no endereço e escolhe o driver automaticamente
  async function detect() {
    busy = true;
    error = null;
    detected = null;
    try {
      const r = await api(`/instruments/${Number(address)}/identify`, { method: "POST" });
      detected = r.idn.raw;
      if (r.driver) {
        driver = r.driver.name;
        if (!name.trim()) name = `${r.idn.model} @ ${address}`;
      } else {
        error = "Instrumento respondeu, mas nenhum driver o reconhece.";
      }
    } catch (e) {
      error = e.message;
    } finally {
      busy = false;
    }
  }

  async function save(e) {
    e.preventDefault();
    busy = true;
    error = null;
    try {
      const body = { name, address: Number(address), driver, notes };
      let saved = initial
        ? await api(`/equipment/${initial.id}`, { method: "PUT", body })
        : await api("/equipment", { method: "POST", body });
      // Intervalo tem rota própria: avisa as telas abertas na hora
      if (Number(pollMs) !== saved.poll_ms) {
        saved = await api(`/equipment/${saved.id}/poll`, { method: "PATCH", body: { poll_ms: Number(pollMs) } });
      }
      if (file) saved = await upload(`/equipment/${saved.id}/image`, file);
      else if (removeImage && initial?.image_url) saved = await api(`/equipment/${saved.id}/image`, { method: "DELETE" });
      onsaved(saved);
    } catch (e) {
      error = e.message;
    } finally {
      busy = false;
    }
  }
</script>

<form class="rounded border border-sky-800 bg-slate-800/40 p-4" onsubmit={save}>
  <h3 class="mb-3 font-semibold">{initial ? `Editar “${initial.name}”` : "Novo equipamento"}</h3>

  <div class="flex flex-wrap gap-4">
    <!-- foto -->
    <div class="flex w-40 flex-col items-center gap-2">
      <div class="flex h-32 w-40 items-center justify-center overflow-hidden rounded bg-black/40">
        {#if preview}
          <img src={preview} alt="foto" class="h-full w-full object-contain" />
        {:else}
          <span class="text-sm text-slate-500">sem foto</span>
        {/if}
      </div>
      <label class="cursor-pointer text-sm text-sky-400 hover:text-sky-300">
        escolher foto…
        <input type="file" accept="image/png,image/jpeg,image/gif,image/webp" class="hidden" onchange={pick} />
      </label>
      {#if preview}
        <button type="button" class="text-xs text-slate-400 hover:text-red-400" onclick={clearImage}>remover foto</button>
      {/if}
    </div>

    <!-- dados -->
    <div class="flex min-w-64 flex-1 flex-col gap-2 text-sm">
      <label class="flex flex-col gap-1">
        nome
        <input class="rounded bg-slate-800 px-2 py-1" bind:value={name} maxlength="100" required />
      </label>
      <div class="flex flex-wrap items-end gap-2">
        <label class="flex flex-col gap-1">
          endereço GPIB
          <input class="w-20 rounded bg-slate-800 px-2 py-1" type="number" min="0" max="30" bind:value={address} required />
        </label>
        <label class="flex flex-1 flex-col gap-1">
          driver
          <select class="rounded bg-slate-800 px-2 py-1" bind:value={driver}>
            {#each drivers as d}
              <option value={d.name}>{d.name} — {d.description}</option>
            {/each}
          </select>
        </label>
        <button
          type="button"
          class="rounded border border-slate-600 px-2 py-1 hover:bg-slate-700 disabled:opacity-50"
          onclick={detect}
          disabled={!connected || busy}
          title={connected ? "Pergunta *IDN? no endereço e escolhe o driver" : "Conecte o barramento"}
        >
          detectar
        </button>
      </div>
      {#if detected}
        <div class="font-mono text-xs text-slate-400">*IDN? → {detected}</div>
      {/if}
      <label class="flex flex-col gap-1">
        intervalo de leitura
        <select class="w-72 rounded bg-slate-800 px-2 py-1" bind:value={pollMs}>
          {#each intervals as [ms, label]}
            <option value={ms}>{label}</option>
          {/each}
        </select>
        <span class="text-xs text-slate-500">
          Vale para a janela “ao vivo” e todos os painéis. Aparelho lento (ex.: multímetro em AC) pede intervalo maior.
        </span>
      </label>
      <label class="flex flex-col gap-1">
        observações
        <textarea class="rounded bg-slate-800 px-2 py-1" rows="2" bind:value={notes}></textarea>
      </label>
    </div>
  </div>

  {#if error}
    <p class="mt-2 text-sm text-red-400">✗ {error}</p>
  {/if}

  <div class="mt-3 flex gap-2">
    <button type="submit" class="rounded bg-sky-700 px-3 py-1 text-sm hover:bg-sky-600 disabled:opacity-50" disabled={busy}>
      salvar
    </button>
    <button type="button" class="rounded border border-slate-600 px-3 py-1 text-sm hover:bg-slate-800" onclick={oncancel}>
      cancelar
    </button>
  </div>
</form>
