const StockManagement = {
  _state: {
    items: [],
    expandedKey: null,
    recordPages: {},
    lookupTimer: null,
    latestLookup: null,
    priceRefreshInFlight: false,
  },

  render(container) {
    container.innerHTML = `
      <div class="page-header">
        <div>
          <h1 class="page-title">股票管理</h1>
        </div>
      </div>

      <div class="stock-action-band">
        <button class="btn btn-primary" id="btn-new-stock" type="button">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg>
          新增股票记录
        </button>
      </div>

      <div class="page-header stock-section-header">
        <div class="page-title stock-section-title">现有资产</div>
        <button class="btn btn-ghost" id="btn-refresh-stocks" type="button">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 12a9 9 0 11-2.64-6.36"/><path d="M21 3v6h-6"/></svg>
          刷新
        </button>
      </div>
      <div class="table-wrap" id="stock-table-wrap"></div>
    `;
    container.querySelector("#btn-new-stock").addEventListener("click", () => StockManagement.openModal(container));
    container.querySelector("#btn-refresh-stocks").addEventListener("click", () => StockManagement.loadSummary(container, true, { showLoading: true, background: false }));
    StockManagement.loadSummary(container);
  },

  async loadSummary(container, refreshPrices = false, options = {}) {
    const showLoading = options.showLoading !== false;
    const background = options.background === true;
    const wrap = container.querySelector("#stock-table-wrap");
    if (showLoading) wrap.innerHTML = `<div class="loading">加载中...</div>`;
    try {
      const data = await API.stockManagement.summary({ refresh_prices: refreshPrices ? "true" : "false" });
      StockManagement._state.items = data.items || [];
      StockManagement.renderTable(container);
      if (!refreshPrices && !background) {
        StockManagement.refreshPricesIfNeeded(container);
      }
    } catch (err) {
      if (background) {
        showToast(`刷新行情失败：${err.message}`);
      } else {
        wrap.innerHTML = `<div class="empty" style="color:var(--expense)">加载失败：${StockManagement.escape(err.message)}</div>`;
      }
    }
  },

  refreshPricesIfNeeded(container) {
    if (StockManagement._state.priceRefreshInFlight) return;
    const needsRefresh = StockManagement._state.items.some(item => item.price_refresh_needed);
    if (!needsRefresh) return;
    StockManagement._state.priceRefreshInFlight = true;
    StockManagement.loadSummary(container, true, { showLoading: false, background: true })
      .finally(() => {
        StockManagement._state.priceRefreshInFlight = false;
      });
  },

  renderTable(container) {
    const wrap = container.querySelector("#stock-table-wrap");
    const items = StockManagement._state.items;
    if (!items.length) {
      wrap.innerHTML = `<div class="empty">暂无股票资产</div>`;
      return;
    }
    wrap.innerHTML = `
      <table class="stock-table">
        <thead>
          <tr>
            <th class="stock-detail-col"></th>
            <th class="stock-expand-col"></th>
            <th>股票代码</th>
            <th>股票名称</th>
            <th>别名</th>
            <th>数量</th>
            <th>当前总价值</th>
            <th>总成本</th>
            <th>当前收益率</th>
            <th>当前股价</th>
            <th>平均成本</th>
            <th>每股派息(去年)</th>
          </tr>
        </thead>
        <tbody>
          ${items.map(item => StockManagement.renderSummaryRows(item)).join("")}
        </tbody>
      </table>
    `;
    wrap.querySelectorAll(".stock-summary-row").forEach(row => {
      row.addEventListener("click", () => StockManagement.toggleRecords(container, row.dataset.key));
    });
    wrap.querySelectorAll("[data-stock-details]").forEach(btn => {
      btn.addEventListener("click", (event) => {
        event.stopPropagation();
        StockManagement.openDetailsModal(btn.dataset.market, btn.dataset.stockId);
      });
    });
    wrap.querySelectorAll("[data-stock-dividends]").forEach(btn => {
      btn.addEventListener("click", (event) => {
        event.stopPropagation();
        StockManagement.openDividendModal(btn.dataset.market, btn.dataset.stockId);
      });
    });
    wrap.querySelectorAll("[data-stock-page]").forEach(btn => {
      btn.addEventListener("click", (event) => {
        event.stopPropagation();
        StockManagement.loadRecords(container, btn.dataset.key, Number(btn.dataset.stockPage));
      });
    });
  },

  renderSummaryRows(item) {
    const key = StockManagement.itemKey(item);
    const expanded = StockManagement._state.expandedKey === key;
    const page = StockManagement._state.recordPages[key];
    const warning = item.lookup_error ? `<div class="stock-price-warning">${StockManagement.escape(item.lookup_error)}</div>` : "";
    const stale = item.price_cache_stale ? `<div class="stock-price-warning">行情缓存已过期，正在后台刷新</div>` : "";
    const pending = item.price_refresh_needed && !item.current_price ? `<div class="stock-price-warning">行情刷新中</div>` : "";
    return `
      <tr class="stock-summary-row ${expanded ? "expanded" : ""}" data-key="${StockManagement.escape(key)}">
        <td class="stock-detail-col">
          <button class="btn btn-ghost stock-detail-btn" type="button" data-stock-details data-market="${StockManagement.escape(item.stock_market)}" data-stock-id="${StockManagement.escape(item.stock_id)}">详情</button>
        </td>
        <td class="stock-expand-col"><span class="stock-expand-arrow">${expanded ? "▼" : "▶"}</span></td>
        <td><strong>${StockManagement.escape(item.stock_market)} · ${StockManagement.escape(item.stock_id)}</strong>${warning}</td>
        <td>${StockManagement.escape(item.stock_name || "--")}</td>
        <td>${StockManagement.escape(item.stock_alias || "--")}</td>
        <td>${StockManagement.formatNumber(item.stock_amount)}</td>
        <td>${StockManagement.formatMoney(item.total_value, item.stock_currency)}</td>
        <td>${StockManagement.formatMoney(item.total_cost, item.stock_currency)}</td>
        <td class="${StockManagement.returnRateClass(item.current_return_rate)}">${StockManagement.formatPercent(item.current_return_rate)}</td>
        <td>${StockManagement.formatMoney(item.current_price, item.stock_currency)}${stale || pending}</td>
        <td>${StockManagement.formatMoney(item.stock_average_price, item.stock_currency, 2)}</td>
        <td class="stock-dividend-cell">
          <span>--</span>
          <button class="btn btn-ghost stock-dividend-btn" type="button" data-stock-dividends data-market="${StockManagement.escape(item.stock_market)}" data-stock-id="${StockManagement.escape(item.stock_id)}">股息</button>
        </td>
      </tr>
      ${expanded ? StockManagement.renderRecordsRow(item, page) : ""}
    `;
  },

  renderRecordsRow(item, pageData) {
    const key = StockManagement.itemKey(item);
    if (!pageData) {
      return `
        <tr class="stock-record-row">
          <td colspan="12"><div class="loading">加载批次...</div></td>
        </tr>
      `;
    }
    const rows = (pageData.items || []).map(record => `
      <tr>
        <td>${StockManagement.escape(record.stock_name || "--")}</td>
        <td>${StockManagement.escape(record.stock_alias || "--")}</td>
        <td>${StockManagement.formatNumber(record.stock_amount)}</td>
        <td>${StockManagement.formatMoney(record.stock_average_price, record.stock_currency, 2)}</td>
        <td>${StockManagement.escape(record.stock_transaction_date || "--")}</td>
        <td>${StockManagement.escape(StockManagement.formatDateTime(record.stock_entry_time) || "--")}</td>
        <td>${StockManagement.escape(record.stock_remark || "--")}</td>
      </tr>
    `).join("");
    return `
      <tr class="stock-record-row">
        <td colspan="12">
          <div class="stock-record-panel">
            <table>
              <thead>
                <tr>
                  <th>股票名称</th>
                  <th>别名</th>
                  <th>数量</th>
                  <th>批次成本</th>
                  <th>成交日期</th>
                  <th>录入时间</th>
                  <th>备注</th>
                </tr>
              </thead>
              <tbody>${rows || `<tr><td colspan="7">暂无批次</td></tr>`}</tbody>
            </table>
            <div class="stock-record-pagination">
              <span>第 ${pageData.page} / ${pageData.total_pages || 1} 页，共 ${pageData.total} 条</span>
              <button class="btn btn-ghost" data-key="${StockManagement.escape(key)}" data-stock-page="${pageData.page - 1}" ${pageData.page <= 1 ? "disabled" : ""}>上一页</button>
              <button class="btn btn-ghost" data-key="${StockManagement.escape(key)}" data-stock-page="${pageData.page + 1}" ${pageData.page >= pageData.total_pages ? "disabled" : ""}>下一页</button>
            </div>
          </div>
        </td>
      </tr>
    `;
  },

  toggleRecords(container, key) {
    if (StockManagement._state.expandedKey === key) {
      StockManagement._state.expandedKey = null;
      StockManagement.renderTable(container);
      return;
    }
    StockManagement._state.expandedKey = key;
    StockManagement.renderTable(container);
    StockManagement.loadRecords(container, key, 1);
  },

  async loadRecords(container, key, page) {
    const item = StockManagement._state.items.find(row => StockManagement.itemKey(row) === key);
    if (!item || page < 1) return;
    try {
      const data = await API.stockManagement.records(item.stock_market, item.stock_id, { page, page_size: 5 });
      StockManagement._state.recordPages[key] = data;
      StockManagement.renderTable(container);
    } catch (err) {
      showToast(`加载批次失败：${err.message}`);
    }
  },

  openModal(container) {
    const existing = document.querySelector(".modal-overlay");
    if (existing) existing.remove();
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    StockManagement._state.latestLookup = null;
    overlay.innerHTML = `
      <div class="modal-dialog modal-dialog-lg stock-modal">
        <div class="modal-title">新增股票记录</div>
        <form id="stock-form">
          <div class="stock-form-grid">
            <div class="form-field stock-form-span2">
              <span class="form-label">所属市场</span>
              <div class="stock-market-options">
                <label><input type="radio" name="stock_market" value="CN" checked> A股</label>
                <label><input type="radio" name="stock_market" value="US"> 美股</label>
              </div>
            </div>
            <label class="form-field stock-code-field">
              <span class="form-label">股票代码 <span class="required-mark">*</span><span class="required-text">必填</span></span>
              <input name="stock_id" id="stock-id" required placeholder="例如 600519 或 AAPL">
            </label>
            <div class="form-field stock-name-field">
              <span class="form-label stock-hidden-label">股票名称</span>
              <div class="stock-name-inline" id="stock-name-inline">
                <span class="stock-name-placeholder">等待输入股票代码</span>
              </div>
            </div>
            <label class="form-field">
              <span class="form-label">别名</span>
              <input name="stock_alias" id="stock-alias" placeholder="选填">
            </label>
            <label class="form-field">
              <span class="form-label">股票数量 <span class="required-mark">*</span><span class="required-text">必填</span></span>
              <input name="stock_amount" type="number" min="0" step="0.000001" required>
            </label>
            <label class="form-field">
              <span class="form-label">平均成本</span>
              <div class="stock-money-input">
                <span id="stock-currency-symbol">¥</span>
                <input name="stock_average_price" type="number" min="0" step="0.0001" placeholder="请填写本批次平均成本">
              </div>
            </label>
            <label class="form-field">
              <span class="form-label">成交日期(选填)</span>
              <input name="stock_transaction_date" type="date">
            </label>
            <label class="form-field stock-form-span2">
              <span class="form-label">备注</span>
              <input name="stock_remark" maxlength="50" placeholder="选填，最多50个汉字">
            </label>
          </div>
          <input type="hidden" name="stock_name" id="stock-name">
          <div id="stock-lookup-hint" class="field-hint"></div>
          <div class="modal-buttons">
            <button class="btn btn-ghost" type="button" id="stock-cancel">取消</button>
            <button class="btn btn-primary" type="submit">保存</button>
          </div>
        </form>
      </div>
    `;
    document.body.appendChild(overlay);
    const marketEls = overlay.querySelectorAll("input[name='stock_market']");
    const codeEl = overlay.querySelector("#stock-id");
    const hintEl = overlay.querySelector("#stock-lookup-hint");
    const currentMarket = () => overlay.querySelector("input[name='stock_market']:checked").value;
    const updateCurrency = () => {
      overlay.querySelector("#stock-currency-symbol").textContent = currentMarket() === "US" ? "$" : "¥";
    };
    marketEls.forEach(marketEl => marketEl.addEventListener("change", () => {
      updateCurrency();
      overlay.querySelector("#stock-name").value = "";
      overlay.querySelector("#stock-alias").value = "";
      StockManagement._state.latestLookup = null;
      StockManagement.renderLookupName(overlay, "等待输入股票代码");
      hintEl.textContent = "";
      StockManagement.queueLookup(overlay);
    }));
    codeEl.addEventListener("input", () => StockManagement.queueLookup(overlay));
    codeEl.addEventListener("blur", () => StockManagement.lookupInModal(overlay));
    overlay.querySelector("#stock-cancel").addEventListener("click", () => overlay.remove());
    overlay.addEventListener("click", event => {
      if (event.target === overlay) overlay.remove();
    });
    overlay.querySelector("#stock-form").addEventListener("submit", event => StockManagement.submitModal(event, overlay, container));
    setTimeout(() => codeEl.focus(), 50);
  },

  async lookupInModal(overlay) {
    clearTimeout(StockManagement._state.lookupTimer);
    const market = overlay.querySelector("input[name='stock_market']:checked").value;
    const stockId = overlay.querySelector("#stock-id").value.trim();
    const nameEl = overlay.querySelector("#stock-name");
    const aliasEl = overlay.querySelector("#stock-alias");
    const hintEl = overlay.querySelector("#stock-lookup-hint");
    if (!stockId) return;
    StockManagement.renderLookupName(overlay, "检索中", true);
    hintEl.textContent = "正在查询股票信息...";
    hintEl.style.color = "var(--text-muted)";
    try {
      const data = await API.stockManagement.lookup({ stock_market: market, stock_id: stockId });
      const currentMarket = overlay.querySelector("input[name='stock_market']:checked").value;
      const currentStockId = overlay.querySelector("#stock-id").value.trim().toUpperCase();
      if (currentMarket !== market || currentStockId !== stockId.toUpperCase()) return;
      nameEl.value = data.stock_name || "";
      StockManagement._state.latestLookup = data;
      StockManagement.renderLookupName(overlay, data.stock_name || "--");
      if (data.stock_alias) aliasEl.value = data.stock_alias;
      hintEl.textContent = `已查询到实时价：${StockManagement.formatMoney(data.current_price, data.stock_currency)}${data.from_cache ? "（缓存）" : ""}`;
      hintEl.style.color = "var(--income)";
    } catch (err) {
      StockManagement._state.latestLookup = null;
      StockManagement.renderLookupName(overlay, "查询失败");
      hintEl.textContent = `查询失败：${err.message}。仍可保存该记录。`;
      hintEl.style.color = "var(--expense)";
    }
  },

  queueLookup(overlay) {
    clearTimeout(StockManagement._state.lookupTimer);
    const stockId = overlay.querySelector("#stock-id").value.trim();
    overlay.querySelector("#stock-name").value = "";
    StockManagement._state.latestLookup = null;
    if (!stockId) {
      StockManagement.renderLookupName(overlay, "等待输入股票代码");
      overlay.querySelector("#stock-lookup-hint").textContent = "";
      return;
    }
    StockManagement.renderLookupName(overlay, "检索中", true);
    StockManagement._state.lookupTimer = setTimeout(() => StockManagement.lookupInModal(overlay), 600);
  },

  renderLookupName(overlay, text, loading = false) {
    const el = overlay.querySelector("#stock-name-inline");
    if (!el) return;
    el.innerHTML = loading
      ? `<span class="stock-lookup-spinner"></span><span>${StockManagement.escape(text)}</span>`
      : `<span class="stock-name-placeholder">${StockManagement.escape(text)}</span>`;
  },

  async submitModal(event, overlay, container) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form).entries());
    const payload = {
      stock_market: data.stock_market,
      stock_id: data.stock_id,
      stock_name: data.stock_name,
      stock_alias: data.stock_alias,
      stock_amount: Number(data.stock_amount),
      stock_average_price: data.stock_average_price === ""
        ? (StockManagement._state.latestLookup && StockManagement._state.latestLookup.current_price !== null
          ? Number(StockManagement._state.latestLookup.current_price)
          : null)
        : Number(data.stock_average_price),
      stock_transaction_date: data.stock_transaction_date || null,
      stock_remark: data.stock_remark,
    };
    try {
      const result = await API.stockManagement.create(payload);
      overlay.remove();
      if (result.lookup_error) {
        showToast(`已保存，行情查询失败：${result.lookup_error}`);
      } else {
        showToast("股票记录已保存");
      }
      await StockManagement.loadSummary(container);
    } catch (err) {
      const hintEl = overlay.querySelector("#stock-lookup-hint");
      hintEl.textContent = `保存失败：${err.message}`;
      hintEl.style.color = "var(--expense)";
    }
  },

  openDetailsModal(market, stockId) {
    const existing = document.querySelector(".modal-overlay");
    if (existing) existing.remove();
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML = `
      <div class="modal-dialog modal-dialog-lg stock-details-modal">
        <div class="stock-details-header">
          <div class="stock-details-title-block">
            <div class="modal-title">股票详情</div>
            <div class="stock-details-meta-row">
              <div class="stock-details-subtitle">${StockManagement.escape(market)} · ${StockManagement.escape(stockId)}</div>
              <span class="stock-details-updated-at" data-stock-details-updated>更新时间：--</span>
              <button class="btn btn-ghost stock-details-refresh" type="button" data-stock-details-refresh>更新</button>
            </div>
          </div>
          <div class="stock-details-actions">
            <button class="btn btn-ghost stock-details-close" type="button" aria-label="关闭">×</button>
          </div>
        </div>
        <div class="stock-details-body">
          <div class="loading">正在查询股票详情...</div>
        </div>
        <div class="modal-buttons">
          <button class="btn btn-primary" type="button" data-stock-details-close>关闭</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
    const close = () => overlay.remove();
    overlay.querySelector(".stock-details-close").addEventListener("click", close);
    overlay.querySelector("[data-stock-details-close]").addEventListener("click", close);
    overlay.querySelector("[data-stock-details-refresh]").addEventListener("click", () => {
      StockManagement.loadDetails(overlay, market, stockId, true);
    });
    overlay.addEventListener("click", event => {
      if (event.target === overlay) close();
    });
    StockManagement.loadDetails(overlay, market, stockId);
  },

  openDividendModal(market, stockId) {
    const existing = document.querySelector(".modal-overlay");
    if (existing) existing.remove();
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML = `
      <div class="modal-dialog modal-dialog-lg stock-details-modal stock-dividend-modal">
        <div class="stock-details-header">
          <div class="stock-details-title-block">
            <div class="modal-title">股息分红</div>
            <div class="stock-details-meta-row">
              <div class="stock-details-subtitle">${StockManagement.escape(market)} · ${StockManagement.escape(stockId)}</div>
              <span class="stock-details-updated-at" data-stock-dividend-updated>更新时间：--</span>
            </div>
          </div>
          <div class="stock-details-actions">
            <button class="btn btn-ghost stock-details-close" type="button" aria-label="关闭">×</button>
          </div>
        </div>
        <div class="stock-details-body" data-stock-dividend-body>
          <div class="loading">正在查询股息分红数据...</div>
        </div>
        <div class="modal-buttons">
          <button class="btn btn-primary" type="button" data-stock-dividend-close>关闭</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
    const close = () => overlay.remove();
    overlay.querySelector(".stock-details-close").addEventListener("click", close);
    overlay.querySelector("[data-stock-dividend-close]").addEventListener("click", close);
    overlay.addEventListener("click", event => {
      if (event.target === overlay) close();
    });
    StockManagement.loadDividendDetails(overlay, market, stockId);
  },

  async loadDividendDetails(overlay, market, stockId) {
    const body = overlay.querySelector("[data-stock-dividend-body]");
    try {
      const data = await API.stockManagement.details(market, stockId);
      const updatedEl = overlay.querySelector("[data-stock-dividend-updated]");
      if (updatedEl) updatedEl.textContent = `更新时间：${StockManagement.formatDateTime(data.updated_at) || "--"}`;
      body.innerHTML = StockManagement.renderDividendDetails(data);
    } catch (err) {
      body.innerHTML = `<div class="empty" style="color:var(--expense)">加载失败：${StockManagement.escape(err.message)}</div>`;
    }
  },

  renderDividendDetails(data) {
    const market = (data.summary || {}).stock_market;
    if (market === "US") {
      return StockManagement.renderUsDividendDetails(data);
    }
    return StockManagement.renderCnDividendDetails(data);
  },

  renderUsDividendDetails(data) {
    const sections = data.external_sections || [];
    const yahooSection = sections.find(section => section.source === "yfinance.Ticker.get_dividends");
    if (!yahooSection) {
      return `<div class="empty">暂无 Yahoo Finance 历史股息数据</div>`;
    }
    if (yahooSection.status === "error") {
      return `<div class="empty" style="color:var(--expense)">Yahoo Finance 历史股息查询失败：${StockManagement.escape(yahooSection.error || "未知错误")}</div>`;
    }
    const rows = StockManagement.normalizedUsDividendRows(yahooSection.rows || []);
    const columns = ["date", "dividend"];
    const yearlyRows = StockManagement.yearlyDividendSummary(rows, "date", "dividend");
    const yearlyColumns = ["年份", "派息次数", "每股派息金额", "环比变化"];
    return `
      <section class="stock-details-section">
        <div class="stock-dividend-overview">
          <div class="stock-dividend-summary">
            <span>Yahoo Finance 历史股息</span>
            <strong>${StockManagement.formatNumber(rows.length)} 条</strong>
          </div>
        </div>
      </section>
      <section class="stock-details-section">
        <div class="stock-details-section-title">最近5年每股派息汇总</div>
        ${StockManagement.renderDetailsTable(yearlyColumns, yearlyRows)}
      </section>
      <section class="stock-details-section">
        <div class="stock-details-section-title">Yahoo Finance 历史股息</div>
        ${StockManagement.renderDetailsTable(columns, rows)}
      </section>
    `;
  },

  normalizedUsDividendRows(rows) {
    return rows
      .map(row => ({
        ...row,
        date: StockManagement.dateOnly(row.date),
      }))
      .sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")));
  },

  yearlyDividendSummary(rows, dateKey, amountKey) {
    const yearly = {};
    const yearlyCounts = {};
    rows.forEach(row => {
      const year = StockManagement.yearFromDate(row[dateKey]);
      const amount = Number(row[amountKey]);
      if (!year || !Number.isFinite(amount)) return;
      yearly[year] = (yearly[year] || 0) + amount;
      yearlyCounts[year] = (yearlyCounts[year] || 0) + 1;
    });
    const summaryByYear = {};
    Object.keys(yearly).map(Number).sort((a, b) => a - b).forEach(year => {
      const amount = yearly[year];
      const previousAmount = yearly[year - 1];
      const change = previousAmount ? ((amount - previousAmount) / previousAmount * 100) : null;
      summaryByYear[year] = {
        "年份": year,
        "派息次数": yearlyCounts[year] || 0,
        "每股派息金额": Number(amount.toFixed(6)),
        "环比变化": change === null ? null : Number(change.toFixed(2)),
      };
    });
    return Object.keys(summaryByYear)
      .map(Number)
      .sort((a, b) => b - a)
      .slice(0, 5)
      .map(year => summaryByYear[year]);
  },

  dateOnly(value) {
    if (!value) return value;
    const text = String(value).trim();
    const match = text.match(/\d{4}-\d{2}-\d{2}/);
    if (match) return match[0];
    const date = new Date(text);
    if (Number.isNaN(date.getTime())) return text;
    const pad = number => String(number).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  },

  yearFromDate(value) {
    if (!value) return null;
    const match = String(value).match(/(19|20)\d{2}/);
    return match ? Number(match[0]) : null;
  },

  renderCnDividendDetails(data) {
    const sections = data.external_sections || [];
    const thsSection = sections.find(section => section.source === "akshare.stock_fhps_detail_ths");
    if (!thsSection) {
      return `<div class="empty">暂无同花顺分红数据</div>`;
    }
    if (thsSection.status === "error") {
      return `<div class="empty" style="color:var(--expense)">同花顺分红数据查询失败：${StockManagement.escape(thsSection.error || "未知错误")}</div>`;
    }
    const parsed = thsSection.dividend_parse || {};
    const rawRows = parsed.raw_rows || thsSection.rows || [];
    const rawColumns = parsed.raw_columns || thsSection.columns || [];
    const yearlyRows = parsed.yearly_summary_rows || [];
    const yearlyColumns = parsed.yearly_summary_columns || ["年份", "每股派息金额"];
    const perShareRows = parsed.per_share_rows || [];
    const perShareColumns = parsed.per_share_columns || [];
    return `
      <section class="stock-details-section">
        <div class="stock-dividend-overview">
          <div class="stock-dividend-summary">
            <span>原数据</span>
            <strong>${StockManagement.formatNumber(rawRows.length)} 条</strong>
          </div>
          <div class="stock-dividend-summary">
            <span>每股派息</span>
            <strong>${StockManagement.formatNumber(perShareRows.filter(row => row["每股派息"] !== null && row["每股派息"] !== undefined).length)} 条可解析</strong>
          </div>
        </div>
      </section>
      <section class="stock-details-section">
        <div class="stock-details-section-title">最近5年每股派息汇总</div>
        ${StockManagement.renderDetailsTable(yearlyColumns, yearlyRows)}
      </section>
      <section class="stock-details-section">
        <div class="stock-details-section-title">每股派息数据</div>
        ${StockManagement.renderDetailsTable(perShareColumns, perShareRows)}
      </section>
      <section class="stock-details-section">
        <div class="stock-details-section-title">原数据</div>
        ${StockManagement.renderDetailsTable(rawColumns, rawRows)}
      </section>
    `;
  },

  async loadDetails(overlay, market, stockId, forceRefresh = false) {
    const body = overlay.querySelector(".stock-details-body");
    const refreshBtn = overlay.querySelector("[data-stock-details-refresh]");
    if (refreshBtn) {
      refreshBtn.disabled = true;
      refreshBtn.textContent = forceRefresh ? "更新中" : "更新";
    }
    try {
      const data = await API.stockManagement.details(market, stockId, { force_refresh: forceRefresh ? "true" : "false" });
      const updatedEl = overlay.querySelector("[data-stock-details-updated]");
      if (updatedEl) updatedEl.textContent = `更新时间：${StockManagement.formatDateTime(data.updated_at) || "--"}`;
      body.innerHTML = StockManagement.renderDetails(data);
    } catch (err) {
      body.innerHTML = `<div class="empty" style="color:var(--expense)">加载失败：${StockManagement.escape(err.message)}</div>`;
    } finally {
      if (refreshBtn) {
        refreshBtn.disabled = false;
        refreshBtn.textContent = "更新";
      }
    }
  },

  renderDetails(data) {
    const summary = data.summary || {};
    const lookup = data.lookup || null;
    const records = data.records || [];
    const sections = data.external_sections || [];
    return `
      <section class="stock-details-section">
        <div class="stock-details-section-title">基础信息</div>
        <div class="stock-details-grid">
          ${StockManagement.renderDetailPair("市场", summary.stock_market)}
          ${StockManagement.renderDetailPair("代码", summary.stock_id)}
          ${StockManagement.renderDetailPair("名称", summary.stock_name || "--")}
          ${StockManagement.renderDetailPair("别名", summary.stock_alias || "--")}
          ${StockManagement.renderDetailPair("币种", summary.stock_currency)}
          ${StockManagement.renderDetailPair("当前价", StockManagement.formatMoney(summary.current_price, summary.stock_currency))}
          ${StockManagement.renderDetailPair("数量", StockManagement.formatNumber(summary.stock_amount))}
          ${StockManagement.renderDetailPair("当前总价值", StockManagement.formatMoney(summary.total_value, summary.stock_currency))}
          ${StockManagement.renderDetailPair("总成本", StockManagement.formatMoney(summary.total_cost, summary.stock_currency))}
          ${StockManagement.renderDetailPair("平均成本", StockManagement.formatMoney(summary.stock_average_price, summary.stock_currency, 2))}
          ${StockManagement.renderDetailPair("当前收益率", StockManagement.formatPercent(summary.current_return_rate))}
          ${StockManagement.renderDetailPair("行情状态", summary.lookup_error ? `失败：${summary.lookup_error}` : "正常")}
        </div>
      </section>
      <section class="stock-details-section">
        <div class="stock-details-section-title">本地批次</div>
        ${StockManagement.renderDetailsTable(
          ["股票名称", "别名", "数量", "批次成本", "成交日期", "录入时间", "备注"],
          records.map(record => ({
            "股票名称": record.stock_name || "--",
            "别名": record.stock_alias || "--",
            "数量": StockManagement.formatNumber(record.stock_amount),
            "批次成本": StockManagement.formatMoney(record.stock_average_price, record.stock_currency, 2),
            "成交日期": record.stock_transaction_date || "--",
            "录入时间": StockManagement.formatDateTime(record.stock_entry_time) || "--",
            "备注": record.stock_remark || "--",
          }))
        )}
      </section>
      <section class="stock-details-section">
        <div class="stock-details-section-title">实时行情</div>
        ${lookup ? StockManagement.renderDetailsTable(
          ["字段", "值"],
          StockManagement.objectRows({
            stock_market: lookup.stock_market,
            stock_id: lookup.stock_id,
            stock_name: lookup.stock_name,
            current_price: StockManagement.formatMoney(lookup.current_price, lookup.stock_currency),
            stock_currency: lookup.stock_currency,
            raw_api_source: lookup.raw_api_source,
            queried_at: StockManagement.formatDateTime(lookup.queried_at),
            from_cache: lookup.from_cache ? "是" : "否",
            raw_api_data: lookup.raw_api_data,
          })
        ) : `<div class="empty">暂无实时行情${data.lookup_error ? `：${StockManagement.escape(data.lookup_error)}` : ""}</div>`}
      </section>
      ${sections.map(section => StockManagement.renderExternalSection(section)).join("")}
    `;
  },

  renderDetailPair(label, value) {
    return `
      <div class="stock-details-pair">
        <span>${StockManagement.escape(label)}</span>
        <strong>${StockManagement.escape(StockManagement.formatDetailValue(value))}</strong>
      </div>
    `;
  },

  renderExternalSection(section) {
    return `
      <section class="stock-details-section">
        <div class="stock-details-section-heading">
          <div>
            <div class="stock-details-section-title">${StockManagement.escape(section.title || "--")}</div>
            <div class="stock-details-source">${StockManagement.escape(section.source || "--")}</div>
          </div>
          <span class="stock-details-status ${section.status === "error" ? "error" : ""}">${section.status === "error" ? "失败" : "正常"}</span>
        </div>
        ${section.status === "error"
          ? `<div class="empty" style="color:var(--expense)">${StockManagement.escape(section.error || "查询失败")}</div>`
          : StockManagement.renderDetailsTable(section.columns || [], section.rows || [])}
      </section>
    `;
  },

  renderDetailsTable(columns, rows) {
    if (!rows.length) return `<div class="empty">暂无数据</div>`;
    const safeColumns = columns.length ? columns : Object.keys(rows[0] || {});
    return `
      <div class="stock-details-table-wrap">
        <table class="stock-details-table">
          <thead>
            <tr>${safeColumns.map(col => `<th>${StockManagement.escape(col)}</th>`).join("")}</tr>
          </thead>
          <tbody>
            ${rows.map(row => `
              <tr>
                ${safeColumns.map(col => StockManagement.renderDetailsTableCell(col, row[col])).join("")}
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  },

  renderDetailsTableCell(column, value) {
    if (column === "环比变化") {
      const cellClass = StockManagement.returnRateClass(value);
      return `<td class="${cellClass}">${StockManagement.escape(StockManagement.formatPercent(value))}</td>`;
    }
    return `<td>${StockManagement.escape(StockManagement.formatDetailValue(value))}</td>`;
  },

  objectRows(obj) {
    return Object.entries(obj).map(([key, value]) => ({
      "字段": key,
      "值": StockManagement.formatDetailValue(value),
    }));
  },

  itemKey(item) {
    return `${item.stock_market}:${item.stock_id}`;
  },

  formatNumber(value) {
    if (value === null || value === undefined) return "--";
    return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 6 });
  },

  formatMoney(value, currency, maximumFractionDigits = 4) {
    if (value === null || value === undefined) return "--";
    const symbol = currency === "USD" ? "$" : "¥";
    return `${symbol}${Number(value).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits })}`;
  },

  formatPercent(value) {
    if (value === null || value === undefined) return "--";
    return `${Number(value).toFixed(1)}%`;
  },

  returnRateClass(value) {
    if (value === null || value === undefined || Number(value) === 0) return "";
    return Number(value) > 0 ? "stock-return-positive" : "stock-return-negative";
  },

  formatDateTime(value) {
    if (!value) return "";
    const text = String(value).trim();
    const hasTimezone = /(Z|[+-]\d{2}:?\d{2})$/.test(text);
    const looksLikeDateTime = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(text);
    const normalized = looksLikeDateTime && !hasTimezone
      ? `${text.replace(" ", "T")}Z`
      : text;
    const date = new Date(normalized);
    if (Number.isNaN(date.getTime())) return text.replace("T", " ").slice(0, 19);
    const pad = number => String(number).padStart(2, "0");
    return [
      date.getFullYear(),
      pad(date.getMonth() + 1),
      pad(date.getDate()),
    ].join("-") + " " + [
      pad(date.getHours()),
      pad(date.getMinutes()),
      pad(date.getSeconds()),
    ].join(":");
  },

  formatDetailValue(value) {
    if (value === null || value === undefined || value === "") return "--";
    if (typeof value === "object") {
      return JSON.stringify(value, null, 2);
    }
    return String(value);
  },

  escape(value) {
    return String(value ?? "").replace(/[&<>"']/g, ch => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[ch]));
  },
};
