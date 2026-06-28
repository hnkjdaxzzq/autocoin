/* ===== Chart.js helpers ===== */
const PALETTE = [
  "#4f6ef7", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6",
  "#06b6d4", "#ec4899", "#10b981", "#f97316", "#6366f1",
  "#84cc16", "#e11d48", "#0ea5e9", "#d946ef", "#14b8a6",
];

function mergeChartOptions(base, extra = {}) {
  const merged = { ...base, ...extra };
  merged.plugins = { ...(base.plugins || {}), ...(extra.plugins || {}) };
  merged.scales = { ...(base.scales || {}), ...(extra.scales || {}) };
  Object.keys(merged.plugins).forEach((key) => {
    if (base.plugins?.[key] && extra.plugins?.[key]) {
      merged.plugins[key] = { ...base.plugins[key], ...extra.plugins[key] };
      if (base.plugins[key].callbacks || extra.plugins[key].callbacks) {
        merged.plugins[key].callbacks = {
          ...(base.plugins[key].callbacks || {}),
          ...(extra.plugins[key].callbacks || {}),
        };
      }
    }
  });
  return merged;
}

if (typeof Chart !== "undefined") {
  Chart.register({
    id: "valueLabels",
    afterDatasetsDraw(chart, _args, pluginOptions) {
      if (!pluginOptions || pluginOptions.display === false) return;
      const { ctx } = chart;
      const formatter = pluginOptions.formatter || ((value) => String(value));
      const color = typeof pluginOptions.color === "function"
        ? pluginOptions.color({ chart })
        : (pluginOptions.color || "#334155");
      const font = pluginOptions.font || "600 11px system-ui, -apple-system, BlinkMacSystemFont, sans-serif";
      const offset = pluginOptions.offset ?? 6;
      const lineHeight = pluginOptions.lineHeight || 14;

      ctx.save();
      ctx.fillStyle = color;
      ctx.font = font;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      chart.data.datasets.forEach((dataset, datasetIndex) => {
        const meta = chart.getDatasetMeta(datasetIndex);
        if (meta.hidden) return;
        meta.data.forEach((element, dataIndex) => {
          const rawValue = Array.isArray(dataset.data) ? dataset.data[dataIndex] : null;
          if (rawValue === null || rawValue === undefined || Number(rawValue) === 0) return;
          const label = formatter(rawValue, { chart, dataset, datasetIndex, dataIndex });
          if (!label) return;
          const lines = Array.isArray(label) ? label : String(label).split("\n");

          const drawLabel = (x, y) => {
            const startY = y - ((lines.length - 1) * lineHeight) / 2;
            lines.forEach((line, lineIndex) => {
              ctx.fillText(line, x, startY + lineIndex * lineHeight);
            });
          };

          const props = element.getProps(["x", "y", "base", "startAngle", "endAngle", "innerRadius", "outerRadius"], true);
          if (chart.config.type === "doughnut" || chart.config.type === "pie") {
            const angle = (props.startAngle + props.endAngle) / 2;
            const radius = (props.innerRadius + props.outerRadius) / 2;
            drawLabel(props.x + Math.cos(angle) * radius, props.y + Math.sin(angle) * radius);
            return;
          }

          const y = chart.config.type === "bar"
            ? props.y + (props.y < props.base ? -offset : offset)
            : props.y - offset;
          drawLabel(props.x, y);
        });
      });

      ctx.restore();
    },
  });
}

const Charts = {
  _instances: {},

  valueLabelOptions(overrides = {}) {
    return mergeChartOptions({
      layout: { padding: { top: 18, right: 16, bottom: 4, left: 16 } },
      plugins: {
        valueLabels: {
          display: true,
          color: () => chartAmountColor(),
          formatter: (value) => fmtChartMoney(value),
        },
        tooltip: {
          callbacks: {
            label: (context) => {
              const label = context.dataset?.label || context.label || "";
              const value = context.parsed?.y ?? context.parsed ?? context.raw;
              return `${label ? `${label}: ` : ""}${fmtMoney(value)}`;
            },
          },
        },
      },
    }, overrides);
  },

  destroy(key) {
    if (Charts._instances[key]) {
      Charts._instances[key].destroy();
      delete Charts._instances[key];
    }
  },

  refreshAll() {
    Object.values(Charts._instances).forEach((chart) => {
      if (chart) chart.update("none");
    });
  },

  createBar(key, ctx, labels, datasets, opts = {}) {
    Charts.destroy(key);
    const options = Charts.valueLabelOptions(mergeChartOptions({
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "top" } },
      scales: { y: { beginAtZero: true } },
    }, opts));
    Charts._instances[key] = new Chart(ctx, {
      type: "bar",
      data: { labels, datasets },
      options,
    });
    return Charts._instances[key];
  },

  createLine(key, ctx, labels, datasets, opts = {}) {
    Charts.destroy(key);
    const options = Charts.valueLabelOptions(mergeChartOptions({
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "top" } },
      tension: 0.3,
    }, opts));
    Charts._instances[key] = new Chart(ctx, {
      type: "line",
      data: { labels, datasets },
      options,
    });
    return Charts._instances[key];
  },

  createDonut(key, ctx, labels, data, opts = {}) {
    Charts.destroy(key);
    const options = Charts.valueLabelOptions(mergeChartOptions({
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "right" } },
    }, opts));
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
      options,
    });
    return Charts._instances[key];
  },
};

/* ===== Formatting helpers ===== */
function fmtMoney(n) {
  return "¥" + Number(n).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtMoneyInt(n) {
  return "¥" + Number(n).toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function fmtChartMoney(n) {
  const amount = Number(n) || 0;
  const abs = Math.abs(amount);
  if (abs >= 10000) {
    const value = amount / 10000;
    return `¥${value.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}万`;
  }
  return fmtMoneyInt(amount);
}

function chartAmountColor() {
  const bg = getComputedStyle(document.documentElement).getPropertyValue("--card-bg").trim();
  const match = bg.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (!match) {
    return document.documentElement.getAttribute("data-theme") === "dark" ? "#fff" : "#000";
  }
  const hex = match[1].length === 3
    ? match[1].split("").map((c) => c + c).join("")
    : match[1];
  const r = parseInt(hex.slice(0, 2), 16);
  const g = parseInt(hex.slice(2, 4), 16);
  const b = parseInt(hex.slice(4, 6), 16);
  const luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  return luminance < 0.45 ? "#fff" : "#000";
}

function dateRangeDays(start, end) {
  const parseDate = (value) => {
    if (!value) return null;
    const parts = String(value).split("-").map(Number);
    if (parts.length !== 3 || parts.some(Number.isNaN)) return null;
    return new Date(parts[0], parts[1] - 1, parts[2]);
  };
  const startDate = parseDate(start);
  const endDate = parseDate(end);
  if (!startDate || !endDate) return 1;
  const msPerDay = 24 * 60 * 60 * 1000;
  return Math.max(1, Math.floor((endDate - startDate) / msPerDay) + 1);
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
