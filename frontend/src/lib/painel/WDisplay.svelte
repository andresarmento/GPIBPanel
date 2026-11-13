<script>
  // Uma leitura em fonte grande; o tamanho do número acompanha o tamanho do widget.
  // text/unit já formatados; color: classe da cor do número
  // footer: texto discreto embaixo (intervalo de leitura)
  // size: tamanho do número em px; se não couber no widget, diminui só o necessário
  let { title, text, unit, color, status, ok, footer = "", size = 48 } = $props();
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
    class="flex min-h-0 flex-1 items-center justify-end font-mono leading-none tabular-nums {color} {ok ? '' : 'opacity-40'}"
    style="font-size: min({size}px, {footer ? 52 : 62}cqh, {Math.round(150 / (text.length + 2))}cqw);"
  >
    {text}<span class="ml-[0.15em] text-[0.45em]">{unit}</span>
  </div>
  {#if footer}
    <div class="shrink-0 text-right text-[10px] leading-3 text-slate-500">{footer}</div>
  {/if}
</div>
