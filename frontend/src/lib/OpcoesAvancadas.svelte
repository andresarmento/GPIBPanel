<script>
  // Ícone de "opções avançadas" (controles deslizantes) que abre um balão por cima.
  // Fica no canto inferior direito do elemento posicionado (relative) mais próximo.
  // Fecha clicando no ícone de novo, clicando fora ou com Esc.
  // children: o conteúdo do balão
  let { children, title = "Opções avançadas" } = $props();

  let open = $state(false);
  let el = $state(null);

  function closeOutside(e) {
    if (open && el && !el.contains(e.target)) open = false;
  }
</script>

<svelte:window onpointerdown={closeOutside} onkeydown={(e) => e.key === "Escape" && (open = false)} />

<div bind:this={el} class="absolute bottom-0 right-0">
  <button
    class="rounded p-1 {open ? 'bg-slate-700 text-slate-100' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'}"
    onclick={() => (open = !open)}
    {title}
    aria-label={title}
    aria-expanded={open}
  >
    <svg viewBox="0 0 20 20" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
      <path d="M3 5h8M15 5h2M3 10h2M9 10h8M3 15h10M17 15h0" />
      <circle cx="13" cy="5" r="2" />
      <circle cx="7" cy="10" r="2" />
      <circle cx="15" cy="15" r="2" />
    </svg>
  </button>
  {#if open}
    <div
      class="absolute bottom-full right-0 z-10 mb-1 flex flex-col gap-2 rounded border border-slate-600 bg-slate-900 p-2 text-sm whitespace-nowrap shadow-lg"
    >
      <div class="text-xs text-slate-400">opções avançadas</div>
      {@render children()}
    </div>
  {/if}
</div>
