Object.assign(StockManagement, {
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
  }
});
