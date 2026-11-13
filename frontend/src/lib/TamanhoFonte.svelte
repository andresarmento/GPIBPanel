<script>
  // Controle deslizante do tamanho do número (em px), com o valor ao lado.
  // Limites fixos (FONT_MIN..FONT_MAX) para não escolher tamanhos absurdos.
  import { FONT_MAX, FONT_MIN } from "./painel/catalogo.js";

  // value: tamanho atual; oninput(v): enquanto arrasta; onchange(v): ao soltar
  let { value, oninput = () => {}, onchange = () => {}, label = "tamanho do número" } = $props();
</script>

<label
  class="flex items-center justify-between gap-3"
  title="Se não couber no widget, o número diminui só o necessário"
>
  {label}
  <span class="flex w-44 items-center gap-2">
    <input
      class="min-w-0 flex-1 accent-sky-500"
      type="range"
      min={FONT_MIN}
      max={FONT_MAX}
      step="2"
      {value}
      oninput={(e) => oninput(Number(e.currentTarget.value))}
      onchange={(e) => onchange(Number(e.currentTarget.value))}
    />
    <span class="w-12 text-right text-xs text-slate-400 tabular-nums">{value} px</span>
  </span>
</label>
