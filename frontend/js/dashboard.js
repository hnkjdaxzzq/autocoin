/* ===== Dashboard page ===== */
const Dashboard = {
  render(container) {
    const now = new Date();
    const year = now.getFullYear();
    const yearStart = `${year}-01-01`;
    const today = Dashboard._formatLocalDate(now);

    container.innerHTML = `
      <div class="page-header">
        <div style="display:flex;gap:14px;flex-wrap:wrap;align-items:center">
          <h1 class="page-title">概览</h1>
          <div class="title-date-filter">
            <input type="date" id="dash-start" value="${yearStart}"> —
            <input type="date" id="dash-end" value="${today}">
          </div>
        </div>
      </div>

      <div class="summary-grid" id="summary-cards">
        <div class="loading">加载中...</div>
      </div>

      <div class="charts-grid">
        <div class="card">
          <div class="card-title">月度收支趋势（${year}年）</div>
          <div class="chart-canvas-wrap"><canvas id="monthly-chart"></canvas></div>
        </div>
        <div class="card">
          <div class="card-title">支出分类占比</div>
          <div class="chart-canvas-wrap"><canvas id="category-chart"></canvas></div>
        </div>
      </div>

      <div class="card" style="margin-bottom:0">
        <div class="card-title">最近账单（当前筛选范围）</div>
        <div id="recent-tx"><div class="loading">加载中...</div></div>
      </div>
    `;

    container.querySelectorAll("#dash-start, #dash-end").forEach(input => {
      input.addEventListener("change", () => {
        Dashboard._reload(container);
      });
    });

    Dashboard._loadAll(container);
  },

  _setLoading(container) {
    const summary = container.querySelector("#summary-cards");
    const recent = container.querySelector("#recent-tx");
    if (summary) summary.innerHTML = `<div class="loading">加载中...</div>`;
    if (recent) recent.innerHTML = `<div class="loading">加载中...</div>`;
  },

  _reload(container) {
    Dashboard._setLoading(container);
    Dashboard._loadAll(container);
  },

  _formatLocalDate(date) {
    return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`;
  },

  async _loadAll(container) {
    const start = container.querySelector("#dash-start").value;
    const end = container.querySelector("#dash-end").value;
    const year = new Date().getFullYear();

    // Parallel fetch
    const [summary, monthly, category, recent] = await Promise.allSettled([
      API.stats.summary({ start_date: start, end_date: end }),
      API.stats.monthly(year),
      API.stats.category({ start_date: start, end_date: end, direction: "expense" }),
      API.transactions.list({ start_date: start, end_date: end, page: 1, page_size: 10 }),
    ]);

    if (summary.status === "fulfilled") {
      Dashboard._renderSummary(container, summary.value);
    }
    if (monthly.status === "fulfilled") {
      Dashboard._renderMonthly(container, monthly.value, year);
    }
    if (category.status === "fulfilled") {
      Dashboard._renderCategory(container, category.value);
    }
    if (recent.status === "fulfilled") {
      Dashboard._renderRecent(container, recent.value.items);
    }
  },

  _renderSummary(container, data) {
    const cards = container.querySelector("#summary-cards");
    const netClass = data.net >= 0 ? "positive" : "negative";
    const days = dateRangeDays(
      container.querySelector("#dash-start").value,
      container.querySelector("#dash-end").value
    );
    const monthlyIncomeAvg = data.total_income / days * 30;
    const monthlyExpenseAvg = data.total_expense / days * 30;
    cards.innerHTML = `
      <div class="summary-card">
        <div class="label">总收入</div>
        <div class="value income">${fmtMoneyInt(data.total_income)}</div>
        <div style="font-size:12px;color:var(--text-muted);margin-top:6px">${data.income_count} 笔交易</div>
      </div>
      <div class="summary-card">
        <div class="label">总支出</div>
        <div class="value expense">${fmtMoneyInt(data.total_expense)}</div>
        <div style="font-size:12px;color:var(--text-muted);margin-top:6px">${data.expense_count} 笔交易</div>
      </div>
      <div class="summary-card">
        <div class="label">结余</div>
        <div class="value net ${netClass}">${fmtMoneyInt(data.net)}</div>
        <div style="font-size:12px;color:var(--text-muted);margin-top:6px">共 ${data.transaction_count} 笔</div>
      </div>
      <div class="summary-card">
        <div class="label">总笔数</div>
        <div class="value" style="color:var(--primary)">${data.transaction_count}</div>
        <div style="font-size:12px;color:var(--text-muted);margin-top:6px">当前筛选范围</div>
      </div>
      <div class="summary-card">
        <div class="label">月均收入</div>
        <div class="value income">${fmtMoneyInt(monthlyIncomeAvg)}</div>
        <div style="font-size:12px;color:var(--text-muted);margin-top:6px">按 ${days} 天折算</div>
      </div>
      <div class="summary-card">
        <div class="label">月均支出</div>
        <div class="value expense">${fmtMoneyInt(monthlyExpenseAvg)}</div>
        <div style="font-size:12px;color:var(--text-muted);margin-top:6px">按 ${days} 天折算</div>
      </div>
      <div class="summary-card">
        <div class="label">月均结余</div>
        <div class="value net ${monthlyIncomeAvg - monthlyExpenseAvg >= 0 ? "positive" : "negative"}">${fmtMoneyInt(monthlyIncomeAvg - monthlyExpenseAvg)}</div>
        <div style="font-size:12px;color:var(--text-muted);margin-top:6px">按 ${days} 天折算</div>
      </div>
    `;
  },

  _renderMonthly(container, data, year) {
    const ctx = container.querySelector("#monthly-chart");
    if (!ctx) return;
    const labels = data.months.map(m => `${m.month}月`);
    Charts.createBar("monthly", ctx, labels, [
      {
        label: "支出",
        data: data.months.map(m => m.expense),
        backgroundColor: "rgba(34,197,94,0.7)",
      },
      {
        label: "收入",
        data: data.months.map(m => m.income),
        backgroundColor: "rgba(239,68,68,0.7)",
      },
    ]);
  },

  _renderCategory(container, data) {
    const ctx = container.querySelector("#category-chart");
    if (!ctx || !data.items.length) return;
    const top = data.items.slice(0, 10);
    Charts.createDonut(
      "category",
      ctx,
      top.map(i => `${i.category || "其他"} (${i.percentage}%)`),
      top.map(i => i.amount)
    );
  },

  _renderRecent(container, items) {
    const el = container.querySelector("#recent-tx");
    if (!items.length) {
      el.innerHTML = `<div class="empty">该时间段内没有交易记录</div>`;
      return;
    }
    el.innerHTML = `
      <table>
        <thead>
          <tr><th>时间</th><th>对方</th><th>商品</th><th>方向</th><th>金额</th><th>分类</th></tr>
        </thead>
        <tbody>
          ${items.map(tx => `
            <tr>
              <td style="white-space:nowrap">${fmtDate(tx.transaction_time)}</td>
              <td style="max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${tx.counterparty || "—"}</td>
              <td style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${tx.product || "—"}</td>
              <td>${directionBadge(tx.direction)}</td>
              <td style="font-weight:600;color:${tx.direction === "income" ? "var(--income)" : tx.direction === "expense" ? "var(--expense)" : "inherit"}">
                ${fmtMoney(tx.amount)}
              </td>
              <td>${tx.category || tx.transaction_type || "—"}</td>
            </tr>`).join("")}
        </tbody>
      </table>
    `;
  },
};
