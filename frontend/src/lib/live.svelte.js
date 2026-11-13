// Conexão única com o WebSocket das leituras ao vivo (/api/ws), compartilhada
// por todos os componentes. Cada componente chama watch(id) para receber as
// leituras de um equipamento; o backend só lê o que alguém está olhando.

export const live = $state({
  connected: false, // WebSocket conectado ao backend
  states: {}, // id do equipamento -> última mensagem recebida
});

const counts = new Map(); // id -> quantos componentes estão olhando
let ws = null;
let retry = null;

function sendSubscriptions() {
  if (ws?.readyState !== WebSocket.OPEN) return;
  // Aba do navegador escondida: para de ler tudo até ela voltar
  const ids = document.hidden ? [] : [...counts.keys()];
  ws.send(JSON.stringify({ subscribe: ids }));
}

function connect() {
  retry = null;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/api/ws`);
  ws.onopen = () => {
    live.connected = true;
    sendSubscriptions();
  };
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    live.states[msg.id] = msg;
  };
  ws.onclose = () => {
    live.connected = false;
    ws = null;
    // Backend reiniciou (ex.: --reload)? tenta de novo enquanto alguém estiver olhando
    if (counts.size && !retry) retry = setTimeout(connect, 2000);
  };
}

/** Começa a receber as leituras do equipamento. Devolve a função que para. */
export function watch(id) {
  counts.set(id, (counts.get(id) ?? 0) + 1);
  if (!ws && !retry) connect();
  else sendSubscriptions();

  return () => {
    const n = counts.get(id) - 1;
    if (n > 0) {
      counts.set(id, n);
    } else {
      counts.delete(id);
      delete live.states[id];
    }
    sendSubscriptions();
  };
}

document.addEventListener("visibilitychange", sendSubscriptions);
