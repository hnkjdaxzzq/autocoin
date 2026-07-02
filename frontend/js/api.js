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
    changePassword: (body) =>
      apiFetch("/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
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
    categories: () => apiFetch("/transactions/categories"),
    paymentMethods: () => apiFetch("/transactions/payment-methods"),
    batchDelete: (ids) =>
      apiFetch("/transactions/batch/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids }),
      }),
    batchHardDelete: (ids) =>
      apiFetch("/transactions/batch/hard-delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids }),
      }),
    batchUpdate: (ids, data) =>
      apiFetch("/transactions/batch/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids, ...data }),
      }),
    exportCsv: (params) => {
      const qs = new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ""))
      );
      const token = Auth.getToken();
      // Use fetch to handle auth, then trigger download
      return fetch(API_BASE + "/transactions/export/csv?" + qs, {
        headers: token ? { "Authorization": `Bearer ${token}` } : {},
      }).then(res => {
        if (!res.ok) throw new Error("导出失败");
        return res.blob();
      }).then(blob => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url; a.download = "autocoin_export.csv";
        a.click(); URL.revokeObjectURL(url);
      });
    },
    exportExcel: (params) => {
      const qs = new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ""))
      );
      const token = Auth.getToken();
      return fetch(API_BASE + "/transactions/export/excel?" + qs, {
        headers: token ? { "Authorization": `Bearer ${token}` } : {},
      }).then(res => {
        if (!res.ok) throw new Error("导出失败");
        return res.blob();
      }).then(blob => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url; a.download = "autocoin_export.xlsx";
        a.click(); URL.revokeObjectURL(url);
      });
    },
  },
  dataManagement: {
    exportBackup: () => {
      const token = Auth.getToken();
      return fetch(API_BASE + "/data-management/backup/export", {
        headers: token ? { "Authorization": `Bearer ${token}` } : {},
      }).then(res => {
        if (!res.ok) throw new Error("备份失败");
        const disposition = res.headers.get("Content-Disposition") || "";
        const match = disposition.match(/filename="?([^"]+)"?/);
        const filename = match ? match[1] : "autocoin_full_backup.csv";
        return res.blob().then(blob => ({ blob, filename }));
      }).then(({ blob, filename }) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
      });
    },
    validateBackup: async (file) => {
      const formData = new FormData();
      formData.append("file", file);
      const token = Auth.getToken();
      const res = await fetch(API_BASE + "/data-management/backup/validate", {
        method: "POST",
        headers: token ? { "Authorization": `Bearer ${token}` } : {},
        body: formData,
      });
      if (!res.ok) {
        let msg = "数据错误，请检查上传的备份数据。";
        try { const j = await res.json(); msg = j.detail || msg; } catch (_) {}
        throw new Error(msg);
      }
      return res.json();
    },
    restoreBackup: async (file) => {
      const formData = new FormData();
      formData.append("file", file);
      const token = Auth.getToken();
      const res = await fetch(API_BASE + "/data-management/backup/restore", {
        method: "POST",
        headers: token ? { "Authorization": `Bearer ${token}` } : {},
        body: formData,
      });
      if (!res.ok) {
        let msg = "数据还原失败";
        try { const j = await res.json(); msg = j.detail || msg; } catch (_) {}
        throw new Error(msg);
      }
      return res.json();
    },
  },
  specialDataProcessing: {
    searchRefunds: () =>
      apiFetch("/special-data-processing/refunds/search", {
        method: "POST",
      }),
    confirmRefunds: (items) =>
      apiFetch("/special-data-processing/refunds/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items }),
      }),
    searchWealth: () =>
      apiFetch("/special-data-processing/wealth/search", {
        method: "POST",
      }),
    confirmWealth: (ids) =>
      apiFetch("/special-data-processing/wealth/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids }),
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
    preview: async (formData) => {
      const headers = {};
      const token = Auth.getToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(API_BASE + "/imports/preview", {
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
    previewCmbSecurities: async (formData) => {
      const headers = {};
      const token = Auth.getToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(API_BASE + "/imports/cmb-securities/preview", {
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
    previewIbkr: async (formData) => {
      const headers = {};
      const token = Auth.getToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(API_BASE + "/imports/ibkr/preview", {
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
    previewMoomoo: async (formData) => {
      const headers = {};
      const token = Auth.getToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(API_BASE + "/imports/moomoo/preview", {
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
    previewHsbcPulse: async (formData) => {
      const headers = {};
      const token = Auth.getToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(API_BASE + "/imports/hsbc-pulse/preview", {
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
    confirmFileImport: (filename, source, transactions) =>
      apiFetch("/imports/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename, source, transactions }),
      }),
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
    confirmImageImport: (transactions, filenames) =>
      apiFetch("/imports/image/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transactions, filenames }),
      }),
    checkDuplicates: (transactions) =>
      apiFetch("/imports/image/check-duplicates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transactions }),
      }),
    imageQuota: () => apiFetch("/imports/image/quota"),
  },
  rules: {
    list: () => apiFetch("/rules"),
    create: (body) =>
      apiFetch("/rules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    update: (id, body) =>
      apiFetch(`/rules/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    delete: (id) => apiFetch(`/rules/${id}`, { method: "DELETE" }),
    reclassify: () => apiFetch("/rules/reclassify", { method: "POST" }),
  },
  aliasRules: {
    list: () => apiFetch("/rules/aliases"),
    create: (body) =>
      apiFetch("/rules/aliases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    update: (id, body) =>
      apiFetch(`/rules/aliases/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    delete: (id) => apiFetch(`/rules/aliases/${id}`, { method: "DELETE" }),
    realias: () => apiFetch("/rules/aliases/realias", { method: "POST" }),
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
  brokerIncomeAnalysis: {
    getSources: () => apiFetch("/broker-income-analysis/preferences/sources"),
    saveSources: (sources) =>
      apiFetch("/broker-income-analysis/preferences/sources", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sources }),
      }),
    list: (params) =>
      apiFetch("/broker-income-analysis/transactions?" + new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ""))
      )),
    categories: (params) =>
      apiFetch("/broker-income-analysis/categories?" + new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ""))
      )),
    monthly: (params) =>
      apiFetch("/broker-income-analysis/monthly?" + new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ""))
      )),
    incomeBySource: (params) =>
      apiFetch("/broker-income-analysis/income-by-source?" + new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ""))
      )),
    incomeByProduct: (params) =>
      apiFetch("/broker-income-analysis/income-by-product?" + new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ""))
      )),
  },
  stockManagement: {
    lookup: (params) =>
      apiFetch("/stock-management/lookup?" + new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ""))
      )),
    create: (body) =>
      apiFetch("/stock-management/stocks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    summary: (params = {}) =>
      apiFetch("/stock-management/stocks/summary?" + new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ""))
      )),
    details: (market, stockId, params = {}) =>
      apiFetch(`/stock-management/stocks/${encodeURIComponent(market)}/${encodeURIComponent(stockId)}/details?` + new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ""))
      )),
    records: (market, stockId, params) =>
      apiFetch(`/stock-management/stocks/${encodeURIComponent(market)}/${encodeURIComponent(stockId)}/records?` + new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ""))
      )),
  },
  aiClassification: {
    getPreferences: () => apiFetch("/ai-classification/preferences"),
    savePreferences: (body) =>
      apiFetch("/ai-classification/preferences", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    classify: (body, signal) =>
      apiFetch("/ai-classification/classify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal,
      }),
    confirm: (body) =>
      apiFetch("/ai-classification/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
  },
};
