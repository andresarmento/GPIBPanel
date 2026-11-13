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

// Envia um arquivo (multipart) no campo "file".
export async function upload(path, file, method = "PUT") {
  const form = new FormData();
  form.append("file", file);
  const r = await fetch(`/api${path}`, { method, body: form });
  const data = await r.json().catch(() => null);
  if (!r.ok) throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${r.status}`);
  return data;
}
