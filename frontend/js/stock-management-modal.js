Object.assign(StockManagement, {
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
  }
});
