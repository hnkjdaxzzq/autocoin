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
  }
};