// Tipos de widget dos painéis: nome, tamanho padrão/mínimo (em células da grade), configuração
// inicial e os tipos de equipamento aceitos (accepts; vazio = não usa equipamento).

// Grade de 24 colunas (vem do backend) com linhas de 24 px: 2 células = 1 célula da
// grade antiga (12 colunas, linhas de 56 px), com o mesmo espaço entre elas.
export const ROW_PX = 24; // altura de uma linha da grade
export const GAP_PX = 8; // espaço entre células

// Tamanho do número (px) nos widgets Multímetro e Display: escolhido por controle
// deslizante entre estes limites; se não couber no widget, diminui só o necessário.
export const FONT_MIN = 16;
export const FONT_MAX = 200;
export const FONT_DEFAULT = 48;

export const WIDGET_TYPES = {
  psu_channel: {
    label: "Fonte",
    hint: "display + ajustes + liga/desliga",
    size: [12, 10],
    min: [8, 8],
    needsEquipment: true,
    accepts: ["power_supply"],
    config: { font_size: FONT_DEFAULT },
  },
  dmm: {
    label: "Multímetro",
    hint: "display + função, faixa e velocidade",
    size: [12, 8],
    min: [8, 6], // em 6 linhas (184 px) ainda cabem display (número menor), funções e faixa
    needsEquipment: true,
    accepts: ["multimeter"],
    config: { font_size: FONT_DEFAULT },
  },
  fgen: {
    label: "Gerador",
    hint: "frequência, amplitude, offset e forma de onda",
    size: [12, 10],
    min: [8, 8],
    needsEquipment: true,
    accepts: ["function_generator"],
    config: { font_size: FONT_DEFAULT },
  },
  rfgen: {
    label: "Gerador RF",
    hint: "frequência, nível (dBm) e liga/desliga do RF",
    size: [12, 8],
    min: [8, 6],
    needsEquipment: true,
    accepts: ["rf_generator"],
    config: { font_size: FONT_DEFAULT },
  },
  display: {
    label: "Display",
    hint: "uma leitura em fonte grande",
    size: [6, 4],
    min: [4, 2],
    needsEquipment: true,
    accepts: ["power_supply", "multimeter", "function_generator", "rf_generator"],
    config: { quantity: "voltage", decimals: null, label: "", font_size: FONT_DEFAULT },
  },
  output_button: {
    label: "Botão de saída",
    hint: "liga/desliga um canal",
    size: [4, 4],
    min: [2, 2],
    needsEquipment: true,
    accepts: ["power_supply"],
    config: { label: "" },
  },
  chart: {
    label: "Gráfico",
    hint: "uma leitura ao longo do tempo",
    size: [12, 8],
    min: [6, 6],
    needsEquipment: true,
    accepts: ["power_supply", "multimeter", "function_generator", "rf_generator"],
    config: { quantity: "voltage", window_s: 300, label: "" },
  },
  text: {
    label: "Texto",
    hint: "título ou anotação",
    size: [8, 2],
    min: [1, 1],
    needsEquipment: false,
    accepts: [],
    config: { text: "Texto", size: "lg", align: "left" },
  },
};

export const TYPE_LABELS = { power_supply: "fonte", multimeter: "multímetro", function_generator: "gerador", rf_generator: "gerador de RF" };

export const CHART_WINDOWS = [
  [60, "1 min"],
  [300, "5 min"],
  [900, "15 min"],
  [1800, "30 min"],
];

export function overlaps(a, b) {
  return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
}

/** O retângulo cabe na grade sem encostar em outro widget (exceto o próprio `id`)? */
export function fits(rect, widgets, cols, id = null) {
  return (
    rect.x >= 0 &&
    rect.y >= 0 &&
    rect.x + rect.w <= cols &&
    widgets.every((w) => w.id === id || !overlaps(rect, w))
  );
}

/** Primeiro lugar livre (de cima para baixo, da esquerda para a direita). */
export function findFreeSpot(widgets, cols, w, h) {
  w = Math.min(w, cols);
  for (let y = 0; ; y++) {
    for (let x = 0; x + w <= cols; x++) {
      if (fits({ x, y, w, h }, widgets, cols)) return { x, y, w, h };
    }
  }
}

export function newWidget(type, widgets, cols) {
  const t = WIDGET_TYPES[type];
  return {
    id: Math.random().toString(36).slice(2, 10),
    type,
    ...findFreeSpot(widgets, cols, t.size[0], t.size[1]),
    config: structuredClone(t.config),
  };
}
