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

// --- histórico em memória (para os gráficos) ---------------------------------
// Só o que chegou desde que a página foi aberta; guardar/exportar fica para a Fase 7.
// Fica fora do $state de propósito (milhares de pontos): o gráfico redesenha
// quando live.states[id] muda.
export const HISTORY_MS = 30 * 60 * 1000;
const HISTORY_MAX = 20000;
const history = new Map(); // id -> [{ t (ms), channels | null }]; null = interrupção da linha

function record(id, point) {
  let h = history.get(id);
  if (!h) history.set(id, (h = []));
  const last = h[h.length - 1];
  if (point.channels === null && (!last || last.channels === null)) return; // uma interrupção basta
  if (last && point.t <= last.t) return; // repetida (ex.: última leitura reenviada ao assinar)
  h.push(point);
  const limit = point.t - HISTORY_MS;
  let cut = 0;
  while (cut < h.length && h[cut].t < limit) cut++;
  if (h.length - cut > HISTORY_MAX) cut = h.length - HISTORY_MAX;
  if (cut) h.splice(0, cut);
}

export function getHistory(id) {
  return history.get(id) ?? [];
}

// --- WebSocket ------------------------------------------------------------

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
    if (msg.type === "state") record(msg.id, { t: msg.time * 1000, channels: msg.ok ? msg.data.channels : null });
    live.states[msg.id] = msg;
  };
  ws.onclose = () => {
    live.connected = false;
    ws = null;
    for (const id of counts.keys()) record(id, { t: Date.now(), channels: null });
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
      record(id, { t: Date.now(), channels: null }); // a linha do gráfico não "liga" o buraco
    }
    sendSubscriptions();
  };
}

document.addEventListener("visibilitychange", sendSubscriptions);

// --- ajudantes compartilhados ---------------------------------------------------

/** Leitura de um canal na mensagem (undefined se não há leitura válida). */
export function channelReading(msg, channel) {
  return msg?.ok ? msg.data.channels.find((c) => c.channel === channel) : undefined;
}

/** [classe da bolinha, texto] para o status de um equipamento. */
export function liveStatus(msg, pollMs) {
  if (!live.connected) return ["bg-slate-500", "conectando ao backend…"];
  if (!msg) return ["bg-slate-500", "aguardando leitura…"];
  if (msg.type === "removed") return ["bg-slate-500", "equipamento excluído"];
  if (msg.status === "disconnected") return ["bg-slate-500", "barramento desconectado"];
  if (msg.status === "timeout") return ["bg-red-500", "sem resposta"];
  if (msg.status === "error") return ["bg-red-500", "erro"];
  if ((pollMs ?? msg.poll_ms) === 0) return ["bg-sky-500", "pausado"];
  return ["bg-green-500 animate-pulse", "ao vivo"];
}

// Grandezas de um canal de fonte que os widgets sabem mostrar.
// text: classe do display; line: cor da linha no gráfico (validada contra o fundo escuro)
export const QUANTITIES = {
  voltage: { label: "Tensão", unit: "V", decimals: 3, text: "text-green-300", line: "#16a34a" },
  current: { label: "Corrente", unit: "A", decimals: 4, text: "text-amber-300", line: "#d97706" },
  power: { label: "Potência", unit: "W", decimals: 3, text: "text-sky-300", line: "#0284c7" },
  voltage_set: { label: "Tensão programada", unit: "V", decimals: 3, text: "text-green-300", line: "#16a34a" },
  current_set: { label: "Corrente programada", unit: "A", decimals: 4, text: "text-amber-300", line: "#d97706" },
};

export function quantityValue(reading, quantity) {
  if (!reading) return undefined;
  if (quantity === "power") return reading.voltage * reading.current;
  return reading[quantity];
}
