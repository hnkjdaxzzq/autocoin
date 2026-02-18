/* ===== API client ===== */
const API_BASE = "/api/v1";

async function apiFetch(path, options = {}) {
  const res = await fetch(API_BASE + path, {
    headers: options.headers || {},
    ...options,
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { const j = await res.json(); msg = j.detail || msg; } catch (_) {}
    throw new Error(msg);
  }
  return res.json();
}

const API = {
  transactions: {
    list: (params) =>
      apiFetch("/transactions?" + new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ""))
      )),
    get: (id) => apiFetch(`/transactions/${id}`),
    update: (id, body) =>
      apiFetch(`/transactions/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    delete: (id) => apiFetch(`/transactions/${id}`, { method: "DELETE" }),
    create: (body) =>
      apiFetch("/transactions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
  },
  imports: {
    upload: async (formData) => {
      const res = await fetch(API_BASE + "/imports", {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        let msg = `HTTP ${res.status}`;
        try { const j = await res.json(); msg = j.detail || msg; } catch (_) {}
        throw new Error(msg);
      }
      return res.json();
    },
    list: () => apiFetch("/imports"),
    get: (id) => apiFetch(`/imports/${id}`),
  },
  stats: {
    summary: (params) =>
      apiFetch("/statistics/summary?" + new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ""))
      )),
    monthly: (year) => apiFetch(`/statistics/monthly?year=${year}`),
    category: (params) =>
      apiFetch("/statistics/category?" + new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ""))
      )),
    daily: (year, month) => apiFetch(`/statistics/daily?year=${year}&month=${month}`),
  },
};
