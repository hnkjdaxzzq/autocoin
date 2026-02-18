/* ===== Chart.js helpers ===== */
const PALETTE = [
  "#4f6ef7", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6",
  "#06b6d4", "#ec4899", "#10b981", "#f97316", "#6366f1",
  "#84cc16", "#e11d48", "#0ea5e9", "#d946ef", "#14b8a6",
];

const Charts = {
  _instances: {},

  destroy(key) {
    if (Charts._instances[key]) {
      Charts._instances[key].destroy();
      delete Charts._instances[key];
    }
  },

  createBar(key, ctx, labels, datasets, opts = {}) {
    Charts.destroy(key);
    Charts._instances[key] = new Chart(ctx, {
      type: "bar",
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "top" } },
        scales: { y: { beginAtZero: true } },
        ...opts,
      },
    });
    return Charts._instances[key];
  },

  createLine(key, ctx, labels, datasets, opts = {}) {
    Charts.destroy(key);
    Charts._instances[key] = new Chart(ctx, {
      type: "line",
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "top" } },
        tension: 0.3,
        ...opts,
      },
    });
    return Charts._instances[key];
  },

  createDonut(key, ctx, labels, data, opts = {}) {
    Charts.destroy(key);
    Charts._instances[key] = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels,
        datasets: [{
          data,
          backgroundColor: PALETTE.slice(0, data.length),
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "right" } },
        ...opts,
      },
    });
    return Charts._instances[key];
  },
};

/* ===== Formatting helpers ===== */
function fmtMoney(n) {
  return "¥" + Number(n).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtDate(s) {
  if (!s) return "";
  return s.replace("T", " ").slice(0, 16);
}

function directionBadge(dir) {
  const map = { income: ["badge-income", "收入"], expense: ["badge-expense", "支出"], neutral: ["badge-neutral", "不计"] };
  const [cls, label] = map[dir] || ["badge-neutral", dir];
  return `<span class="badge ${cls}">${label}</span>`;
}

function showError(container, msg) {
  container.innerHTML = `<div class="empty" style="color:#ef4444">⚠️ ${msg}</div>`;
}
