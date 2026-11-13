<script>
  // Teste da Fase 2: identifica o instrumento pelo *IDN? e usa o driver de fonte.
  // Provisório: na Fase 4 vira o componente de canal com leitura ao vivo.
  import { api } from "./api.js";

  let { connected } = $props();

  let address = $state(5);
  let found = $state(null); // resposta de /identify
  let channel = $state(null); // nome do canal escolhido
  let st = $state(null); // estado do canal
  let form = $state({ range: "", voltage: "", current: "" });
  let busy = $state(false);
  let error = $state(null);

  const isPsu = $derived(found?.driver?.type === "power_supply");
  const ranges = $derived(found?.driver?.channels?.find((c) => c.name === channel)?.ranges ?? []);
  const base = $derived(`/instruments/${Number(address)}/psu/${channel}`);

  async function run(fn) {
    busy = true;
    error = null;
    try {
      await fn();
    } catch (e) {
      error = e.message;
    } finally {
      busy = false;
    }
  }

  const identify = () =>
    run(async () => {
      found = null;
      st = null;
      found = await api(`/instruments/${Number(address)}/identify`, { method: "POST" });
      channel = found.driver?.channels?.[0]?.name ?? null;
      if (isPsu) await read();
    });

  async function read() {
    st = await api(base);
    form = { range: st.range, voltage: st.voltage_set, current: st.current_set };
  }

  const refresh = () => run(read);

  function apply(extra = {}) {
    return run(async () => {
      const body = {
        range: form.range !== st.range ? form.range : null,
        voltage: form.voltage === "" ? null : Number(form.voltage),
        current: form.current === "" ? null : Number(form.current),
        ...extra,
      };
      st = await api(base, { method: "POST", body });
      form = { range: st.range, voltage: st.voltage_set, current: st.current_set };
    });
  }

  const f = (x, d = 4) => Number(x).toFixed(d);
</script>

<section class="rounded border border-slate-700 p-4">
  <h2 class="mb-3 font-semibold">Teste de driver</h2>

  <div class="flex flex-wrap items-center gap-2">
    <label class="text-sm">
      endereço
      <input class="w-16 rounded bg-slate-800 px-2 py-1" type="number" min="0" max="30" bind:value={address} />
    </label>
    <button
      class="rounded bg-sky-700 px-3 py-1 text-sm hover:bg-sky-600 disabled:opacity-50"
      onclick={identify}
      disabled={!connected || busy}
    >
      identificar
    </button>
  </div>

  {#if error}
    <p class="mt-2 text-sm text-red-400">✗ {error}</p>
  {/if}

  {#if found}
    <div class="mt-3 text-sm">
      <div class="font-mono text-slate-400">{found.idn.raw}</div>
      {#if found.driver}
        <div>
          Driver: <span class="font-semibold">{found.driver.name}</span>
          <span class="text-slate-400">— {found.driver.description}</span>
        </div>
      {:else}
        <div class="text-amber-400">Nenhum driver reconhece este instrumento.</div>
      {/if}
    </div>
  {/if}

  {#if isPsu && st}
    <div class="mt-4 grid max-w-xl grid-cols-2 gap-4">
      <div class="rounded bg-black/40 p-3 font-mono">
        <div class="text-3xl text-green-300">{f(st.voltage, 3)} V</div>
        <div class="text-3xl text-amber-300">{f(st.current, 4)} A</div>
        <div class="mt-1 text-sm text-slate-400">
          canal {st.channel} · {st.range} · saída
          <span class={st.output ? "text-green-400" : "text-slate-500"}>{st.output ? "LIGADA" : "desligada"}</span>
        </div>
        <div class="text-sm text-slate-500">programado: {f(st.voltage_set, 3)} V / {f(st.current_set, 4)} A</div>
      </div>

      <div class="flex flex-col gap-2 text-sm">
        <label class="flex items-center justify-between gap-2">
          faixa
          <select class="w-40 rounded bg-slate-800 px-2 py-1" bind:value={form.range}>
            {#each ranges as r}
              <option value={r.name}>{r.name} ({r.label})</option>
            {/each}
          </select>
        </label>
        <label class="flex items-center justify-between gap-2">
          tensão (V)
          <input class="w-40 rounded bg-slate-800 px-2 py-1" type="number" step="0.001" bind:value={form.voltage} />
        </label>
        <label class="flex items-center justify-between gap-2">
          corrente (A)
          <input class="w-40 rounded bg-slate-800 px-2 py-1" type="number" step="0.0001" bind:value={form.current} />
        </label>
        <div class="flex flex-wrap gap-2">
          <button class="rounded bg-sky-700 px-3 py-1 hover:bg-sky-600 disabled:opacity-50" onclick={() => apply()} disabled={busy}>
            aplicar
          </button>
          <button
            class="rounded px-3 py-1 disabled:opacity-50 {st.output ? 'bg-red-700 hover:bg-red-600' : 'bg-green-700 hover:bg-green-600'}"
            onclick={() => apply({ output: !st.output })}
            disabled={busy}
          >
            {st.output ? "desligar saída" : "ligar saída"}
          </button>
          <button class="rounded border border-slate-600 px-3 py-1 hover:bg-slate-800 disabled:opacity-50" onclick={refresh} disabled={busy}>
            ler
          </button>
        </div>
      </div>
    </div>
  {/if}

  {#if !connected}
    <p class="mt-2 text-sm text-slate-400">Conecte o barramento para testar.</p>
  {/if}
</section>
