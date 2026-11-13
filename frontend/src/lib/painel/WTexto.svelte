<script>
  let { config } = $props();

  const SIZES = { sm: "text-sm", md: "text-base", lg: "text-xl", xl: "text-3xl", "2xl": "text-5xl" };
  const ALIGN = { left: "justify-start text-left", center: "justify-center text-center", right: "justify-end text-right" };
</script>

<div
  class="flex h-full items-center overflow-hidden whitespace-pre-line px-1 font-semibold text-slate-200 {SIZES[
    config.size
  ] ?? SIZES.lg} {ALIGN[config.align] ?? ALIGN.left}"
>
  {config.text}
</div>
