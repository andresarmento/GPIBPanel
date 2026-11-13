// Tipos de widget dos painéis: nome, tamanho padrão/mínimo (em células da grade) e configuração inicial.

export const ROW_PX = 56; // altura de uma linha da grade
export const GAP_PX = 8; // espaço entre células

export const WIDGET_TYPES = {
  psu_channel: {
    label: "Canal de fonte",
    hint: "display + ajustes + liga/desliga",
    size: [6, 5],
    min: [4, 4],
    needsEquipment: true,
    config: {},
  },
  display: {
    label: "Display",
    hint: "uma grandeza em fonte grande",
    size: [3, 2],
    min: [2, 1],
    needsEquipment: true,
    config: { quantity: "voltage", decimals: null, label: "" },
  },
  output_button: {
    label: "Botão de saída",
    hint: "liga/desliga um canal",
    size: [2, 2],
    min: [1, 1],
    needsEquipment: true,
    config: { label: "" },
  },
  chart: {
    label: "Gráfico",
    hint: "uma grandeza ao longo do tempo",
    size: [6, 4],
    min: [3, 3],
    needsEquipment: true,
    config: { quantity: "voltage", window_s: 300, label: "" },
  },
  text: {
    label: "Texto",
    hint: "título ou anotação",
    size: [4, 1],
    min: [1, 1],
    needsEquipment: false,
    config: { text: "Texto", size: "lg", align: "left" },
  },
};

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
