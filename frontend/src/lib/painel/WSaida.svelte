<script>
  // Botão grande de liga/desliga de um canal.
  import { api } from "../api.js";

  let { equipmentId, channel, reading, disabled } = $props();

  let busy = $state(false);
  let error = $state(null);

  async function toggle() {
    busy = true;
    error = null;
    try {
      // O estado novo chega pelo WebSocket logo em seguida
      await api(`/equipment/${equipmentId}/psu/${channel}`, { method: "POST", body: { output: !reading.output } });
    } catch (e) {
      error = e.message;
    } finally {
      busy = false;
    }
  }
</script>

<div class="flex h-full flex-col gap-1 p-2" style="container-type: size;">
  <button
    class="flex-1 rounded font-semibold transition-colors disabled:opacity-40 {reading?.output
      ? 'bg-green-700 text-green-50 hover:bg-green-600'
      : 'bg-slate-700 text-slate-300 hover:bg-slate-600'}"
    style="font-size: clamp(0.75rem, min(18cqh, 12cqw), 2.5rem);"
    onclick={toggle}
    disabled={disabled || busy || !reading}
    title={reading?.output ? "clique para desligar" : "clique para ligar"}
  >
    {reading ? (reading.output ? "LIGADA" : "DESLIGADA") : "—"}
  </button>
  {#if error}
    <p class="truncate text-xs text-red-400" title={error}>✗ {error}</p>
  {/if}
</div>
