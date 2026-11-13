<script>
  // Um canal de fonte: leituras ao vivo + ajuste de faixa, tensão, corrente e saída.
  // Será reaproveitado nos painéis (Fase 5).
  import { api } from "./api.js";

  // spec: canal vindo do driver ({name, ranges}); reading: leitura ao vivo do canal (ou undefined)
  let { equipmentId, spec, reading, disabled = false } = $props();

  // Campos editáveis. Enquanto o usuário não mexe, acompanham o valor programado na fonte;
  // depois de editados ("pendentes"), ficam como estão até aplicar (Enter) ou desfazer (Esc).
  let form = $state({ range: "", voltage: null, current: null });
  let dirty = $state({ range: false, voltage: false, current: false });
  let busy = $state(false);
  let error = $state(null);

  const pending = $derived(dirty.range || dirty.voltage || dirty.current);
  const range = $derived(spec.ranges.find((r) => r.name === (dirty.range ? form.range : reading?.range)));

  $effect(() => {
    if (!reading) return;
    if (!dirty.range) form.range = reading.range;
    if (!dirty.voltage) form.voltage = reading.voltage_set;
    if (!dirty.current) form.current = reading.current_set;
  });

  async function send(body) {
    busy = true;
    error = null;
    try {
      await api(`/equipment/${equipmentId}/psu/${spec.name}`, { method: "POST", body });
      return true;
    } catch (e) {
      error = e.message;
      return false;
    } finally {
      busy = false;
    }
  }

  async function apply() {
    if (!pending) return;
    const body = {
      range: dirty.range ? form.range : null,
      voltage: dirty.voltage && form.voltage !== null ? Number(form.voltage) : null,
      current: dirty.current && form.current !== null ? Number(form.current) : null,
    };
    // O estado novo chega pelo WebSocket logo em seguida
    if (await send(body)) dirty = { range: false, voltage: false, current: false };
  }

  function revert() {
    dirty = { range: false, voltage: false, current: false };
    error = null;
  }

  function onkeydown(e) {
    if (e.key === "Enter") apply();
    if (e.key === "Escape") revert();
  }

  const fmt = (x, d) => (x === undefined || x === null ? "—" : Number(x).toFixed(d));
  const field = (isDirty) =>
    `w-28 rounded bg-slate-800 px-2 py-1 text-right font-mono outline-none ${isDirty ? "ring-1 ring-amber-400" : ""}`;
</script>

<div class="flex flex-wrap gap-4">
  <!-- display -->
  <div class="min-w-56 flex-1 rounded bg-black/50 p-3 font-mono">
    <div class="flex items-center justify-between text-xs text-slate-400">
      <span>{spec.name}</span>
      <span
        class="rounded px-1.5 py-0.5 {reading?.output ? 'bg-green-700 text-green-100' : 'bg-slate-700 text-slate-400'}"
      >
        {reading ? (reading.output ? "SAÍDA LIGADA" : "saída desligada") : "—"}
      </span>
    </div>
    <div class="mt-1 text-4xl text-green-300 tabular-nums">{fmt(reading?.voltage, 3)} <span class="text-xl">V</span></div>
    <div class="text-4xl text-amber-300 tabular-nums">{fmt(reading?.current, 4)} <span class="text-xl">A</span></div>
    <div class="mt-1 text-xs text-slate-500">
      programado {fmt(reading?.voltage_set, 3)} V / {fmt(reading?.current_set, 4)} A · faixa {reading?.range ?? "—"}
    </div>
  </div>

  <!-- ajustes -->
  <div class="flex flex-col gap-2 text-sm">
    <label class="flex items-center justify-between gap-3">
      faixa
      <select
        class="w-40 rounded bg-slate-800 px-2 py-1 outline-none {dirty.range ? 'ring-1 ring-amber-400' : ''}"
        bind:value={form.range}
        onchange={() => (dirty.range = form.range !== reading?.range)}
        {onkeydown}
        {disabled}
      >
        {#each spec.ranges as r}
          <option value={r.name}>{r.name} ({r.label})</option>
        {/each}
      </select>
    </label>
    <label class="flex items-center justify-between gap-3">
      tensão (V)
      <input
        class={field(dirty.voltage)}
        type="number"
        step="0.001"
        min="0"
        max={range?.max_voltage}
        bind:value={form.voltage}
        oninput={() => (dirty.voltage = true)}
        {onkeydown}
        {disabled}
      />
    </label>
    <label class="flex items-center justify-between gap-3">
      corrente (A)
      <input
        class={field(dirty.current)}
        type="number"
        step="0.0001"
        min="0"
        max={range?.max_current}
        bind:value={form.current}
        oninput={() => (dirty.current = true)}
        {onkeydown}
        {disabled}
      />
    </label>
    <div class="flex flex-wrap gap-2">
      <button
        class="rounded bg-sky-700 px-3 py-1 hover:bg-sky-600 disabled:opacity-40"
        onclick={apply}
        disabled={disabled || busy || !pending}
        title="Enter aplica · Esc desfaz"
      >
        aplicar
      </button>
      {#if pending}
        <button class="text-slate-400 hover:text-slate-200" onclick={revert}>desfazer</button>
      {/if}
      <button
        class="ml-auto rounded px-3 py-1 font-semibold disabled:opacity-40 {reading?.output
          ? 'bg-red-700 hover:bg-red-600'
          : 'bg-green-700 hover:bg-green-600'}"
        onclick={() => send({ output: !reading.output })}
        disabled={disabled || busy || !reading}
      >
        {reading?.output ? "desligar" : "ligar"}
      </button>
    </div>
    {#if error}
      <p class="max-w-72 text-red-400">✗ {error}</p>
    {/if}
  </div>
</div>
