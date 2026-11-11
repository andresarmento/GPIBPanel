// Chamada à API do backend. Lança Error com a mensagem do servidor quando falha.
export async function api(path, { method = "GET", body } = {}) {
  const r = await fetch(`/api${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await r.json().catch(() => null);
  if (!r.ok) {
    const detail = data?.detail;
    throw new Error(
      typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : `HTTP ${r.status}`,
    );
  }
  return data;
}
