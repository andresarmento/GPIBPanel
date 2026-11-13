// Formatação das leituras de multímetro (prefixo SI no estilo do display de bancada).

// Rótulos curtos das funções (os nomes são comuns a todos os multímetros)
export const SHORT = { DCV: "V DC", ACV: "V AC", DCI: "A DC", ACI: "A AC", OHM2: "Ω 2W", OHM4: "Ω 4W", FREQ: "Hz" };

const PREFIX = { 6: "M", 3: "k", 0: "", "-3": "m", "-6": "µ", "-9": "n" };

/** Expoente (múltiplo de 3) para mostrar um valor; V e A não usam "k"/"M". */
export function exponent(x, unit) {
  if (!x || !Number.isFinite(x)) return 0;
  let e = Math.floor(Math.log10(Math.abs(x)) / 3) * 3;
  e = Math.max(-9, Math.min(6, e));
  return unit === "V" || unit === "A" ? Math.min(e, 0) : e;
}

export const prefixed = (e, unit) => PREFIX[e] + unit;

/**
 * Leitura no estilo do display de 6½ dígitos: a faixa define o prefixo e as casas
 * (faixa de 10 V → "+1.23457 V"; faixa de 100 mA → "+12.3000 mA").
 * decimals (opcional) fixa as casas depois do prefixo.
 */
export function formatReading(r, unit, decimals = null) {
  if (!r) return { text: "—", unit };
  if (r.overload) return { text: "OVERFLOW", unit: "" };
  const e = exponent(r.range ?? r.value, unit);
  const scaled = r.value / 10 ** e;
  let text;
  if (decimals !== null && decimals !== undefined) {
    text = scaled.toFixed(decimals);
  } else if (r.range != null) {
    const intDigits = Math.max(1, Math.floor(Math.log10(r.range / 10 ** e) + 1e-9) + 1);
    text = scaled.toFixed(Math.max(0, 7 - intDigits));
  } else {
    text = scaled.toPrecision(7);
  }
  return { text: (r.value >= 0 ? "+" : "") + text, unit: prefixed(e, unit) };
}

/**
 * Valor com prefixo SI (ex.: 1500 Hz → "1.500000 kHz").
 * decimals (opcional) fixa as casas depois do prefixo; senão, 7 algarismos.
 */
export function formatSI(value, unit, decimals = null) {
  if (value === undefined || value === null || !Number.isFinite(value)) return { text: "—", unit };
  const e = exponent(value, unit);
  const scaled = value / 10 ** e;
  const text = decimals !== null && decimals !== undefined ? scaled.toFixed(decimals) : scaled.toPrecision(7);
  return { text, unit: prefixed(e, unit) };
}

/** "100 mV", "10 kΩ", "1000 V" */
export function rangeLabel(value, unit) {
  const e = exponent(value, unit);
  return `${+(value / 10 ** e).toPrecision(6)} ${prefixed(e, unit)}`;
}
