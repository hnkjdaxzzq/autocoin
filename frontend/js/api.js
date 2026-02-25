/* ===== Auth Token Management ===== */
const Auth = {
  getToken() { return localStorage.getItem("autocoin_token"); },
  setToken(token) { localStorage.setItem("autocoin_token", token); },
  getUsername() { return localStorage.getItem("autocoin_username"); },
  setUsername(name) { localStorage.setItem("autocoin_username", name); },
  clear() {
    localStorage.removeItem("autocoin_token");
    localStorage.removeItem("autocoin_username");
  },
  isLoggedIn() { return !!this.getToken(); },
};

/* ===== API client ===== */
const API_BASE = "/api/v1";

async function apiFetch(path, options = {}) {
  const token = Auth.getToken();
  const headers = { ...(options.headers || {}) };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(API_BASE + path, { ...options, headers });

  if (res.status === 401 && !path.startsWith("/auth/")) {
    Auth.clear();
    window.location.hash = "#/login";
    throw new Error("请先登录");
  }

  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { const j = await res.json(); msg = j.detail || msg; } catch (_) {}
    throw new Error(msg);
  }
  return res.json();
}

const API = {
  auth: {
    register: (body) =>
      apiFetch("/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    login: (body) =>
      apiFetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    me: () => apiFetch("/auth/me"),
  },
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
      const headers = {};
      const token = Auth.getToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(API_BASE + "/imports", {
        method: "POST",
        headers,
        body: formData,
      });

      if (res.status === 401) {
        Auth.clear();
        window.location.hash = "#/login";
        throw new Error("请先登录");
      }

      if (!res.ok) {
        let msg = `HTTP ${res.status}`;
        try { const j = await res.json(); msg = j.detail || msg; } catch (_) {}
        throw new Error(msg);
      }
      return res.json();
    },
    list: () => apiFetch("/imports"),
    get: (id) => apiFetch(`/imports/${id}`),
    recognizeImages: async (formData, { timeoutMs = 90000 } = {}) => {
      const headers = {};
      const token = Auth.getToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);

      let res;
      try {
        res = await fetch(API_BASE + "/imports/image/recognize", {
          method: "POST",
          headers,
          body: formData,
          signal: controller.signal,
        });
      } catch (e) {
        clearTimeout(timer);
        if (e.name === "AbortError") throw new Error("识别请求超时，请稍后重试或减少图片数量");
        throw e;
      } finally {
        clearTimeout(timer);
      }

      if (res.status === 401) {
        Auth.clear();
        window.location.hash = "#/login";
        throw new Error("请先登录");
      }

      if (!res.ok) {
        let msg = `HTTP ${res.status}`;
        try { const j = await res.json(); msg = j.detail || msg; } catch (_) {}
        throw new Error(msg);
      }
      return res.json();
    },
    confirmImageImport: (transactions) =>
      apiFetch("/imports/image/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transactions }),
      }),
    imageQuota: () => apiFetch("/imports/image/quota"),
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
