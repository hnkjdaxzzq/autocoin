/* ===== BrokerIncomeAnalysis page ===== */
const BrokerIncomeAnalysis = {
  _state: {
    page: 1,
    page_size: 15,
    total: 0,
    total_pages: 1,
    filters: {},
    selectedIds: new Set(),
    categories: [],
    selectedSources: [],
  },
  _sourceOptions: [
    "alipay",
    "wechat",
    "manual",
    "image",
    "招商证券",
    "盈透IBKR",
    "MOOMOO",
    "汇丰PULSE",
  ],
  _defaultSelectedSources: ["招商证券", "盈透IBKR", "MOOMOO", "汇丰PULSE"],

  render(container) {
    const now = new Date();
    const today = BrokerIncomeAnalysis._formatLocalDate(now);
    const yearStart = `${now.getFullYear()}-01-01`;
    const defaultTime = `${today}T${String(now.getHours()).padStart(2,"0")}:${String(now.getMinutes()).padStart(2,"0")}`;

    container.innerHTML = `
      <div class="page-header">
        <div style="display:flex;gap:14px;flex-wrap:wrap;align-items:center">
          <h1 class="page-title">券商收入分析</h1>
          <label class="title-date-filter">日期范围
            <input type="date" id="f-start" value="${yearStart}" placeholder="开始日期">
            <span style="color:#94a3b8">—</span>
            <input type="date" id="f-end" value="${today}" placeholder="结束日期">
          </label>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
          <div class="export-dropdown" id="export-dropdown">
            <button class="export-dropdown-btn" id="btn-export-toggle" type="button">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              导出
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="width:12px;height:12px"><polyline points="6 9 12 15 18 9"/></svg>
            </button>
            <div class="export-dropdown-menu" id="export-menu">
              <button type="button" id="btn-export-csv">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                导出为 CSV
              </button>
              <button type="button" id="btn-export-excel">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
                导出为 Excel
              </button>
            </div>
          </div>
          <button class="btn btn-primary" id="btn-toggle-form">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="width:15px;height:15px"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            手动记账
          </button>
        </div>
      </div>

      <!-- Manual entry form (hidden by default) -->
      <div class="card" id="manual-form-wrap" style="display:none;margin-bottom:16px">
        <div class="card-title">手动录入账单</div>
        <form id="manual-form" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin-top:12px">
          <label class="form-field">
            <span class="form-label">交易时间 *</span>
            <input type="datetime-local" id="m-time" value="${defaultTime}" required>
          </label>
          <label class="form-field">
            <span class="form-label">收支方向 *</span>
            <select id="m-direction" required>
              <option value="expense">支出</option>
              <option value="income">收入</option>
              <option value="neutral">不计收支</option>
            </select>
          </label>
          <label class="form-field">
            <span class="form-label">金额 *</span>
            <input type="number" id="m-amount" step="0.01" min="0" placeholder="0.00" required>
          </label>
          <label class="form-field">
            <span class="form-label">分类</span>
            <input type="text" id="m-category" list="category-datalist" placeholder="如：餐饮美食、交通出行">
            <datalist id="category-datalist"></datalist>
          </label>
          <label class="form-field">
            <span class="form-label">交易对方</span>
            <input type="text" id="m-counterparty" placeholder="如：美团、滴滴出行">
          </label>
          <label class="form-field">
            <span class="form-label">商品说明</span>
            <input type="text" id="m-product" placeholder="描述">
          </label>
          <label class="form-field">
            <span class="form-label">支付方式</span>
            <input type="text" id="m-payment" placeholder="如：现金、银行卡">
          </label>
          <label class="form-field">
            <span class="form-label">备注</span>
            <input type="text" id="m-remark" placeholder="备注信息">
          </label>
          <div style="display:flex;align-items:flex-end;gap:8px">
            <button type="submit" class="btn btn-primary" id="btn-submit-manual">保存</button>
            <button type="button" class="btn btn-ghost" id="btn-cancel-manual">取消</button>
          </div>
        </form>
        <div id="manual-result" style="margin-top:10px"></div>
      </div>

      <div class="filter-bar">
        <label>方向
          <select id="f-direction">
            <option value="">全部</option>
            <option value="income">收入</option>
            <option value="expense">支出</option>
            <option value="neutral">不计收支</option>
          </select>
        </label>
        <div class="multi-source-filter" id="broker-source-filter">
          <button type="button" class="multi-source-toggle" id="f-source-toggle">
            <span>来源</span>
            <strong id="f-source-summary">加载中...</strong>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="6 9 12 15 18 9"/></svg>
          </button>
          <div class="multi-source-menu" id="f-source-menu">
            ${BrokerIncomeAnalysis._sourceOptions.map(source => `
              <label class="multi-source-option">
                <input type="checkbox" class="f-source-check" value="${source}">
                <span>${source}</span>
              </label>
            `).join("")}
          </div>
        </div>
        <label>分类
          <select id="f-category">
            <option value="">全部</option>
          </select>
        </label>
        <input type="text" id="f-search" placeholder="搜索对方/商品/备注…" style="min-width:180px">
        <button class="btn btn-primary" id="btn-search">搜索</button>
        <button class="btn btn-ghost" id="btn-reset">重置</button>
      </div>

      <div class="summary-grid" id="tx-summary"></div>

      <div class="card" style="margin-bottom:16px">
        <div class="card-title">月度明细列表</div>
        <div id="broker-monthly-table"></div>
      </div>

      <div class="broker-chart-stack">
        <div class="card">
          <div class="card-title">净收入</div>
          <div class="chart-canvas-wrap"><canvas id="broker-net-line"></canvas></div>
        </div>
        <div class="card">
          <div class="card-title" id="broker-monthly-title">月度收支</div>
          <div class="chart-canvas-wrap"><canvas id="broker-monthly-bar"></canvas></div>
        </div>
        <div class="card">
          <div class="card-title">分券商统计</div>
          <div class="chart-canvas-wrap" id="broker-source-chart-wrap"><canvas id="broker-source-donut"></canvas></div>
        </div>
        <div class="card">
          <div class="card-title">分股票统计</div>
          <div class="chart-canvas-wrap" id="broker-product-chart-wrap"><canvas id="broker-product-bar"></canvas></div>
        </div>
      </div>

      <!-- Batch action bar (hidden until selection) -->
      <div class="batch-bar" id="batch-bar" style="display:none">
        <span id="batch-count">已选 0 条</span>
        <select id="batch-category" style="font-size:13px;padding:4px 8px;border:1px solid var(--border);border-radius:6px">
          <option value="">批量改分类…</option>
        </select>
        <button class="btn btn-ghost btn-sm" id="btn-batch-category">应用分类</button>
        <button class="btn btn-danger btn-sm" id="btn-batch-delete">批量删除</button>
        <button class="btn btn-ghost btn-sm" id="btn-batch-clear">取消选择</button>
      </div>

      <div class="table-wrap" id="tx-table-wrap">
        <div class="loading">加载中...</div>
      </div>
    `;

    BrokerIncomeAnalysis._state.page = 1;
    BrokerIncomeAnalysis._state.selectedIds = new Set();
    BrokerIncomeAnalysis._bindFilters(container);
    BrokerIncomeAnalysis._bindManualForm(container);
    BrokerIncomeAnalysis._bindExport(container);
    BrokerIncomeAnalysis._bindBatch(container);
    BrokerIncomeAnalysis._loadCategories(container);
    BrokerIncomeAnalysis._loadSourcePreference(container);
  },

  async _loadSourcePreference(container) {
    try {
      const res = await API.brokerIncomeAnalysis.getSources();
      const saved = Array.isArray(res.sources) ? res.sources : [];
      BrokerIncomeAnalysis._state.selectedSources = saved.length ? saved : [...BrokerIncomeAnalysis._defaultSelectedSources];
    } catch (_) {
      BrokerIncomeAnalysis._state.selectedSources = [...BrokerIncomeAnalysis._defaultSelectedSources];
    }
    BrokerIncomeAnalysis._syncSourceChecks(container);
    BrokerIncomeAnalysis._loadCategories(container);
    BrokerIncomeAnalysis._load(container);
  },

  _syncSourceChecks(container) {
    const selected = new Set(BrokerIncomeAnalysis._state.selectedSources);
    container.querySelectorAll(".f-source-check").forEach(check => {
      check.checked = selected.has(check.value);
    });
    BrokerIncomeAnalysis._updateSourceSummary(container);
  },

  _updateSourceSummary(container) {
    const el = container.querySelector("#f-source-summary");
    const selected = BrokerIncomeAnalysis._state.selectedSources;
    if (!selected.length) {
      el.textContent = "未选择";
    } else if (selected.length === BrokerIncomeAnalysis._sourceOptions.length) {
      el.textContent = "全部";
    } else if (selected.length <= 2) {
      el.textContent = selected.join("、");
    } else {
      el.textContent = `${selected.slice(0, 2).join("、")} 等 ${selected.length} 项`;
    }
  },

  async _loadCategories(container) {
    try {
      const source = BrokerIncomeAnalysis._state.selectedSources.length
        ? BrokerIncomeAnalysis._state.selectedSources.join(",")
        : "__none__";
      const res = await API.brokerIncomeAnalysis.categories({ source });
      BrokerIncomeAnalysis._state.categories = res.categories || [];
      // Populate datalist and batch dropdown
      const dl = container.querySelector("#category-datalist");
      const batchSel = container.querySelector("#batch-category");
      const filterSel = container.querySelector("#f-category");
      if (dl) {
        dl.innerHTML = BrokerIncomeAnalysis._state.categories.map(c => `<option value="${c}">`).join("");
      }
      if (batchSel) {
        batchSel.innerHTML = '<option value="">批量改分类…</option>' +
          BrokerIncomeAnalysis._state.categories.map(c => `<option value="${c}">${c}</option>`).join("");
      }
      if (filterSel) {
        const current = filterSel.value;
        filterSel.innerHTML = '<option value="">全部</option>' +
          BrokerIncomeAnalysis._state.categories.map(c => `<option value="${c}">${c}</option>`).join("");
        filterSel.value = current;
      }
    } catch (_) {}
  },

  _bindExport(container) {
    // Dropdown toggle
    const toggleBtn = container.querySelector("#btn-export-toggle");
    const menu = container.querySelector("#export-menu");
    toggleBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      menu.classList.toggle("show");
    });
    document.addEventListener("click", () => menu.classList.remove("show"));
    menu.addEventListener("click", (e) => e.stopPropagation());

    container.querySelector("#btn-export-csv").addEventListener("click", () => {
      menu.classList.remove("show");
      const filters = BrokerIncomeAnalysis._getFilters(container);
      API.transactions.exportCsv(filters).catch(e => alert("导出失败: " + e.message));
    });
    container.querySelector("#btn-export-excel").addEventListener("click", () => {
      menu.classList.remove("show");
      const filters = BrokerIncomeAnalysis._getFilters(container);
      API.transactions.exportExcel(filters).catch(e => alert("导出失败: " + e.message));
    });
  },

  _bindBatch(container) {
    container.querySelector("#btn-batch-delete").addEventListener("click", async () => {
      const ids = Array.from(BrokerIncomeAnalysis._state.selectedIds);
      if (!ids.length) return;
      if (!confirm(`确定删除选中的 ${ids.length} 条记录？`)) return;
      try {
        await API.transactions.batchDelete(ids);
        BrokerIncomeAnalysis._state.selectedIds.clear();
        BrokerIncomeAnalysis._load(container);
      } catch (e) { alert("批量删除失败: " + e.message); }
    });
    container.querySelector("#btn-batch-category").addEventListener("click", async () => {
      const ids = Array.from(BrokerIncomeAnalysis._state.selectedIds);
      const cat = container.querySelector("#batch-category").value;
      if (!ids.length || !cat) { alert("请先选择记录和分类"); return; }
      try {
        await API.transactions.batchUpdate(ids, { category: cat });
        BrokerIncomeAnalysis._state.selectedIds.clear();
        BrokerIncomeAnalysis._load(container);
      } catch (e) { alert("批量更新失败: " + e.message); }
    });
    container.querySelector("#btn-batch-clear").addEventListener("click", () => {
      BrokerIncomeAnalysis._state.selectedIds.clear();
      BrokerIncomeAnalysis._updateBatchBar(container);
      container.querySelectorAll(".tx-row-check").forEach(c => c.checked = false);
      const sa = container.querySelector("#tx-select-all");
      if (sa) sa.checked = false;
    });
  },

  _updateBatchBar(container) {
    const bar = container.querySelector("#batch-bar");
    const cnt = BrokerIncomeAnalysis._state.selectedIds.size;
    bar.style.display = cnt > 0 ? "flex" : "none";
    container.querySelector("#batch-count").textContent = `已选 ${cnt} 条`;
  },

  _bindFilters(container) {
    const sourceFilter = container.querySelector("#broker-source-filter");
    const sourceToggle = container.querySelector("#f-source-toggle");
    const sourceMenu = container.querySelector("#f-source-menu");

    sourceToggle.addEventListener("click", (e) => {
      e.stopPropagation();
      sourceMenu.classList.toggle("show");
    });
    sourceMenu.addEventListener("click", (e) => e.stopPropagation());
    document.addEventListener("click", (e) => {
      if (!sourceFilter.contains(e.target)) sourceMenu.classList.remove("show");
    });
    container.querySelectorAll(".f-source-check").forEach(check => {
      check.addEventListener("change", async () => {
        BrokerIncomeAnalysis._state.selectedSources = Array.from(container.querySelectorAll(".f-source-check:checked"))
          .map(item => item.value);
        BrokerIncomeAnalysis._updateSourceSummary(container);
        BrokerIncomeAnalysis._state.page = 1;
        try {
          await API.brokerIncomeAnalysis.saveSources(BrokerIncomeAnalysis._state.selectedSources);
        } catch (e) {
          alert("保存来源筛选失败: " + e.message);
        }
        BrokerIncomeAnalysis._loadCategories(container);
        BrokerIncomeAnalysis._load(container);
      });
    });

    container.querySelector("#btn-search").addEventListener("click", () => {
      BrokerIncomeAnalysis._state.page = 1;
      BrokerIncomeAnalysis._load(container);
    });

    container.querySelector("#btn-reset").addEventListener("click", () => {
      const now = new Date();
      container.querySelector("#f-start").value = `${now.getFullYear()}-01-01`;
      container.querySelector("#f-end").value = BrokerIncomeAnalysis._formatLocalDate(now);
      container.querySelector("#f-direction").value = "";
      container.querySelector("#f-category").value = "";
      container.querySelector("#f-search").value = "";
      BrokerIncomeAnalysis._state.selectedSources = [...BrokerIncomeAnalysis._defaultSelectedSources];
      BrokerIncomeAnalysis._syncSourceChecks(container);
      API.brokerIncomeAnalysis.saveSources(BrokerIncomeAnalysis._state.selectedSources)
        .catch(e => alert("保存来源筛选失败: " + e.message));
      BrokerIncomeAnalysis._loadCategories(container);
      BrokerIncomeAnalysis._state.page = 1;
      BrokerIncomeAnalysis._load(container);
    });

    // Search on Enter key
    container.querySelector("#f-search").addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        BrokerIncomeAnalysis._state.page = 1;
        BrokerIncomeAnalysis._load(container);
      }
    });
  },

  _formatLocalDate(date) {
    return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`;
  },

  _bindManualForm(container) {
    const toggleBtn = container.querySelector("#btn-toggle-form");
    const formWrap = container.querySelector("#manual-form-wrap");
    const form = container.querySelector("#manual-form");

    toggleBtn.addEventListener("click", () => {
      const visible = formWrap.style.display !== "none";
      formWrap.style.display = visible ? "none" : "block";
      toggleBtn.textContent = visible ? "+ 手动记账" : "- 收起表单";
    });

    container.querySelector("#btn-cancel-manual").addEventListener("click", () => {
      formWrap.style.display = "none";
      toggleBtn.textContent = "+ 手动记账";
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const resultEl = container.querySelector("#manual-result");
      const submitBtn = container.querySelector("#btn-submit-manual");

      const timeVal = container.querySelector("#m-time").value;
      const body = {
        transaction_time: timeVal.replace("T", " ") + ":00",
        direction: container.querySelector("#m-direction").value,
        amount: parseFloat(container.querySelector("#m-amount").value),
        category: container.querySelector("#m-category").value.trim(),
        counterparty: container.querySelector("#m-counterparty").value.trim(),
        product: container.querySelector("#m-product").value.trim(),
        payment_method: container.querySelector("#m-payment").value.trim(),
        remark: container.querySelector("#m-remark").value.trim(),
      };

      submitBtn.disabled = true;
      submitBtn.textContent = "保存中...";

      try {
        await API.transactions.create(body);
        resultEl.innerHTML = `<span style="color:var(--income);font-size:13px">✅ 录入成功！</span>`;
        // Reset form fields except time
        container.querySelector("#m-amount").value = "";
        container.querySelector("#m-category").value = "";
        container.querySelector("#m-counterparty").value = "";
        container.querySelector("#m-product").value = "";
        container.querySelector("#m-payment").value = "";
        container.querySelector("#m-remark").value = "";
        // Refresh list
        BrokerIncomeAnalysis._state.page = 1;
        BrokerIncomeAnalysis._load(container);
        setTimeout(() => { resultEl.innerHTML = ""; }, 3000);
      } catch (err) {
        resultEl.innerHTML = `<span style="color:var(--expense);font-size:13px">❌ ${err.message}</span>`;
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "保存";
      }
    });
  },

  _getFilters(container) {
    return {
      start_date: container.querySelector("#f-start").value || "",
      end_date: container.querySelector("#f-end").value || "",
      direction: container.querySelector("#f-direction").value || "",
      source: BrokerIncomeAnalysis._state.selectedSources.length
        ? BrokerIncomeAnalysis._state.selectedSources.join(",")
        : "__none__",
      category: container.querySelector("#f-category").value || "",
      search: container.querySelector("#f-search").value || "",
    };
  },

  async _load(container) {
    const wrap = container.querySelector("#tx-table-wrap");
    wrap.innerHTML = `<div class="loading">加载中...</div>`;
    const filters = BrokerIncomeAnalysis._getFilters(container);
    BrokerIncomeAnalysis._loadAnalysis(container, filters);
    try {
      const data = await API.brokerIncomeAnalysis.list({
        ...filters,
        page: BrokerIncomeAnalysis._state.page,
        page_size: BrokerIncomeAnalysis._state.page_size,
      });
      BrokerIncomeAnalysis._state.total = data.total;
      BrokerIncomeAnalysis._state.total_pages = data.total_pages;
      BrokerIncomeAnalysis._renderSummary(container, data.summary);
      BrokerIncomeAnalysis._render(wrap, data, container);
    } catch (err) {
      showError(wrap, err.message);
    }
  },

  async _loadAnalysis(container, filters) {
    container.querySelector("#broker-monthly-title").textContent =
      `月度收支（${filters.start_date || "不限"} 至 ${filters.end_date || "不限"}）`;
    try {
      const data = await API.brokerIncomeAnalysis.monthly(filters);
      const months = data.months || [];
      const labels = months.map(m => m.month);
      Charts.createLine("broker-net-line", container.querySelector("#broker-net-line"), labels, [
        {
          label: "净收入",
          data: months.map(m => m.net),
          borderColor: "#4f6ef7",
          backgroundColor: "rgba(79,110,247,0.1)",
          fill: true,
          pointBackgroundColor: months.map(m => m.net >= 0 ? "#22c55e" : "#ef4444"),
        },
      ], BrokerIncomeAnalysis._chartValueOptions());
      Charts.createBar("broker-monthly-bar", container.querySelector("#broker-monthly-bar"), labels, [
        { label: "支出", data: months.map(m => m.expense), backgroundColor: "rgba(239,68,68,0.75)" },
        { label: "收入", data: months.map(m => m.income), backgroundColor: "rgba(34,197,94,0.75)" },
      ], BrokerIncomeAnalysis._chartValueOptions());
      BrokerIncomeAnalysis._renderMonthlyTable(container, months);
    } catch (err) {
      showError(container.querySelector("#broker-monthly-table"), err.message);
    }

    BrokerIncomeAnalysis._loadSourceChart(container, filters);
    BrokerIncomeAnalysis._loadProductChart(container, filters);
  },

  _renderMonthlyTable(container, months) {
    const el = container.querySelector("#broker-monthly-table");
    if (!months.length) {
      el.innerHTML = `<div class="empty">暂无数据</div>`;
      return;
    }

    const totalIncome = months.reduce((s, m) => s + m.income, 0);
    const totalExpense = months.reduce((s, m) => s + m.expense, 0);
    const totalNet = totalIncome - totalExpense;
    let cumulative = 0;
    const cumulativeData = months.map(m => {
      cumulative += m.net;
      return cumulative;
    });

    el.innerHTML = `
      <table>
        <thead>
          <tr><th>月份</th><th>收入</th><th>支出</th><th>月结余</th><th>累计结余</th><th>笔数</th></tr>
        </thead>
        <tbody>
          ${months.map((m, i) => `
            <tr>
              <td>${m.month}</td>
              <td style="color:var(--income)">${fmtMoney(m.income)}</td>
              <td style="color:var(--expense)">${fmtMoney(m.expense)}</td>
              <td style="font-weight:600;color:${m.net >= 0 ? "var(--income)" : "var(--expense)"}">
                ${fmtMoney(m.net)}
              </td>
              <td style="font-weight:600;color:${cumulativeData[i] >= 0 ? "var(--income)" : "var(--expense)"}">
                ${fmtMoney(cumulativeData[i])}
              </td>
              <td>${m.count}</td>
            </tr>`).join("")}
          <tr style="font-weight:700;border-top:2px solid var(--border)">
            <td>合计</td>
            <td style="color:var(--income)">${fmtMoney(totalIncome)}</td>
            <td style="color:var(--expense)">${fmtMoney(totalExpense)}</td>
            <td style="color:${totalNet >= 0 ? "var(--income)" : "var(--expense)"}">${fmtMoney(totalNet)}</td>
            <td style="color:${totalNet >= 0 ? "var(--income)" : "var(--expense)"}">${fmtMoney(totalNet)}</td>
            <td>${months.reduce((s, m) => s + m.count, 0)}</td>
          </tr>
        </tbody>
      </table>
    `;
  },

  async _loadSourceChart(container, filters) {
    const wrap = container.querySelector("#broker-source-chart-wrap");
    try {
      const data = await API.brokerIncomeAnalysis.incomeBySource(filters);
      const items = data.items || [];
      if (!items.length) {
        Charts.destroy("broker-source-donut");
        wrap.innerHTML = `<div class="empty">暂无收入数据</div>`;
        return;
      }
      wrap.innerHTML = `<canvas id="broker-source-donut"></canvas>`;
      Charts.createDonut(
        "broker-source-donut",
        container.querySelector("#broker-source-donut"),
        items.map(item => `${item.label} ${item.percentage}% ${fmtMoney(item.amount)}`),
        items.map(item => item.amount),
        BrokerIncomeAnalysis._chartValueOptions({
          plugins: {
            legend: { position: "right" },
            valueLabels: {
              display: true,
              formatter: (value, context) => {
                const item = items[context.dataIndex];
                return [
                  item.label,
                  `${item.percentage}%`,
                  BrokerIncomeAnalysis._formatCompactMoney(value),
                ];
              },
              lineHeight: 15,
            },
          },
        })
      );
    } catch (err) {
      showError(wrap, err.message);
    }
  },

  async _loadProductChart(container, filters) {
    const wrap = container.querySelector("#broker-product-chart-wrap");
    try {
      const data = await API.brokerIncomeAnalysis.incomeByProduct(filters);
      const items = (data.items || []).slice(0, 20);
      if (!items.length) {
        Charts.destroy("broker-product-bar");
        wrap.innerHTML = `<div class="empty">暂无收入数据</div>`;
        return;
      }
      wrap.innerHTML = `<canvas id="broker-product-bar"></canvas>`;
      Charts.createBar("broker-product-bar", container.querySelector("#broker-product-bar"), items.map(item => BrokerIncomeAnalysis._truncateLabel(item.label, 10)), [
        { label: "收入金额", data: items.map(item => item.amount), backgroundColor: "rgba(79,110,247,0.75)" },
      ], BrokerIncomeAnalysis._chartValueOptions({
        plugins: {
          legend: { position: "top" },
          valueLabels: {
            display: true,
            formatter: (value) => BrokerIncomeAnalysis._formatCompactMoney(value),
          },
          tooltip: {
            callbacks: {
              label: (context) => {
                const item = items[context.dataIndex];
                return `${item.label}: ${fmtMoney(item.amount)} (${item.percentage}%)`;
              },
            },
          },
        },
      }));
    } catch (err) {
      showError(wrap, err.message);
    }
  },

  _chartValueOptions(overrides = {}) {
    return {
      layout: { padding: { top: 18, right: 16, bottom: 4, left: 16 } },
      plugins: {
        legend: { position: "top" },
        valueLabels: {
          display: true,
          formatter: (value) => BrokerIncomeAnalysis._formatCompactMoney(value),
        },
      },
      ...overrides,
      plugins: {
        legend: { position: "top" },
        valueLabels: {
          display: true,
          formatter: (value) => BrokerIncomeAnalysis._formatCompactMoney(value),
        },
        ...(overrides.plugins || {}),
      },
    };
  },

  _formatCompactMoney(value) {
    const amount = Number(value) || 0;
    return `¥${(amount / 10000).toFixed(2)}万`;
  },

  _truncateLabel(label, maxLength) {
    const text = String(label || "");
    return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
  },

  _renderSummary(container, summary) {
    const el = container.querySelector("#tx-summary");
    if (!summary) { el.innerHTML = ""; return; }
    const bal = summary.balance;
    el.innerHTML = `
      <div class="summary-card">
        <div class="label">总收入</div>
        <div class="value income">${fmtMoney(summary.total_income)}</div>
      </div>
      <div class="summary-card">
        <div class="label">总支出</div>
        <div class="value expense">${fmtMoney(summary.total_expense)}</div>
      </div>
      <div class="summary-card">
        <div class="label">结余</div>
        <div class="value net ${bal >= 0 ? "positive" : "negative"}">${fmtMoney(bal)}</div>
      </div>
      <div class="summary-card">
        <div class="label">总笔数</div>
        <div class="value" style="color:var(--primary)">${summary.total_count}</div>
      </div>
    `;
  },

  _render(wrap, data, container) {
    if (!data.items.length) {
      wrap.innerHTML = `<div class="empty">没有找到账单记录</div>`;
      return;
    }

    wrap.innerHTML = `
      <table>
        <thead>
          <tr>
            <th style="width:40px"><input type="checkbox" id="tx-select-all" title="全选"></th>
            <th>时间</th>
            <th>来源</th>
            <th>分类</th>
            <th>交易对方</th>
            <th>商品</th>
            <th>别名</th>
            <th>方向</th>
            <th>金额</th>
            <th>支付方式</th>
            <th>备注</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          ${data.items.map(tx => `
            <tr data-id="${tx.id}">
              <td><input type="checkbox" class="tx-row-check" data-id="${tx.id}" ${BrokerIncomeAnalysis._state.selectedIds.has(tx.id) ? "checked" : ""}></td>
              <td style="white-space:nowrap">${fmtDate(tx.transaction_time)}</td>
              <td>${tx.source || "—"}</td>
              <td>
                <span class="editable category-cell" data-id="${tx.id}" title="点击编辑分类">
                  ${tx.category || tx.transaction_type || "—"}
                </span>
              </td>
              <td style="max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${tx.counterparty || ""}">
                ${tx.counterparty || "—"}
              </td>
              <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${tx.product || ""}">
                ${tx.product || "—"}
              </td>
              <td style="max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${tx.product_alias || ""}">
                ${tx.product_alias || "—"}
              </td>
              <td>${directionBadge(tx.direction)}</td>
              <td style="font-weight:600;
                color:${tx.direction === "income" ? "var(--income)" : tx.direction === "expense" ? "var(--expense)" : "inherit"}">
                ${fmtMoney(tx.amount)}
              </td>
              <td style="max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                ${tx.payment_method || "—"}
              </td>
              <td style="max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${tx.remark || ""}">
                ${tx.remark || "—"}
              </td>
              <td>
                <button class="btn btn-danger btn-sm btn-delete" data-id="${tx.id}"
                  style="padding:2px 8px;font-size:12px">删除</button>
              </td>
            </tr>`).join("")}
        </tbody>
      </table>
      ${BrokerIncomeAnalysis._renderPagination(data)}
    `;

    // Bind select-all
    const selectAll = wrap.querySelector("#tx-select-all");
    selectAll.addEventListener("change", () => {
      wrap.querySelectorAll(".tx-row-check").forEach(cb => {
        cb.checked = selectAll.checked;
        const id = parseInt(cb.dataset.id);
        if (selectAll.checked) BrokerIncomeAnalysis._state.selectedIds.add(id);
        else BrokerIncomeAnalysis._state.selectedIds.delete(id);
      });
      BrokerIncomeAnalysis._updateBatchBar(container);
    });

    // Bind row checkboxes
    wrap.querySelectorAll(".tx-row-check").forEach(cb => {
      cb.addEventListener("change", () => {
        const id = parseInt(cb.dataset.id);
        if (cb.checked) BrokerIncomeAnalysis._state.selectedIds.add(id);
        else BrokerIncomeAnalysis._state.selectedIds.delete(id);
        BrokerIncomeAnalysis._updateBatchBar(container);
      });
    });

    // Bind category inline edit
    wrap.querySelectorAll(".category-cell").forEach(cell => {
      cell.addEventListener("click", () => BrokerIncomeAnalysis._inlineEdit(cell, container));
    });

    // Bind delete buttons
    wrap.querySelectorAll(".btn-delete").forEach(btn => {
      btn.addEventListener("click", async () => {
        if (!confirm("确认删除这条账单记录？")) return;
        try {
          await API.transactions.delete(parseInt(btn.dataset.id));
          BrokerIncomeAnalysis._load(container);
        } catch (err) {
          alert("删除失败: " + err.message);
        }
      });
    });

    // Bind pagination
    wrap.querySelectorAll(".page-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const p = parseInt(btn.dataset.page);
        if (p && p !== BrokerIncomeAnalysis._state.page) {
          BrokerIncomeAnalysis._state.page = p;
          BrokerIncomeAnalysis._load(container);
        }
      });
    });

    BrokerIncomeAnalysis._updateBatchBar(container);
  },

  _renderPagination(data) {
    const { page, total_pages, total } = { page: data.page, total_pages: data.total_pages, total: data.total };
    const pgs = BrokerIncomeAnalysis._paginationItems(page, total_pages).map(item => (
      `<button class="page-btn ${item.page === page ? "active" : ""}" data-page="${item.page}">${item.label}</button>`
    ));
    return `
      <div class="pagination">
        <span class="info">共 ${total} 条</span>
        <button class="page-btn" data-page="${page - 1}" ${page <= 1 ? "disabled" : ""}>‹ 上一页</button>
        ${pgs.join("")}
        <button class="page-btn" data-page="${page + 1}" ${page >= total_pages ? "disabled" : ""}>下一页 ›</button>
      </div>
    `;
  },

  _paginationItems(page, totalPages) {
    if (totalPages <= 0) return [];
    if (totalPages <= 5) {
      return Array.from({ length: totalPages }, (_, idx) => {
        const pageNo = idx + 1;
        return { page: pageNo, label: String(pageNo) };
      });
    }

    const middle = [];
    const start = Math.max(2, Math.min(page - 1, totalPages - 3));
    const end = Math.min(totalPages - 1, start + 2);
    for (let pageNo = start; pageNo <= end; pageNo++) {
      middle.push({ page: pageNo, label: String(pageNo) });
    }

    return [
      { page: 1, label: start > 2 ? "1..." : "1" },
      ...middle,
      { page: totalPages, label: end < totalPages - 1 ? `...${totalPages}` : String(totalPages) },
    ];
  },

  _inlineEdit(cell, container) {
    if (cell.querySelector("input")) return;
    const id = parseInt(cell.dataset.id);
    const current = cell.textContent.trim();
    const cats = BrokerIncomeAnalysis._state.categories;
    // Use input with datalist for dropdown + custom
    const dlId = "cat-dl-" + id;
    cell.innerHTML = `<input class="inline-input" list="${dlId}" value="${current === "—" ? "" : current}" />
      <datalist id="${dlId}">${cats.map(c => `<option value="${c}">`).join("")}</datalist>`;
    const input = cell.querySelector("input");
    input.focus();
    input.select();

    const commit = async () => {
      const val = input.value.trim();
      try {
        await API.transactions.update(id, { category: val });
        cell.textContent = val || "—";
        cell.classList.add("editable");
        cell.addEventListener("click", () => BrokerIncomeAnalysis._inlineEdit(cell, container));
      } catch (err) {
        cell.textContent = current;
        alert("更新失败: " + err.message);
      }
    };

    input.addEventListener("blur", commit);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") input.blur();
      if (e.key === "Escape") { cell.textContent = current; }
    });
  },
};
