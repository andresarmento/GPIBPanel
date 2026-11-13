<script>
  // Uma grandeza em fonte grande; o tamanho do número acompanha o tamanho do widget.
  let { title, q, value, decimals, status, ok } = $props();

  const text = $derived(value === undefined || value === null ? "—" : Number(value).toFixed(decimals));
</script>

<div class="flex h-full flex-col px-2 py-1" style="container-type: size;">
  <div class="flex items-center gap-2 text-xs text-slate-400">
    <span class="inline-block h-2 w-2 shrink-0 rounded-full {status[0]}" title={status[1]}></span>
    <span class="truncate">{title}</span>
    {#if !ok}
      <span class="ml-auto shrink-0 text-slate-500">{status[1]}</span>
    {/if}
  </div>
  <div
    class="flex min-h-0 flex-1 items-center justify-end font-mono leading-none tabular-nums {q.text} {ok ? '' : 'opacity-40'}"
    style="font-size: min(62cqh, {Math.round(150 / (text.length + 2))}cqw);"
  >
    {text}<span class="ml-[0.15em] text-[0.45em]">{q.unit}</span>
  </div>
</div>
