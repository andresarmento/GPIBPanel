<script>
  // Grade do painel. No modo edição: arrastar move, o canto inferior direito redimensiona;
  // a posição encaixa nas células e não é aceita se sobrepor outro widget (contorno vermelho).
  import { fits, GAP_PX, ROW_PX, WIDGET_TYPES } from "./catalogo.js";
  import Widget from "./Widget.svelte";

  let { widgets = $bindable(), cols, editing, ctx, visible, onconfigure, onremove } = $props();

  let width = $state(0);
  let drag = $state(null); // { id, mode: "move" | "resize", sx, sy, orig, rect, valid }

  const colW = $derived((width - GAP_PX * (cols - 1)) / cols);
  const rows = $derived(
    Math.max(1, ...widgets.map((w) => w.y + w.h), drag ? drag.rect.y + drag.rect.h : 0) + (editing ? 3 : 0),
  );

  const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);

  function start(e, w, mode) {
    if (!editing || e.button !== 0) return;
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
    const orig = { x: w.x, y: w.y, w: w.w, h: w.h };
    drag = { id: w.id, mode, sx: e.clientX, sy: e.clientY, orig, rect: orig, valid: true };
  }

  function move(e) {
    if (!drag) return;
    const dx = Math.round((e.clientX - drag.sx) / (colW + GAP_PX));
    const dy = Math.round((e.clientY - drag.sy) / (ROW_PX + GAP_PX));
    const o = drag.orig;
    const [minW, minH] = WIDGET_TYPES[widgets.find((w) => w.id === drag.id).type].min;
    const rect =
      drag.mode === "move"
        ? { ...o, x: clamp(o.x + dx, 0, cols - o.w), y: Math.max(0, o.y + dy) }
        : { ...o, w: clamp(o.w + dx, minW, cols - o.x), h: Math.max(minH, o.h + dy) };
    drag.rect = rect;
    drag.valid = fits(rect, widgets, cols, drag.id);
  }

  function end() {
    if (!drag) return;
    if (drag.valid) Object.assign(widgets.find((w) => w.id === drag.id), drag.rect);
    drag = null;
  }
</script>

<div
  class="relative grid select-none"
  bind:clientWidth={width}
  style="grid-template-columns: repeat({cols}, minmax(0, 1fr)); grid-template-rows: repeat({rows}, {ROW_PX}px); gap: {GAP_PX}px;"
>
  {#if editing}
    {#each { length: rows * cols } as _, i}
      <div
        class="rounded border border-dashed border-slate-800"
        style="grid-column: {(i % cols) + 1}; grid-row: {Math.floor(i / cols) + 1};"
      ></div>
    {/each}
  {/if}

  {#each widgets as w (w.id)}
    {@const r = drag?.id === w.id ? drag.rect : w}
    <div
      class="relative min-h-0 min-w-0 {drag?.id === w.id ? 'z-10 opacity-90' : ''}"
      style="grid-column: {r.x + 1} / span {r.w}; grid-row: {r.y + 1} / span {r.h};"
    >
      <Widget widget={w} {ctx} {visible} {editing} />

      {#if editing}
        <!-- camada de edição por cima do conteúdo: arrastar move o widget -->
        <div
          class="absolute inset-0 cursor-move rounded ring-2 {drag?.id === w.id
            ? drag.valid
              ? 'ring-sky-400'
              : 'ring-red-500'
            : 'ring-sky-800 hover:ring-sky-500'}"
          role="button"
          tabindex="-1"
          aria-label="mover widget"
          onpointerdown={(e) => start(e, w, "move")}
          onpointermove={move}
          onpointerup={end}
          onpointercancel={end}
        ></div>
        <div class="absolute right-1 top-1 flex gap-1">
          <button
            class="rounded bg-slate-700 px-1.5 text-sm hover:bg-sky-700"
            title="configurar"
            onclick={() => onconfigure(w.id)}>⚙</button
          >
          <button
            class="rounded bg-slate-700 px-1.5 text-sm hover:bg-red-700"
            title="remover"
            onclick={() => onremove(w.id)}>✕</button
          >
        </div>
        <div
          class="absolute bottom-0 right-0 h-5 w-5 cursor-se-resize rounded-br bg-[linear-gradient(135deg,transparent_50%,var(--color-sky-500)_50%)]"
          role="button"
          tabindex="-1"
          aria-label="redimensionar widget"
          onpointerdown={(e) => start(e, w, "resize")}
          onpointermove={move}
          onpointerup={end}
          onpointercancel={end}
        ></div>
      {/if}
    </div>
  {/each}
</div>
