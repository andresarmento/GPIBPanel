<script>
  import { api } from "./api.js";

  let { connected } = $props();

  let address = $state(5);
  let command = $state("*IDN?");
  let log = $state([]); // { kind: "out" | "in" | "err", text }
  let busy = $state(false);

  const quick = ["*IDN?", "SYST:ERR?", "MEAS:VOLT?", "MEAS:CURR?", "OUTP?", "VOLT:RANG?"];

  function add(kind, text) {
    log.push({ kind, text, time: new Date().toLocaleTimeString() });
  }

  // Comando terminado em "?" é consulta (espera resposta); senão só escreve
  async function send(cmd = command) {
    cmd = cmd.trim();
    if (!cmd || busy) return;
    const isQuery = cmd.endsWith("?");
    busy = true;
    add("out", `[${address}] ${cmd}`);
    try {
      if (isQuery) {
        const r = await api("/bus/query", { method: "POST", body: { address: Number(address), command: cmd } });
        add("in", r.response);
      } else {
        await api("/bus/write", { method: "POST", body: { address: Number(address), command: cmd } });
      }
    } catch (e) {
      add("err", e.message);
    } finally {
      busy = false;
    }
  }

  function onkeydown(e) {
    if (e.key === "Enter") send();
  }
</script>

<section class="rounded border border-slate-700 p-4">
  <div class="mb-3 flex items-center justify-between">
    <h2 class="font-semibold">Console GPIB</h2>
    <button class="text-sm text-slate-400 hover:text-slate-200" onclick={() => (log = [])}>limpar</button>
  </div>

  <div class="mb-3 h-64 overflow-y-auto rounded bg-black/40 p-2 font-mono text-sm">
    {#each log as entry}
      <div
        class={entry.kind === "out" ? "text-sky-300" : entry.kind === "in" ? "text-green-300" : "text-red-400"}
      >
        <span class="text-slate-500">{entry.time}</span>
        {entry.kind === "out" ? "→" : entry.kind === "in" ? "←" : "✗"}
        {entry.text}
      </div>
    {:else}
      <div class="text-slate-500">Comandos terminados em "?" esperam resposta; os outros só são enviados.</div>
    {/each}
  </div>

  <div class="flex flex-wrap items-center gap-2">
    <label class="text-sm">
      endereço
      <input class="w-16 rounded bg-slate-800 px-2 py-1" type="number" min="0" max="30" bind:value={address} />
    </label>
    <input
      class="min-w-48 flex-1 rounded bg-slate-800 px-2 py-1 font-mono"
      bind:value={command}
      {onkeydown}
      placeholder="comando SCPI"
    />
    <button
      class="rounded bg-sky-700 px-3 py-1 text-sm hover:bg-sky-600 disabled:opacity-50"
      onclick={() => send()}
      disabled={!connected || busy}
    >
      enviar
    </button>
  </div>

  <div class="mt-2 flex flex-wrap gap-2">
    {#each quick as q}
      <button
        class="rounded border border-slate-600 px-2 py-0.5 font-mono text-xs hover:bg-slate-800 disabled:opacity-50"
        onclick={() => send(q)}
        disabled={!connected || busy}
      >
        {q}
      </button>
    {/each}
  </div>

  {#if !connected}
    <p class="mt-2 text-sm text-slate-400">Conecte o barramento para usar o console.</p>
  {/if}
</section>
