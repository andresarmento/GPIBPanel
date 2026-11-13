<script>
  // Aba "Controle": todos os equipamentos cadastrados, com leitura ao vivo.
  import { api } from "./api.js";
  import EquipamentoAoVivo from "./EquipamentoAoVivo.svelte";

  let { visible, busConnected } = $props();

  let items = $state([]);
  let drivers = $state({}); // nome -> descrição do driver
  let loaded = $state(false);
  let error = $state(null);

  async function load() {
    error = null;
    try {
      const [eqs, drvs] = await Promise.all([api("/equipment"), api("/drivers")]);
      items = eqs;
      drivers = Object.fromEntries(drvs.map((d) => [d.name, d]));
    } catch (e) {
      error = e.message;
    } finally {
      loaded = true;
    }
  }

  // Recarrega ao abrir a aba (o cadastro pode ter mudado na aba Equipamentos)
  $effect(() => {
    if (visible) load();
  });
</script>

<div class="flex flex-col gap-4">
  {#if error}
    <p class="text-sm text-red-400">✗ {error}</p>
  {/if}
  {#if !busConnected}
    <p class="text-sm text-slate-400">Barramento desconectado: conecte acima para ler e controlar os equipamentos.</p>
  {/if}

  {#each items as eq (eq.id)}
    <EquipamentoAoVivo equipment={eq} driver={drivers[eq.driver]} {visible} {busConnected} />
  {:else}
    {#if loaded}
      <p class="text-sm text-slate-400">Nenhum equipamento cadastrado. Cadastre na aba Equipamentos.</p>
    {/if}
  {/each}
</div>
