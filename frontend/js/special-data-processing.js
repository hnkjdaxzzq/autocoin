/* ===== Special Data Processing page ===== */
const SpecialDataProcessing = {
  _state: {
    result: null,
    page: 1,
    pageSize: 50,
    selections: new Map(),
    wealthResult: null,
    wealthPage: 1,
    wealthSelections: new Map(),
  },

  render(container) {
    container.innerHTML = `
      <div class="page-header">
        <div>
          <h1 class="page-title">特殊数据处理</h1>
          <p style="margin-top:6px;color:var(--text-muted);font-size:14px">处理需要人工确认的特殊账单数据。</p>
        </div>
      </div>

      <div class="summary-card" style="max-width:560px;margin-bottom:16px">
        <div class="label">退款数据处理</div>
        <div style="margin:8px 0 16px;color:var(--text-muted);font-size:14px;line-height:1.6">
          查询微信、支付宝和汇丰 PULSE 中尚未确认过的疑似退款数据，并选择对应支出记录后批量处理为“不计”。
        </div>
        <button class="btn btn-primary" id="btn-search-refunds" type="button">
          查询所有疑似退款数据
        </button>
      </div>

      <div class="summary-card" style="max-width:560px">
        <div class="label">理财数据检查</div>
        <div style="margin:8px 0 16px;color:var(--text-muted);font-size:14px;line-height:1.6">
          检查支付宝余额宝相关交易，并按需批量标记为“不计”。
        </div>
        <button class="btn btn-primary" id="btn-search-wealth" type="button">
          检查理财数据
        </button>
      </div>
    `;

    container.querySelector("#btn-search-refunds").addEventListener("click", () => {
      SpecialDataProcessing._searchRefunds(container);
    });
    container.querySelector("#btn-search-wealth").addEventListener("click", () => {
      SpecialDataProcessing._searchWealth(container);
    });
  },

  async _searchRefunds(container) {
    const btn = container.querySelector("#btn-search-refunds");
    btn.disabled = true;
    btn.textContent = "查询中...";
    try {
      const result = await API.specialDataProcessing.searchRefunds();
      SpecialDataProcessing._state.result = result;
      SpecialDataProcessing._state.page = 1;
      SpecialDataProcessing._initSelections(result);
      SpecialDataProcessing._showRefundModal();
    } catch (err) {
      showToast("查询失败: " + err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "查询所有疑似退款数据";
    }
  },

  _initSelections(result) {
    SpecialDataProcessing._state.selections = new Map();
    (result.items || []).forEach(item => {
      const refundId = item.refund_transaction.id;
      const firstCandidate = item.expense_candidates && item.expense_candidates[0];
      SpecialDataProcessing._state.selections.set(refundId, {
        markNeutral: true,
        selectedExpenseId: firstCandidate ? firstCandidate.id : null,
      });
    });
  },

  async _searchWealth(container) {
    const btn = container.querySelector("#btn-search-wealth");
    btn.disabled = true;
    btn.textContent = "检查中...";
    try {
      const result = await API.specialDataProcessing.searchWealth();
      SpecialDataProcessing._state.wealthResult = result;
      SpecialDataProcessing._state.wealthPage = 1;
      SpecialDataProcessing._initWealthSelections(result);
      SpecialDataProcessing._showWealthModal();
    } catch (err) {
      showToast("检查失败: " + err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "检查理财数据";
    }
  },

  _initWealthSelections(result) {
    SpecialDataProcessing._state.wealthSelections = new Map();
    (result.items || []).forEach(tx => {
      SpecialDataProcessing._state.wealthSelections.set(tx.id, true);
    });
  },

  _showRefundModal() {
    SpecialDataProcessing._removeModal();
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.id = "refund-processing-overlay";
    document.body.appendChild(overlay);
    SpecialDataProcessing._renderRefundModal(overlay);
  },

  _showWealthModal() {
    SpecialDataProcessing._removeModal();
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.id = "wealth-processing-overlay";
    document.body.appendChild(overlay);
    SpecialDataProcessing._renderWealthModal(overlay);
  },

  _renderRefundModal(overlay) {
    const result = SpecialDataProcessing._state.result || { items: [] };
    const items = result.items || [];
    const totalPages = Math.max(1, Math.ceil(items.length / SpecialDataProcessing._state.pageSize));
    const page = Math.min(SpecialDataProcessing._state.page, totalPages);
    SpecialDataProcessing._state.page = page;
    const start = (page - 1) * SpecialDataProcessing._state.pageSize;
    const pageItems = items.slice(start, start + SpecialDataProcessing._state.pageSize);
    const hasItems = items.length > 0;

    overlay.innerHTML = `
      <div class="modal-dialog modal-dialog-lg refund-modal-dialog">
        <div class="modal-title">退款数据处理</div>
        <div class="modal-body">
          <div style="color:var(--text-muted);font-size:14px;margin-bottom:12px">
            检索到 ${result.suspected_total || 0} 条疑似退款数据，其中 ${result.matched_total || 0} 条匹配到支出候选。
          </div>
          ${hasItems ? SpecialDataProcessing._renderRefundTable(pageItems) : `<div class="empty">没有匹配到可处理的支出候选</div>`}
          ${hasItems ? SpecialDataProcessing._renderPagination(page, totalPages, items.length) : ""}
        </div>
        <div class="modal-buttons">
          ${hasItems ? `
            <button class="btn btn-primary" id="refund-confirm">确认处理数据</button>
            <button class="btn btn-ghost" id="refund-cancel">取消</button>
          ` : `
            <button class="btn btn-primary" id="refund-close">确认</button>
          `}
        </div>
      </div>
    `;

    const cancelBtn = overlay.querySelector("#refund-cancel");
    const closeBtn = overlay.querySelector("#refund-close");
    if (cancelBtn) cancelBtn.addEventListener("click", () => {
      SpecialDataProcessing._removeModal();
    });
    if (closeBtn) closeBtn.addEventListener("click", () => {
      SpecialDataProcessing._removeModal();
    });
    const confirmBtn = overlay.querySelector("#refund-confirm");
    if (confirmBtn) {
      confirmBtn.addEventListener("click", () => SpecialDataProcessing._confirmRefunds(confirmBtn));
    }
    overlay.querySelectorAll(".refund-neutral-check").forEach(cb => {
      cb.addEventListener("change", () => {
        const id = parseInt(cb.dataset.refundId);
        const current = SpecialDataProcessing._state.selections.get(id) || {};
        current.markNeutral = cb.checked;
        SpecialDataProcessing._state.selections.set(id, current);
      });
    });
    overlay.querySelectorAll(".refund-expense-radio").forEach(radio => {
      radio.addEventListener("change", () => {
        if (!radio.checked) return;
        const id = parseInt(radio.dataset.refundId);
        const current = SpecialDataProcessing._state.selections.get(id) || {};
        current.selectedExpenseId = parseInt(radio.value);
        SpecialDataProcessing._state.selections.set(id, current);
      });
    });
    overlay.querySelectorAll(".page-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const nextPage = parseInt(btn.dataset.page);
        if (!nextPage || nextPage === SpecialDataProcessing._state.page) return;
        SpecialDataProcessing._state.page = nextPage;
        SpecialDataProcessing._renderRefundModal(overlay);
      });
    });
  },

  _renderWealthModal(overlay) {
    const result = SpecialDataProcessing._state.wealthResult || { items: [] };
    const items = result.items || [];
    const totalPages = Math.max(1, Math.ceil(items.length / SpecialDataProcessing._state.pageSize));
    const page = Math.min(SpecialDataProcessing._state.wealthPage, totalPages);
    SpecialDataProcessing._state.wealthPage = page;
    const start = (page - 1) * SpecialDataProcessing._state.pageSize;
    const pageItems = items.slice(start, start + SpecialDataProcessing._state.pageSize);
    const hasItems = items.length > 0;

    overlay.innerHTML = `
      <div class="modal-dialog modal-dialog-lg refund-modal-dialog">
        <div class="modal-title">理财数据检查</div>
        <div class="modal-body">
          <div style="color:var(--text-muted);font-size:14px;margin-bottom:12px">
            检测到 ${result.total || 0} 条疑似理财数据。
          </div>
          ${hasItems ? SpecialDataProcessing._renderWealthTable(pageItems) : `<div class="empty">没有检测到匹配的理财数据</div>`}
          ${hasItems ? SpecialDataProcessing._renderWealthPagination(page, totalPages, items.length) : ""}
        </div>
        <div class="modal-buttons">
          ${hasItems ? `
            <button class="btn btn-primary" id="wealth-confirm">确认处理数据</button>
            <button class="btn btn-ghost" id="wealth-cancel">取消</button>
          ` : `
            <button class="btn btn-primary" id="wealth-close">确认</button>
          `}
        </div>
      </div>
    `;

    const cancelBtn = overlay.querySelector("#wealth-cancel");
    const closeBtn = overlay.querySelector("#wealth-close");
    if (cancelBtn) cancelBtn.addEventListener("click", () => {
      SpecialDataProcessing._removeModal();
    });
    if (closeBtn) closeBtn.addEventListener("click", () => {
      SpecialDataProcessing._removeModal();
    });
    const confirmBtn = overlay.querySelector("#wealth-confirm");
    if (confirmBtn) {
      confirmBtn.addEventListener("click", () => SpecialDataProcessing._confirmWealth(confirmBtn));
    }
    overlay.querySelectorAll(".wealth-neutral-check").forEach(cb => {
      cb.addEventListener("change", () => {
        const id = parseInt(cb.dataset.txId);
        SpecialDataProcessing._state.wealthSelections.set(id, cb.checked);
      });
    });
    overlay.querySelectorAll(".wealth-page-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const nextPage = parseInt(btn.dataset.page);
        if (!nextPage || nextPage === SpecialDataProcessing._state.wealthPage) return;
        SpecialDataProcessing._state.wealthPage = nextPage;
        SpecialDataProcessing._renderWealthModal(overlay);
      });
    });
  },

  _renderRefundTable(items) {
    return `
      <div class="modal-table-wrap refund-table-wrap">
        <table class="modal-table refund-result-table">
          <thead>
            <tr>
              <th>处理为“不计”</th>
              <th>疑似退款数据</th>
              <th>支出候选</th>
            </tr>
          </thead>
          <tbody>
            ${items.map(item => SpecialDataProcessing._renderRefundRow(item)).join("")}
          </tbody>
        </table>
      </div>
    `;
  },

  _renderRefundRow(item) {
    const refund = item.refund_transaction;
    const selection = SpecialDataProcessing._state.selections.get(refund.id) || {};
    const candidates = item.expense_candidates || [];
    return `
      <tr>
        <td>
          <input type="checkbox" class="refund-neutral-check" data-refund-id="${refund.id}" ${selection.markNeutral !== false ? "checked" : ""}>
        </td>
        <td class="refund-tx-cell">
          ${SpecialDataProcessing._renderTxSummary(refund)}
        </td>
        <td class="refund-candidates-cell">
          ${candidates.map(candidate => `
            <label class="refund-candidate-option">
              <input type="radio" class="refund-expense-radio" name="refund-expense-${refund.id}" data-refund-id="${refund.id}" value="${candidate.id}" ${selection.selectedExpenseId === candidate.id ? "checked" : ""}>
              <span>${SpecialDataProcessing._renderTxSummary(candidate)}</span>
            </label>
          `).join("")}
        </td>
      </tr>
    `;
  },

  _renderWealthTable(items) {
    return `
      <div class="modal-table-wrap refund-table-wrap">
        <table class="modal-table refund-result-table">
          <thead>
            <tr>
              <th>标为“不计”</th>
              <th>交易数据</th>
            </tr>
          </thead>
          <tbody>
            ${items.map(tx => SpecialDataProcessing._renderWealthRow(tx)).join("")}
          </tbody>
        </table>
      </div>
    `;
  },

  _renderWealthRow(tx) {
    const checked = SpecialDataProcessing._state.wealthSelections.get(tx.id) !== false;
    return `
      <tr>
        <td>
          <input type="checkbox" class="wealth-neutral-check" data-tx-id="${tx.id}" ${checked ? "checked" : ""}>
        </td>
        <td class="refund-tx-cell">
          ${SpecialDataProcessing._renderTxSummary(tx)}
        </td>
      </tr>
    `;
  },

  _renderTxSummary(tx) {
    return `
      <div class="refund-tx-summary">
        <div><strong>${fmtDate(tx.transaction_time)}</strong> · ${SpecialDataProcessing._escape(tx.source || "—")} · ${directionBadge(tx.direction)}</div>
        <div>${SpecialDataProcessing._escape(tx.counterparty || "—")} · ${SpecialDataProcessing._escape(tx.payment_method || "—")} · <strong>${fmtMoney(tx.amount)}</strong></div>
        <div title="${SpecialDataProcessing._escape(tx.product || "")}">${SpecialDataProcessing._escape(tx.product || "—")}</div>
      </div>
    `;
  },

  _renderPagination(page, totalPages, total) {
    const buttons = DataManagement._paginationItems(page, totalPages).map(item => (
      `<button class="page-btn ${item.page === page ? "active" : ""}" data-page="${item.page}">${item.label}</button>`
    ));
    return `
      <div class="pagination">
        <span class="info">共 ${total} 条疑似退款</span>
        <button class="page-btn" data-page="${page - 1}" ${page <= 1 ? "disabled" : ""}>‹ 上一页</button>
        ${buttons.join("")}
        <button class="page-btn" data-page="${page + 1}" ${page >= totalPages ? "disabled" : ""}>下一页 ›</button>
      </div>
    `;
  },

  _renderWealthPagination(page, totalPages, total) {
    const buttons = DataManagement._paginationItems(page, totalPages).map(item => (
      `<button class="page-btn wealth-page-btn ${item.page === page ? "active" : ""}" data-page="${item.page}">${item.label}</button>`
    ));
    return `
      <div class="pagination">
        <span class="info">共 ${total} 条疑似理财数据</span>
        <button class="page-btn wealth-page-btn" data-page="${page - 1}" ${page <= 1 ? "disabled" : ""}>‹ 上一页</button>
        ${buttons.join("")}
        <button class="page-btn wealth-page-btn" data-page="${page + 1}" ${page >= totalPages ? "disabled" : ""}>下一页 ›</button>
      </div>
    `;
  },

  async _confirmRefunds(confirmBtn) {
    const result = SpecialDataProcessing._state.result || { items: [] };
    const items = (result.items || []).map(item => {
      const refundId = item.refund_transaction.id;
      const selection = SpecialDataProcessing._state.selections.get(refundId) || {};
      return {
        refund_id: refundId,
        selected_expense_id: selection.selectedExpenseId || null,
        mark_neutral: selection.markNeutral !== false,
      };
    });
    confirmBtn.disabled = true;
    confirmBtn.textContent = "处理中...";
    try {
      const res = await API.specialDataProcessing.confirmRefunds(items);
      SpecialDataProcessing._removeModal();
      showToast(`处理完成：标记 ${res.marked_refunds || 0} 条疑似退款，${res.marked_expenses || 0} 条支出候选`);
    } catch (err) {
      showToast("处理失败: " + err.message);
      confirmBtn.disabled = false;
      confirmBtn.textContent = "确认处理数据";
    }
  },

  async _confirmWealth(confirmBtn) {
    const result = SpecialDataProcessing._state.wealthResult || { items: [] };
    const ids = (result.items || [])
      .map(tx => tx.id)
      .filter(id => SpecialDataProcessing._state.wealthSelections.get(id) !== false);

    confirmBtn.disabled = true;
    confirmBtn.textContent = "处理中...";
    try {
      const res = await API.specialDataProcessing.confirmWealth(ids);
      SpecialDataProcessing._removeModal();
      showToast(`处理完成：已将 ${res.updated || 0} 条理财数据标为“不计”`);
    } catch (err) {
      showToast("处理失败: " + err.message);
      confirmBtn.disabled = false;
      confirmBtn.textContent = "确认处理数据";
    }
  },

  _removeModal() {
    ["refund-processing-overlay", "wealth-processing-overlay"].forEach(id => {
      const existing = document.getElementById(id);
      if (existing) existing.remove();
    });
  },

  _escape(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  },
};
