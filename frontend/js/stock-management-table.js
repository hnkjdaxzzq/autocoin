Object.assign(StockManagement, {
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
  }
});
