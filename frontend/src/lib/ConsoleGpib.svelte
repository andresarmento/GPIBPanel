<script>
  import { api } from "./api.js";

  let { connected } = $props();

  let address = $state(5);
  let command = $state("*IDN?");
  let log = $state([]); // { kind: "out" | "in" | "err", text }
  let busy = $state(false);
  // auto: termina em "?" = envia e lê (SCPI); "query": sempre envia e lê; "write": só envia.
  // Aparelhos sem SCPI (ex.: Anritsu MG3601A) pedem dados sem "?" (FRRD): use "enviar e ler".
  let mode = $state("auto");

  const quick = ["*IDN?", "SYST:ERR?", "MEAS:VOLT?", "MEAS:CURR?", "OUTP?", "VOLT:RANG?"];

  function add(kind, text) {
    log.push({ kind, text, time: new Date().toLocaleTimeString() });
  }

  async function send(cmd = command) {
    cmd = cmd.trim();
    if (!cmd || busy) return;
    const isQuery = mode === "query" || (mode === "auto" && cmd.endsWith("?"));
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

  // Só lê a resposta pendente (sem enviar nada)
  async function read() {
    if (busy) return;
    busy = true;
    add("out", `[${address}] (ler)`);
    try {
      add("in", (await api(`/bus/read/${Number(address)}`, { method: "POST" })).response);
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
      <div class="text-slate-500">
        No modo automático, comandos terminados em "?" esperam resposta e os outros só são enviados. Para
        aparelhos sem SCPI (ex.: FRRD no Anritsu), escolha "enviar e ler" ou use o botão "ler".
      </div>
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
      placeholder="comando"
    />
    <select class="rounded bg-slate-800 px-2 py-1 text-sm" bind:value={mode} title="Quando ler a resposta">
      <option value="auto">automático (? = lê)</option>
      <option value="query">enviar e ler</option>
      <option value="write">só enviar</option>
    </select>
    <button
      class="rounded bg-sky-700 px-3 py-1 text-sm hover:bg-sky-600 disabled:opacity-50"
      onclick={() => send()}
      disabled={!connected || busy}
    >
      enviar
    </button>
    <button
      class="rounded border border-slate-600 px-3 py-1 text-sm hover:bg-slate-800 disabled:opacity-50"
      onclick={read}
      disabled={!connected || busy}
      title="Só lê a resposta pendente do instrumento, sem enviar comando"
    >
      ler
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
