Object.assign(StockManagement, {
  loadingDots() {
    return `<span class="stock-metric-loading" aria-label="加载中"><span></span><span></span><span></span></span>`;
  },

  inlineLoadingDots(label = "加载中") {
    return `<span class="stock-inline-loading">${StockManagement.loadingDots().replace('aria-label="加载中"', `aria-label="${StockManagement.escape(label)}"`)}</span>`;
  },

  renderEmptyTableRow(colspan) {
    return `<tr><td class="stock-empty-table-cell" colspan="${colspan}">当前无数据</td></tr>`;
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
  }
});
