<script>
  let health = $state(null);
  let error = $state(null);

  async function check() {
    error = null;
    try {
      const r = await fetch("/api/health");
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      health = await r.json();
    } catch (e) {
      health = null;
      error = e.message;
    }
  }

  check();
</script>

<main class="min-h-screen bg-slate-900 text-slate-100 p-8">
  <h1 class="text-2xl font-semibold mb-4">GPIBPanel</h1>

  <div class="flex items-center gap-3">
    <span>Backend:</span>
    {#if health}
      <span class="rounded bg-green-700 px-2 py-0.5 text-sm">ok · v{health.version}</span>
    {:else if error}
      <span class="rounded bg-red-700 px-2 py-0.5 text-sm">offline ({error})</span>
    {:else}
      <span class="text-slate-400 text-sm">verificando…</span>
    {/if}
    <button class="rounded border border-slate-600 px-2 py-0.5 text-sm hover:bg-slate-800" onclick={check}>
      testar de novo
    </button>
  </div>
</main>
