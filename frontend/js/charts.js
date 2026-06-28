/* ===== Chart.js helpers ===== */
const PALETTE = [
  "#4f6ef7", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6",
  "#06b6d4", "#ec4899", "#10b981", "#f97316", "#6366f1",
  "#84cc16", "#e11d48", "#0ea5e9", "#d946ef", "#14b8a6",
];

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
