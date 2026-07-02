const StockManagement = {
  _state: {
    items: [],
    portfolioSummary: null,
    expandedKey: null,
    recordPages: {},
    lookupTimer: null,
    latestLookup: null,
    summaryRefreshInFlight: false,
    summarySort: { key: "total_value", direction: "desc" },
  },

  render(container) {
    container.innerHTML = `
      <div class="page-header">
        <div>
          <h1 class="page-title">股票管理</h1>
        </div>
      </div>

      <div class="stock-action-band">
        <div class="page-title stock-section-title">操作</div>
        <div class="stock-action-buttons">
          <button class="btn btn-primary" id="btn-new-stock" type="button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg>
            新增股票记录
          </button>
          <button class="btn btn-ghost" id="btn-refresh-stocks" type="button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 12a9 9 0 11-2.64-6.36"/><path d="M21 3v6h-6"/></svg>
            刷新数据
          </button>
        </div>
      </div>

      <div class="page-header stock-section-header">
        <div class="page-title stock-section-title">汇总统计</div>
      </div>
      <div id="stock-portfolio-summary"></div>
      <div class="page-header stock-section-header stock-assets-header">
        <div class="page-title stock-section-title">现有资产</div>
      </div>
      <div class="table-wrap" id="stock-table-wrap"></div>
    `;
    container.querySelector("#btn-new-stock").addEventListener("click", () => StockManagement.openModal(container));
    container.querySelector("#btn-refresh-stocks").addEventListener("click", () => StockManagement.loadSummary(container, { refreshPrices: true, refreshDividends: true, showLoading: true, background: false }));
    StockManagement.loadSummary(container);
  },

  async loadSummary(container, options = {}) {
    const refreshPrices = options.refreshPrices === true;
    const refreshDividends = options.refreshDividends === true;
    const showLoading = options.showLoading !== false;
    const background = options.background === true;
    const wrap = container.querySelector("#stock-table-wrap");
    if (showLoading) wrap.innerHTML = `<div class="loading">加载中...</div>`;
    try {
      const data = await API.stockManagement.summary({
        refresh_prices: refreshPrices ? "true" : "false",
        refresh_dividends: refreshDividends ? "true" : "false",
      });
      StockManagement._state.items = data.items || [];
      StockManagement._state.portfolioSummary = data.portfolio_summary || null;
      StockManagement.renderTable(container);
      if (!refreshPrices && !refreshDividends && !background) {
        StockManagement.refreshSummaryIfNeeded(container);
      }
    } catch (err) {
      if (background) {
        showToast(`刷新股票数据失败：${err.message}`);
      } else {
        wrap.innerHTML = `<div class="empty" style="color:var(--danger)">加载失败：${StockManagement.escape(err.message)}</div>`;
      }
    }
  },

  refreshSummaryIfNeeded(container) {
    if (StockManagement._state.summaryRefreshInFlight) return;
    const needsRefresh = StockManagement._state.items.some(item => item.price_refresh_needed || item.stock_dividend_refresh_needed);
    if (!needsRefresh) return;
    StockManagement._state.summaryRefreshInFlight = true;
    StockManagement.loadSummary(container, { refreshPrices: true, refreshDividends: true, showLoading: false, background: true })
      .finally(() => {
        StockManagement._state.summaryRefreshInFlight = false;
      });
  },

  renderTable(container) {
    StockManagement.renderPortfolioSummary(container);
    const wrap = container.querySelector("#stock-table-wrap");
    const items = StockManagement.sortedSummaryItems();
    wrap.innerHTML = `
      <table class="stock-table">
        <thead>
          <tr>
            <th class="stock-expand-col"></th>
            ${StockManagement.summarySortColumns().map(col => StockManagement.renderSortableHeader(col)).join("")}
            <th class="stock-detail-col">操作</th>
          </tr>
        </thead>
        <tbody>
          ${items.length ? items.map((item, index) => StockManagement.renderSummaryRows(item, index)).join("") : StockManagement.renderEmptyTableRow(16)}
        </tbody>
      </table>
    `;
    wrap.querySelectorAll("[data-stock-sort]").forEach(btn => {
      btn.addEventListener("click", (event) => {
        event.stopPropagation();
        StockManagement.toggleSummarySort(btn.dataset.stockSort);
        StockManagement.renderTable(container);
      });
    });
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
    wrap.querySelectorAll("[data-stock-record-edit]").forEach(btn => {
      btn.addEventListener("click", (event) => {
        event.stopPropagation();
        const record = StockManagement.findRecord(btn.dataset.stockVid);
        if (record) StockManagement.openModal(container, { record });
      });
    });
    wrap.querySelectorAll("[data-stock-record-delete]").forEach(btn => {
      btn.addEventListener("click", (event) => {
        event.stopPropagation();
        const record = StockManagement.findRecord(btn.dataset.stockVid);
        if (record) StockManagement.openDeleteConfirm(container, record);
      });
    });
  },

  summarySortColumns() {
    return [
      { key: "stock_code", label: "股票代码", type: "text" },
      { key: "stock_name", label: "股票名称", type: "text" },
      { key: "stock_alias", label: "别名", type: "text" },
      { key: "stock_amount", label: "数量", type: "number" },
      { key: "total_value", label: "当前总价值", type: "number" },
      { key: "total_cost", label: "总成本", type: "number" },
      { key: "current_return_rate", label: "当前收益率", type: "number" },
      { key: "current_price", label: "当前股价", type: "number" },
      { key: "stock_average_price", label: "持仓成本", type: "number" },
      { key: "stock_dividend_per_share_last_year", label: "每股派息(去年)", type: "number" },
      { key: "stock_dividend_change_rate", label: "股息环比变化", type: "number" },
      { key: "dividend_rate", label: "股息率", type: "number" },
      { key: "holding_dividend_rate", label: "持仓股息率", type: "number" },
      { key: "annual_dividend", label: "预计股息/年", type: "number" },
    ];
  },

  renderSortableHeader(column) {
    const sort = StockManagement._state.summarySort;
    const active = sort.key === column.key;
    const icon = active ? (sort.direction === "asc" ? "▲" : "▼") : "↕";
    return `
      <th>
        <button class="stock-sort-header ${active ? "active" : ""}" type="button" data-stock-sort="${StockManagement.escape(column.key)}">
          <span>${StockManagement.escape(column.label)}</span>
          <span class="stock-sort-icon">${icon}</span>
        </button>
      </th>
    `;
  },

  toggleSummarySort(key) {
    const current = StockManagement._state.summarySort;
    if (current.key === key) {
      current.direction = current.direction === "desc" ? "asc" : "desc";
      return;
    }
    StockManagement._state.summarySort = { key, direction: "desc" };
  },

  sortedSummaryItems() {
    const items = [...StockManagement._state.items];
    const sort = StockManagement._state.summarySort;
    const column = StockManagement.summarySortColumns().find(item => item.key === sort.key) || { key: "total_value", type: "number" };
    return items.sort((left, right) => StockManagement.compareSummaryItems(left, right, column, sort.direction));
  },

  compareSummaryItems(left, right, column, direction) {
    const leftValue = StockManagement.summarySortValue(left, column.key);
    const rightValue = StockManagement.summarySortValue(right, column.key);
    const leftEmpty = leftValue === null || leftValue === undefined || leftValue === "";
    const rightEmpty = rightValue === null || rightValue === undefined || rightValue === "";
    if (leftEmpty && rightEmpty) return 0;
    if (leftEmpty) return 1;
    if (rightEmpty) return -1;
    let result;
    if (column.type === "number") {
      result = Number(leftValue) - Number(rightValue);
    } else {
      result = String(leftValue).localeCompare(String(rightValue), "zh-CN", { numeric: true, sensitivity: "base" });
    }
    return direction === "asc" ? result : -result;
  },

  summarySortValue(item, key) {
    if (key === "stock_code") return `${item.stock_market || ""} ${item.stock_id || ""}`.trim();
    if (key === "dividend_rate") {
      return StockManagement.rateValue(item.stock_dividend_per_share_last_year, item.current_price);
    }
    if (key === "holding_dividend_rate") {
      return StockManagement.rateValue(item.stock_dividend_per_share_last_year, item.stock_average_price);
    }
    if (key === "annual_dividend") return StockManagement.annualDividendValue(item);
    return item[key];
  },

  renderPortfolioSummary(container) {
    const el = container.querySelector("#stock-portfolio-summary");
    if (!el) return;
    const summary = StockManagement._state.portfolioSummary;
    const rows = [
      ...((summary && summary.converted_total) ? [summary.converted_total] : []),
      ...((summary && summary.rows) || []),
    ];
    el.innerHTML = `
      <div class="stock-portfolio-summary">
        <table class="stock-portfolio-table">
          <thead>
            <tr>
              <th>币种</th>
              <th>资产总价值</th>
              <th>持仓总成本</th>
              <th>本金收益率</th>
              <th>持仓股息率</th>
              <th>预计股息/年</th>
              <th>税后股息</th>
            </tr>
          </thead>
          <tbody>
            ${rows.length ? rows.map(row => StockManagement.renderPortfolioSummaryRow(row)).join("") : StockManagement.renderEmptyTableRow(7)}
          </tbody>
        </table>
      </div>
    `;
  },

  renderPortfolioSummaryRow(row) {
    const isConverted = row.is_converted === true;
    const label = row.label || row.currency || "--";
    const note = row.exchange_rate_error
      ? `<div class="stock-price-warning">${StockManagement.escape(row.exchange_rate_error)}</div>`
      : (isConverted ? StockManagement.renderExchangeRateNote() : "");
    return `
      <tr class="${isConverted ? "stock-portfolio-total-row" : ""}">
        <td><strong>${StockManagement.escape(label)}</strong>${note}</td>
        <td>${StockManagement.renderPortfolioValue(row.asset_total_value, row.currency, row.asset_value_pending)}</td>
        <td>${StockManagement.renderPortfolioValue(row.holding_total_cost, row.currency, false)}</td>
        <td class="${StockManagement.returnRateClass(row.principal_return_rate)}">${StockManagement.renderPortfolioPercent(row.principal_return_rate, row.asset_value_pending)}</td>
        <td>${StockManagement.renderPortfolioPercent(row.holding_dividend_rate, row.dividend_pending)}</td>
        <td>${StockManagement.renderPortfolioValue(row.annual_dividend, row.currency, row.dividend_pending)}</td>
        <td>${StockManagement.renderPortfolioValue(row.after_tax_dividend, row.currency, row.dividend_pending)}</td>
      </tr>
    `;
  },

  renderExchangeRateNote() {
    const summary = StockManagement._state.portfolioSummary || {};
    const rows = summary.rows || [];
    const notes = rows
      .filter(row => row.currency && row.currency !== "CNY" && row.exchange_rate_to_cny)
      .map(row => `${row.currency}=${Number(row.exchange_rate_to_cny).toFixed(4)}CNY`);
    return notes.length ? `<div class="stock-portfolio-rate-note">${StockManagement.escape(notes.join("，"))}</div>` : "";
  },

  renderPortfolioValue(value, currency, loading) {
    if (loading) return StockManagement.loadingDots();
    return StockManagement.formatMoneyInteger(value, currency);
  },

  renderPortfolioPercent(value, loading) {
    if (loading) return StockManagement.loadingDots();
    return StockManagement.formatPercent(value);
  },

  loadingDots() {
    return `<span class="stock-metric-loading" aria-label="加载中"><span></span><span></span><span></span></span>`;
  },

  inlineLoadingDots(label = "加载中") {
    return `<span class="stock-inline-loading">${StockManagement.loadingDots().replace('aria-label="加载中"', `aria-label="${StockManagement.escape(label)}"`)}</span>`;
  },

  renderEmptyTableRow(colspan) {
    return `<tr><td class="stock-empty-table-cell" colspan="${colspan}">当前无数据</td></tr>`;
  },

  renderSummaryRows(item, index = 0) {
    const key = StockManagement.itemKey(item);
    const expanded = StockManagement._state.expandedKey === key;
    const page = StockManagement._state.recordPages[key];
    const warning = item.lookup_error ? `<div class="stock-price-warning">${StockManagement.escape(item.lookup_error)}</div>` : "";
    const priceLoading = (item.price_cache_stale || (item.price_refresh_needed && !item.current_price))
      ? StockManagement.inlineLoadingDots("行情刷新中")
      : "";
    const dividendLoading = item.stock_dividend_refresh_needed ? StockManagement.inlineLoadingDots("股息刷新中") : "";
    const stripeClass = index % 2 === 0 ? "stock-row-even" : "stock-row-odd";
    return `
      <tr class="stock-summary-row ${stripeClass} ${expanded ? "expanded" : ""}" data-key="${StockManagement.escape(key)}">
        <td class="stock-expand-col"><span class="stock-expand-arrow">${expanded ? "▼" : "▶"}</span></td>
        <td><strong>${StockManagement.escape(item.stock_market)} · ${StockManagement.escape(item.stock_id)}</strong>${warning}</td>
        <td>${StockManagement.escape(item.stock_name || "--")}</td>
        <td>${StockManagement.escape(item.stock_alias || "--")}</td>
        <td>${StockManagement.formatNumber(item.stock_amount)}</td>
        <td>${StockManagement.formatMoneyInteger(item.total_value, item.stock_currency)}</td>
        <td>${StockManagement.formatMoneyInteger(item.total_cost, item.stock_currency)}</td>
        <td class="${StockManagement.returnRateClass(item.current_return_rate)}">${StockManagement.formatPercent(item.current_return_rate)}</td>
        <td>${StockManagement.formatMoney(item.current_price, item.stock_currency)}${priceLoading}</td>
        <td>${StockManagement.formatMoney(item.stock_average_price, item.stock_currency, 2)}</td>
        <td class="stock-dividend-cell">
          <span title="${StockManagement.escape(StockManagement.dividendCellTitle(item))}">${StockManagement.formatMoney(item.stock_dividend_per_share_last_year, item.stock_currency, 2)}</span>
          ${dividendLoading}
        </td>
        <td class="${StockManagement.returnRateClass(item.stock_dividend_change_rate)}">${StockManagement.formatPercent(item.stock_dividend_change_rate)}</td>
        <td>${StockManagement.formatDividendRate(item.stock_dividend_per_share_last_year, item.current_price)}</td>
        <td>${StockManagement.formatDividendRate(item.stock_dividend_per_share_last_year, item.stock_average_price)}</td>
        <td>${StockManagement.renderAnnualDividend(item, dividendLoading)}</td>
        <td class="stock-detail-col">
          <div class="stock-row-actions">
            <button class="btn btn-ghost stock-detail-btn" type="button" data-stock-details data-market="${StockManagement.escape(item.stock_market)}" data-stock-id="${StockManagement.escape(item.stock_id)}">详情</button>
            <button class="btn btn-ghost stock-dividend-btn" type="button" data-stock-dividends data-market="${StockManagement.escape(item.stock_market)}" data-stock-id="${StockManagement.escape(item.stock_id)}">股息</button>
          </div>
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
          <td colspan="16"><div class="loading">加载批次...</div></td>
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
        <td>
          <div class="stock-row-actions">
            <button class="btn btn-ghost stock-record-action-btn" type="button" data-stock-record-edit data-stock-vid="${StockManagement.escape(record.stock_vid)}">编辑</button>
            <button class="btn btn-ghost stock-record-action-btn stock-record-delete-btn" type="button" data-stock-record-delete data-stock-vid="${StockManagement.escape(record.stock_vid)}">删除</button>
          </div>
        </td>
      </tr>
    `).join("");
    return `
      <tr class="stock-record-row">
        <td colspan="16">
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
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>${rows || `<tr><td colspan="8">暂无批次</td></tr>`}</tbody>
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

  findRecord(stockVid) {
    for (const pageData of Object.values(StockManagement._state.recordPages)) {
      const record = (pageData.items || []).find(item => item.stock_vid === stockVid);
      if (record) return record;
    }
    return null;
  },

  openModal(container, options = {}) {
    const existing = document.querySelector(".modal-overlay");
    if (existing) existing.remove();
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    const record = options.record || null;
    const isEdit = !!record;
    StockManagement._state.latestLookup = null;
    if (record) {
      StockManagement._state.latestLookup = {
        current_price: record.stock_average_price,
        stock_currency: record.stock_currency,
        stock_name: record.stock_name,
      };
    }
    overlay.dataset.mode = isEdit ? "edit" : "create";
    overlay.dataset.stockVid = record ? record.stock_vid : "";
    overlay.dataset.aliasTouched = record && record.stock_alias ? "true" : "false";
    overlay.dataset.aliasAutoValue = "";
    overlay.dataset.lookupSeq = "0";
    overlay.innerHTML = `
      <div class="modal-dialog modal-dialog-lg stock-modal">
        <div class="modal-title">${isEdit ? "编辑股票记录" : "新增股票记录"}</div>
        <form id="stock-form">
          <div class="stock-form-grid">
            <div class="form-field stock-form-span2">
              <span class="form-label">所属市场</span>
              <div class="stock-market-options">
                <label><input type="radio" name="stock_market" value="CN" ${!record || record.stock_market === "CN" ? "checked" : ""}> A股</label>
                <label><input type="radio" name="stock_market" value="US" ${record && record.stock_market === "US" ? "checked" : ""}> 美股</label>
              </div>
            </div>
            <label class="form-field stock-code-field">
              <span class="form-label">股票代码 <span class="required-mark">*</span><span class="required-text">必填</span></span>
              <input name="stock_id" id="stock-id" required placeholder="例如 600519 或 AAPL" value="${StockManagement.escape(record ? record.stock_id : "")}">
            </label>
            <div class="form-field stock-name-field">
              <span class="form-label stock-hidden-label">股票名称</span>
              <div class="stock-name-inline" id="stock-name-inline">
                <span class="stock-name-placeholder">${StockManagement.escape(record ? (record.stock_name || "--") : "等待输入股票代码")}</span>
              </div>
            </div>
            <label class="form-field">
              <span class="form-label">别名</span>
              <input name="stock_alias" id="stock-alias" placeholder="选填" value="${StockManagement.escape(record ? (record.stock_alias || "") : "")}">
            </label>
            <label class="form-field">
              <span class="form-label">股票数量 <span class="required-mark">*</span><span class="required-text">必填</span></span>
              <input name="stock_amount" type="number" min="0" step="0.000001" required value="${StockManagement.escape(record ? record.stock_amount : "")}">
            </label>
            <label class="form-field">
              <span class="form-label stock-cost-label">平均成本 <span id="stock-live-price" class="stock-live-price"></span></span>
              <div class="stock-money-input">
                <span id="stock-currency-symbol">¥</span>
                <input name="stock_average_price" type="number" min="0" step="0.0001" placeholder="请填写本批次平均成本" value="${StockManagement.escape(record && record.stock_average_price !== null && record.stock_average_price !== undefined ? record.stock_average_price : "")}">
              </div>
            </label>
            <label class="form-field">
              <span class="form-label">成交日期(选填)</span>
              <input name="stock_transaction_date" type="date" value="${StockManagement.escape(record ? (record.stock_transaction_date || "") : "")}">
            </label>
            <label class="form-field stock-form-span2">
              <span class="form-label">备注</span>
              <input name="stock_remark" maxlength="50" placeholder="选填，最多50个汉字" value="${StockManagement.escape(record ? (record.stock_remark || "") : "")}">
            </label>
          </div>
          <input type="hidden" name="stock_name" id="stock-name" value="${StockManagement.escape(record ? (record.stock_name || "") : "")}">
          <div id="stock-lookup-hint" class="field-hint"></div>
          <div class="modal-buttons">
            <button class="btn btn-ghost" type="button" id="stock-cancel">取消</button>
            <button class="btn btn-primary" type="submit">${isEdit ? "保存修改" : "保存"}</button>
          </div>
        </form>
      </div>
    `;
    document.body.appendChild(overlay);
    const marketEls = overlay.querySelectorAll("input[name='stock_market']");
    const codeEl = overlay.querySelector("#stock-id");
    const hintEl = overlay.querySelector("#stock-lookup-hint");
    const aliasEl = overlay.querySelector("#stock-alias");
    const currentMarket = () => overlay.querySelector("input[name='stock_market']:checked").value;
    const updateCurrency = () => {
      overlay.querySelector("#stock-currency-symbol").textContent = currentMarket() === "US" ? "$" : "¥";
    };
    updateCurrency();
    marketEls.forEach(marketEl => marketEl.addEventListener("change", () => {
      updateCurrency();
      overlay.querySelector("#stock-name").value = "";
      aliasEl.value = "";
      overlay.dataset.aliasTouched = "false";
      overlay.dataset.aliasAutoValue = "";
      StockManagement._state.latestLookup = null;
      StockManagement.renderLookupName(overlay, "等待输入股票代码");
      StockManagement.renderLookupPrice(overlay);
      hintEl.textContent = "";
      StockManagement.queueLookup(overlay);
    }));
    aliasEl.addEventListener("input", () => {
      overlay.dataset.aliasTouched = "true";
    });
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
    StockManagement.renderLookupPrice(overlay);
    hintEl.textContent = "";
    hintEl.style.color = "var(--text-muted)";
    const lookupSeq = Number(overlay.dataset.lookupSeq || "0") + 1;
    overlay.dataset.lookupSeq = String(lookupSeq);
    try {
      const data = await StockManagement.lookupStockWithRetry(market, stockId);
      if (Number(overlay.dataset.lookupSeq || "0") !== lookupSeq) return;
      const currentMarket = overlay.querySelector("input[name='stock_market']:checked").value;
      const currentStockId = overlay.querySelector("#stock-id").value.trim().toUpperCase();
      if (currentMarket !== market || currentStockId !== stockId.toUpperCase()) return;
      nameEl.value = data.stock_name || "";
      StockManagement._state.latestLookup = data;
      StockManagement.renderLookupName(overlay, data.stock_name || "--");
      StockManagement.applyDefaultAlias(overlay, data, market, stockId);
      StockManagement.renderLookupPrice(overlay, data);
      hintEl.textContent = "";
      hintEl.style.color = "var(--success)";
    } catch (err) {
      if (Number(overlay.dataset.lookupSeq || "0") !== lookupSeq) return;
      StockManagement._state.latestLookup = null;
      StockManagement.renderLookupName(overlay, "查询失败", false, { retry: true, error: err.message });
      StockManagement.renderLookupPrice(overlay);
      hintEl.textContent = `查询失败：${err.message}。仍可保存该记录。`;
      hintEl.style.color = "var(--danger)";
    }
  },

  async lookupStockWithRetry(market, stockId, retryTimes = 2) {
    let lastError = null;
    for (let attempt = 0; attempt <= retryTimes; attempt += 1) {
      try {
        return await API.stockManagement.lookup({ stock_market: market, stock_id: stockId });
      } catch (err) {
        lastError = err;
        if (attempt < retryTimes) {
          await StockManagement.sleep(300 * (attempt + 1));
        }
      }
    }
    throw lastError;
  },

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  },

  applyDefaultAlias(overlay, data, market, stockId) {
    const aliasEl = overlay.querySelector("#stock-alias");
    const previousAutoValue = overlay.dataset.aliasAutoValue || "";
    const aliasTouched = overlay.dataset.aliasTouched === "true";
    const defaultAlias = market === "US" ? stockId.toUpperCase() : (data.stock_name || "");
    const shouldApply = defaultAlias && !aliasTouched && (!aliasEl.value || aliasEl.value === previousAutoValue);
    if (!shouldApply) return;
    aliasEl.value = defaultAlias;
    overlay.dataset.aliasAutoValue = defaultAlias;
  },

  queueLookup(overlay) {
    clearTimeout(StockManagement._state.lookupTimer);
    const stockId = overlay.querySelector("#stock-id").value.trim();
    overlay.querySelector("#stock-name").value = "";
    const aliasEl = overlay.querySelector("#stock-alias");
    if (overlay.dataset.aliasTouched !== "true") {
      aliasEl.value = "";
      overlay.dataset.aliasAutoValue = "";
    }
    StockManagement._state.latestLookup = null;
    StockManagement.renderLookupPrice(overlay);
    if (!stockId) {
      StockManagement.renderLookupName(overlay, "等待输入股票代码");
      overlay.querySelector("#stock-lookup-hint").textContent = "";
      return;
    }
    StockManagement.renderLookupName(overlay, "检索中", true);
    StockManagement._state.lookupTimer = setTimeout(() => StockManagement.lookupInModal(overlay), 600);
  },

  renderLookupName(overlay, text, loading = false, options = {}) {
    const el = overlay.querySelector("#stock-name-inline");
    if (!el) return;
    if (loading) {
      el.innerHTML = `<span class="stock-lookup-spinner"></span><span>${StockManagement.escape(text)}</span>`;
      return;
    }
    el.innerHTML = `
      <span class="stock-name-placeholder">${StockManagement.escape(text)}</span>
      ${options.retry ? `<button class="stock-lookup-retry" type="button">重试</button>` : ""}
    `;
    const retryBtn = el.querySelector(".stock-lookup-retry");
    if (retryBtn) {
      retryBtn.addEventListener("click", event => {
        event.preventDefault();
        event.stopPropagation();
        StockManagement.lookupInModal(overlay);
      });
    }
  },

  renderLookupPrice(overlay, data = null) {
    const el = overlay.querySelector("#stock-live-price");
    if (!el) return;
    if (!data || data.current_price === null || data.current_price === undefined) {
      el.textContent = "";
      return;
    }
    el.textContent = `实时价：${StockManagement.formatMoney(data.current_price, data.stock_currency)}${data.from_cache ? "（缓存）" : ""}`;
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
      const isEdit = overlay.dataset.mode === "edit";
      const stockVid = overlay.dataset.stockVid;
      const result = isEdit
        ? await API.stockManagement.update(stockVid, payload)
        : await API.stockManagement.create(payload);
      overlay.remove();
      if (result.lookup_error) {
        showToast(`${isEdit ? "已更新" : "已保存"}，行情查询失败：${result.lookup_error}`);
      } else {
        showToast(isEdit ? "股票记录已更新" : "股票记录已保存");
      }
      await StockManagement.refreshAfterRecordChange(container);
    } catch (err) {
      const hintEl = overlay.querySelector("#stock-lookup-hint");
      hintEl.textContent = `保存失败：${err.message}`;
      hintEl.style.color = "var(--danger)";
    }
  },

  async refreshAfterRecordChange(container) {
    const expandedKey = StockManagement._state.expandedKey;
    const page = expandedKey ? ((StockManagement._state.recordPages[expandedKey] || {}).page || 1) : null;
    await StockManagement.loadSummary(container, { showLoading: false });
    const expandedItem = StockManagement._state.items.find(item => StockManagement.itemKey(item) === expandedKey);
    if (expandedItem && page) {
      await StockManagement.loadRecords(container, expandedKey, page);
    }
  },

  openDeleteConfirm(container, record) {
    const existing = document.querySelector(".modal-overlay");
    if (existing) existing.remove();
    const code = String(Math.floor(Math.random() * 900) + 100);
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML = `
      <div class="modal-dialog stock-delete-modal">
        <div class="modal-title">删除股票资产</div>
        <div class="stock-delete-message">该操作将删除本条股票资产，是否确认？</div>
        <div class="stock-delete-code">请输入确认码 <strong>${code}</strong></div>
        <input class="stock-delete-input" type="text" inputmode="numeric" maxlength="3" placeholder="输入3位数字确认">
        <div class="modal-buttons">
          <button class="btn btn-ghost" type="button" data-stock-delete-cancel>取消</button>
          <button class="btn btn-primary" type="button" data-stock-delete-confirm disabled>确认删除</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
    const input = overlay.querySelector(".stock-delete-input");
    const confirmBtn = overlay.querySelector("[data-stock-delete-confirm]");
    const close = () => overlay.remove();
    input.addEventListener("input", () => {
      input.value = input.value.replace(/\D/g, "").slice(0, 3);
      confirmBtn.disabled = input.value !== code;
    });
    overlay.querySelector("[data-stock-delete-cancel]").addEventListener("click", close);
    overlay.addEventListener("click", event => {
      if (event.target === overlay) close();
    });
    confirmBtn.addEventListener("click", async () => {
      if (input.value !== code) return;
      confirmBtn.disabled = true;
      confirmBtn.textContent = "删除中";
      try {
        await API.stockManagement.delete(record.stock_vid);
        close();
        showToast("股票资产已删除");
        await StockManagement.refreshAfterRecordChange(container);
      } catch (err) {
        confirmBtn.disabled = false;
        confirmBtn.textContent = "确认删除";
        showToast(`删除失败：${err.message}`);
      }
    });
    setTimeout(() => input.focus(), 50);
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
      body.innerHTML = `<div class="empty" style="color:var(--danger)">加载失败：${StockManagement.escape(err.message)}</div>`;
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
      return `<div class="empty" style="color:var(--danger)">Yahoo Finance 历史股息查询失败：${StockManagement.escape(yahooSection.error || "未知错误")}</div>`;
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
      return `<div class="empty" style="color:var(--danger)">同花顺分红数据查询失败：${StockManagement.escape(thsSection.error || "未知错误")}</div>`;
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
      body.innerHTML = `<div class="empty" style="color:var(--danger)">加载失败：${StockManagement.escape(err.message)}</div>`;
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
          ? `<div class="empty" style="color:var(--danger)">${StockManagement.escape(section.error || "查询失败")}</div>`
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

  dividendCellTitle(item) {
    if (item.stock_dividend_per_share_last_year === null || item.stock_dividend_per_share_last_year === undefined) {
      return "暂无缓存的股息汇总数据";
    }
    const year = item.stock_dividend_reference_year || "--";
    const frequency = item.stock_dividend_frequency ?? "--";
    return `${year} 年，每股派息，派息次数 ${frequency}`;
  },

  annualDividendValue(item) {
    if (!item) return null;
    const dividend = Number(item.stock_dividend_per_share_last_year);
    const amount = Number(item.stock_amount);
    if (!Number.isFinite(dividend) || !Number.isFinite(amount)) return null;
    return dividend * amount;
  },

  renderAnnualDividend(item, loading) {
    if (loading) return StockManagement.loadingDots();
    return StockManagement.formatMoneyInteger(StockManagement.annualDividendValue(item), item.stock_currency);
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

  formatMoneyInteger(value, currency) {
    if (value === null || value === undefined) return "--";
    const symbol = currency === "USD" ? "$" : "¥";
    return `${symbol}${Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 0 })}`;
  },

  formatPercent(value) {
    if (value === null || value === undefined) return "--";
    return `${Number(value).toFixed(1)}%`;
  },

  formatDividendRate(dividend, base) {
    if (dividend === null || dividend === undefined || base === null || base === undefined || Number(base) === 0) return "--";
    return StockManagement.formatPercent(Number(dividend) / Number(base) * 100);
  },

  rateValue(dividend, base) {
    if (dividend === null || dividend === undefined || base === null || base === undefined || Number(base) === 0) return null;
    return Number(dividend) / Number(base) * 100;
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
