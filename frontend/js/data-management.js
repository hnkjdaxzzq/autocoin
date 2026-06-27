/* ===== DataManagement page ===== */
const DataManagement = {
  _state: {
    page: 1,
    page_size: 50,
    total: 0,
    total_pages: 1,
    filters: {},
    selectedIds: new Set(),
    categories: [],
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

  render(container) {
    const now = new Date();
    const today = DataManagement._formatLocalDate(now);
    const yearStart = `${now.getFullYear()}-01-01`;

    container.innerHTML = `
      <div class="page-header">
        <div style="display:flex;gap:14px;flex-wrap:wrap;align-items:center">
          <h1 class="page-title">数据管理</h1>
          <label class="title-date-filter">日期范围
            <input type="date" id="f-start" value="${yearStart}" placeholder="开始日期">
            <span style="color:#94a3b8">—</span>
            <input type="date" id="f-end" value="${today}" placeholder="结束日期">
          </label>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
          <input type="file" id="backup-file-input" accept=".csv,text/csv" style="display:none">
          <button class="btn btn-ghost" id="btn-import-backup" type="button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            导入备份数据
          </button>
          <button class="btn btn-primary" id="btn-backup-all" type="button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            备份所有数据
          </button>
        </div>
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
        <label>来源
          <select id="f-source">
            <option value="">全部</option>
            ${DataManagement._sourceOptions.map(source => `<option value="${source}">${source}</option>`).join("")}
          </select>
        </label>
        <label>分类
          <select id="f-category">
            <option value="">全部</option>
          </select>
        </label>
        <input type="text" id="f-search" placeholder="搜索对方/商品/备注…" style="min-width:180px">
        <button class="btn btn-primary" id="btn-search">搜索</button>
        <button class="btn btn-ghost" id="btn-reset">重置</button>
      </div>

      <!-- Batch action bar (hidden until selection) -->
      <div class="batch-bar" id="batch-bar" style="display:none">
        <span id="batch-count">已选 0 条</span>
        <select id="batch-category" style="font-size:13px;padding:4px 8px;border:1px solid var(--border);border-radius:6px">
          <option value="">批量改分类…</option>
        </select>
        <button class="btn btn-ghost btn-sm" id="btn-batch-category">应用分类</button>
        <button class="btn btn-danger btn-sm" id="btn-batch-delete">软删除数据</button>
        <button class="btn btn-danger btn-sm" id="btn-batch-hard-delete">物理删除数据</button>
        <button class="btn btn-ghost btn-sm" id="btn-batch-clear">取消选择</button>
      </div>

      <div class="summary-grid" id="tx-summary"></div>

      <div class="table-wrap" id="tx-table-wrap">
        <div class="loading">加载中...</div>
      </div>
    `;

    DataManagement._state.page = 1;
    DataManagement._state.selectedIds = new Set();
    DataManagement._bindFilters(container);
    DataManagement._bindBackup(container);
    DataManagement._bindBatch(container);
    DataManagement._loadCategories(container);
    DataManagement._load(container);
  },

  async _loadCategories(container) {
    try {
      const res = await API.transactions.categories();
      DataManagement._state.categories = res.categories || [];
      // Populate datalist and batch dropdown
      const dl = container.querySelector("#category-datalist");
      const batchSel = container.querySelector("#batch-category");
      const filterSel = container.querySelector("#f-category");
      if (dl) {
        dl.innerHTML = DataManagement._state.categories.map(c => `<option value="${c}">`).join("");
      }
      if (batchSel) {
        batchSel.innerHTML = '<option value="">批量改分类…</option>' +
          DataManagement._state.categories.map(c => `<option value="${c}">${c}</option>`).join("");
      }
      if (filterSel) {
        const current = filterSel.value;
        filterSel.innerHTML = '<option value="">全部</option>' +
          DataManagement._state.categories.map(c => `<option value="${c}">${c}</option>`).join("");
        filterSel.value = current;
      }
    } catch (_) {}
  },

  _bindBackup(container) {
    const backupBtn = container.querySelector("#btn-backup-all");
    const importBtn = container.querySelector("#btn-import-backup");
    const fileInput = container.querySelector("#backup-file-input");

    backupBtn.addEventListener("click", async () => {
      const confirmed = await DataManagement._showConfirm({
        title: "备份所有数据",
        body: "确认后将生成当前数据库所有表和数据的备份文件，并由浏览器下载。",
        confirmText: "确认备份",
      });
      if (!confirmed) return;

      backupBtn.disabled = true;
      try {
        await API.dataManagement.exportBackup();
      } catch (e) {
        DataManagement._showToast("备份失败: " + e.message);
      } finally {
        backupBtn.disabled = false;
      }
    });

    importBtn.addEventListener("click", () => {
      fileInput.value = "";
      fileInput.click();
    });

    fileInput.addEventListener("change", async () => {
      const file = fileInput.files && fileInput.files[0];
      if (!file) return;

      importBtn.disabled = true;
      try {
        await API.dataManagement.validateBackup(file);
        const confirmed = await DataManagement._showRestoreConfirm();
        if (!confirmed) return;

        await API.dataManagement.restoreBackup(file);
        DataManagement._state.selectedIds.clear();
        DataManagement._showToast("数据还原成功");
        DataManagement._loadCategories(container);
        DataManagement._load(container);
      } catch (e) {
        DataManagement._showToast(e.message || "数据错误，请检查上传的备份数据。");
      } finally {
        importBtn.disabled = false;
        fileInput.value = "";
      }
    });
  },

  _showConfirm({ title, body, confirmText = "确认", cancelText = "取消" }) {
    return new Promise((resolve) => {
      DataManagement._removeModal();
      const overlay = document.createElement("div");
      overlay.className = "modal-overlay";
      overlay.innerHTML = `
        <div class="modal-dialog modal-dialog-sm">
          <div class="modal-title">${title}</div>
          <div class="modal-body">${body}</div>
          <div class="modal-buttons">
            <button class="btn btn-primary" id="modal-confirm">${confirmText}</button>
            <button class="btn btn-ghost" id="modal-cancel">${cancelText}</button>
          </div>
        </div>
      `;
      document.body.appendChild(overlay);
      overlay.querySelector("#modal-confirm").addEventListener("click", () => {
        DataManagement._removeModal();
        resolve(true);
      });
      overlay.querySelector("#modal-cancel").addEventListener("click", () => {
        DataManagement._removeModal();
        resolve(false);
      });
    });
  },

  _showRestoreConfirm() {
    return new Promise((resolve) => {
      DataManagement._removeModal();
      let code = DataManagement._randomCode();
      const overlay = document.createElement("div");
      overlay.className = "modal-overlay";
      overlay.innerHTML = `
        <div class="modal-dialog modal-dialog-sm">
          <div class="modal-title">导入备份数据</div>
          <div class="modal-body">
            <p>该操作将清空当前所有数据并还原导入的数据，请谨慎操作，如需继续请输入以下数字：</p>
            <div class="backup-confirm-code" id="backup-confirm-code">${code}</div>
            <input class="backup-confirm-input" id="backup-confirm-input" type="text" inputmode="numeric" autocomplete="off" maxlength="5">
          </div>
          <div class="modal-buttons">
            <button class="btn btn-danger" id="modal-confirm">确认还原</button>
            <button class="btn btn-ghost" id="modal-cancel">取消</button>
          </div>
        </div>
      `;
      document.body.appendChild(overlay);
      const input = overlay.querySelector("#backup-confirm-input");
      input.focus();

      overlay.querySelector("#modal-confirm").addEventListener("click", () => {
        if (input.value.trim() !== code) {
          DataManagement._showToast("输入有误，请重新输入");
          code = DataManagement._randomCode();
          overlay.querySelector("#backup-confirm-code").textContent = code;
          input.value = "";
          input.focus();
          return;
        }
        DataManagement._removeModal();
        resolve(true);
      });
      overlay.querySelector("#modal-cancel").addEventListener("click", () => {
        DataManagement._removeModal();
        resolve(false);
      });
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") overlay.querySelector("#modal-confirm").click();
        if (e.key === "Escape") overlay.querySelector("#modal-cancel").click();
      });
    });
  },

  _removeModal() {
    const existing = document.querySelector(".modal-overlay");
    if (existing) existing.remove();
  },

  _randomCode() {
    return String(Math.floor(10000 + Math.random() * 90000));
  },

  _showToast(message) {
    const existing = document.querySelector(".toast-message");
    if (existing) existing.remove();
    const toast = document.createElement("div");
    toast.className = "toast-message";
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.classList.add("show"), 10);
    setTimeout(() => {
      toast.classList.remove("show");
      setTimeout(() => toast.remove(), 200);
    }, 2600);
  },

  _bindBatch(container) {
    container.querySelector("#btn-batch-delete").addEventListener("click", async () => {
      const ids = Array.from(DataManagement._state.selectedIds);
      if (!ids.length) return;
      if (!confirm(`确定软删除选中的 ${ids.length} 条记录？`)) return;
      try {
        await API.transactions.batchDelete(ids);
        DataManagement._state.selectedIds.clear();
        DataManagement._load(container);
      } catch (e) { alert("批量删除失败: " + e.message); }
    });
    const hardDeleteBtn = container.querySelector("#btn-batch-hard-delete");
    if (hardDeleteBtn) {
      hardDeleteBtn.addEventListener("click", async () => {
        const ids = Array.from(DataManagement._state.selectedIds);
        if (!ids.length) return;
        if (!confirm(`确定物理删除选中的 ${ids.length} 条记录？此操作不可恢复。`)) return;
        try {
          await API.transactions.batchHardDelete(ids);
          DataManagement._state.selectedIds.clear();
          DataManagement._load(container);
        } catch (e) { alert("物理删除失败: " + e.message); }
      });
    }
    container.querySelector("#btn-batch-category").addEventListener("click", async () => {
      const ids = Array.from(DataManagement._state.selectedIds);
      const cat = container.querySelector("#batch-category").value;
      if (!ids.length || !cat) { alert("请先选择记录和分类"); return; }
      try {
        await API.transactions.batchUpdate(ids, { category: cat });
        DataManagement._state.selectedIds.clear();
        DataManagement._load(container);
      } catch (e) { alert("批量更新失败: " + e.message); }
    });
    container.querySelector("#btn-batch-clear").addEventListener("click", () => {
      DataManagement._state.selectedIds.clear();
      DataManagement._updateBatchBar(container);
      container.querySelectorAll(".tx-row-check").forEach(c => c.checked = false);
      const sa = container.querySelector("#tx-select-all");
      if (sa) sa.checked = false;
    });
  },

  _updateBatchBar(container) {
    const bar = container.querySelector("#batch-bar");
    const cnt = DataManagement._state.selectedIds.size;
    bar.style.display = cnt > 0 ? "flex" : "none";
    container.querySelector("#batch-count").textContent = `已选 ${cnt} 条`;
  },

  _bindFilters(container) {
    container.querySelector("#btn-search").addEventListener("click", () => {
      DataManagement._state.page = 1;
      DataManagement._load(container);
    });

    container.querySelector("#btn-reset").addEventListener("click", () => {
      const now = new Date();
      container.querySelector("#f-start").value = `${now.getFullYear()}-01-01`;
      container.querySelector("#f-end").value = DataManagement._formatLocalDate(now);
      container.querySelector("#f-direction").value = "";
      container.querySelector("#f-source").value = "";
      container.querySelector("#f-category").value = "";
      container.querySelector("#f-search").value = "";
      DataManagement._state.page = 1;
      DataManagement._load(container);
    });

    // Search on Enter key
    container.querySelector("#f-search").addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        DataManagement._state.page = 1;
        DataManagement._load(container);
      }
    });
  },

  _formatLocalDate(date) {
    return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`;
  },

  _getFilters(container) {
    return {
      start_date: container.querySelector("#f-start").value || "",
      end_date: container.querySelector("#f-end").value || "",
      direction: container.querySelector("#f-direction").value || "",
      source: container.querySelector("#f-source").value || "",
      category: container.querySelector("#f-category").value || "",
      search: container.querySelector("#f-search").value || "",
    };
  },

  async _load(container) {
    const wrap = container.querySelector("#tx-table-wrap");
    wrap.innerHTML = `<div class="loading">加载中...</div>`;
    const filters = DataManagement._getFilters(container);
    try {
      const data = await API.transactions.list({
        ...filters,
        page: DataManagement._state.page,
        page_size: DataManagement._state.page_size,
      });
      DataManagement._state.total = data.total;
      DataManagement._state.total_pages = data.total_pages;
      DataManagement._renderSummary(container, data.summary);
      DataManagement._render(wrap, data, container);
    } catch (err) {
      showError(wrap, err.message);
    }
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
              <td><input type="checkbox" class="tx-row-check" data-id="${tx.id}" ${DataManagement._state.selectedIds.has(tx.id) ? "checked" : ""}></td>
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
      ${DataManagement._renderPagination(data)}
    `;

    // Bind select-all
    const selectAll = wrap.querySelector("#tx-select-all");
    selectAll.addEventListener("change", () => {
      wrap.querySelectorAll(".tx-row-check").forEach(cb => {
        cb.checked = selectAll.checked;
        const id = parseInt(cb.dataset.id);
        if (selectAll.checked) DataManagement._state.selectedIds.add(id);
        else DataManagement._state.selectedIds.delete(id);
      });
      DataManagement._updateBatchBar(container);
    });

    // Bind row checkboxes
    wrap.querySelectorAll(".tx-row-check").forEach(cb => {
      cb.addEventListener("change", () => {
        const id = parseInt(cb.dataset.id);
        if (cb.checked) DataManagement._state.selectedIds.add(id);
        else DataManagement._state.selectedIds.delete(id);
        DataManagement._updateBatchBar(container);
      });
    });

    // Bind category inline edit
    wrap.querySelectorAll(".category-cell").forEach(cell => {
      cell.addEventListener("click", () => DataManagement._inlineEdit(cell, container));
    });

    // Bind delete buttons
    wrap.querySelectorAll(".btn-delete").forEach(btn => {
      btn.addEventListener("click", async () => {
        if (!confirm("确认删除这条账单记录？")) return;
        try {
          await API.transactions.delete(parseInt(btn.dataset.id));
          DataManagement._load(container);
        } catch (err) {
          alert("删除失败: " + err.message);
        }
      });
    });

    // Bind pagination
    wrap.querySelectorAll(".page-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const p = parseInt(btn.dataset.page);
        if (p && p !== DataManagement._state.page) {
          DataManagement._state.page = p;
          DataManagement._load(container);
        }
      });
    });

    DataManagement._updateBatchBar(container);
  },

  _renderPagination(data) {
    const { page, total_pages, total } = { page: data.page, total_pages: data.total_pages, total: data.total };
    const pgs = DataManagement._paginationItems(page, total_pages).map(item => (
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
    const cats = DataManagement._state.categories;
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
        cell.addEventListener("click", () => DataManagement._inlineEdit(cell, container));
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
