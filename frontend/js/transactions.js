/* ===== Transactions page ===== */
const Transactions = {
  _state: {
    page: 1,
    page_size: 50,
    total: 0,
    total_pages: 1,
    filters: {},
  },

  render(container) {
    const now = new Date();
    const defaultTime = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-${String(now.getDate()).padStart(2,"0")}T${String(now.getHours()).padStart(2,"0")}:${String(now.getMinutes()).padStart(2,"0")}`;

    container.innerHTML = `
      <div class="page-header">
        <h1 class="page-title">账单明细</h1>
        <button class="btn btn-primary" id="btn-toggle-form">+ 手动记账</button>
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
            <input type="text" id="m-category" placeholder="如：餐饮美食、交通出行">
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
        <label>日期范围
          <input type="date" id="f-start" placeholder="开始日期">
          <span style="color:#94a3b8">—</span>
          <input type="date" id="f-end" placeholder="结束日期">
        </label>
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
            <option value="alipay">支付宝</option>
            <option value="wechat">微信支付</option>
            <option value="manual">手动录入</option>
          </select>
        </label>
        <input type="text" id="f-search" placeholder="搜索对方/商品/备注…" style="min-width:180px">
        <button class="btn btn-primary" id="btn-search">搜索</button>
        <button class="btn btn-ghost" id="btn-reset">重置</button>
      </div>

      <div class="summary-grid" id="tx-summary"></div>

      <div class="table-wrap" id="tx-table-wrap">
        <div class="loading">加载中...</div>
      </div>
    `;

    Transactions._state.page = 1;
    Transactions._bindFilters(container);
    Transactions._bindManualForm(container);
    Transactions._load(container);
  },

  _bindFilters(container) {
    container.querySelector("#btn-search").addEventListener("click", () => {
      Transactions._state.page = 1;
      Transactions._load(container);
    });

    container.querySelector("#btn-reset").addEventListener("click", () => {
      container.querySelector("#f-start").value = "";
      container.querySelector("#f-end").value = "";
      container.querySelector("#f-direction").value = "";
      container.querySelector("#f-source").value = "";
      container.querySelector("#f-search").value = "";
      Transactions._state.page = 1;
      Transactions._load(container);
    });

    // Search on Enter key
    container.querySelector("#f-search").addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        Transactions._state.page = 1;
        Transactions._load(container);
      }
    });
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
        Transactions._state.page = 1;
        Transactions._load(container);
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
      source: container.querySelector("#f-source").value || "",
      search: container.querySelector("#f-search").value || "",
    };
  },

  async _load(container) {
    const wrap = container.querySelector("#tx-table-wrap");
    wrap.innerHTML = `<div class="loading">加载中...</div>`;
    const filters = Transactions._getFilters(container);
    try {
      const data = await API.transactions.list({
        ...filters,
        page: Transactions._state.page,
        page_size: Transactions._state.page_size,
      });
      Transactions._state.total = data.total;
      Transactions._state.total_pages = data.total_pages;
      Transactions._renderSummary(container, data.summary);
      Transactions._render(wrap, data, container);
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
            <th>时间</th>
            <th>来源</th>
            <th>分类</th>
            <th>交易对方</th>
            <th>商品</th>
            <th>方向</th>
            <th style="text-align:right">金额</th>
            <th>支付方式</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          ${data.items.map(tx => `
            <tr data-id="${tx.id}">
              <td style="white-space:nowrap">${fmtDate(tx.transaction_time)}</td>
              <td>${tx.source === "alipay" ? "支付宝" : tx.source === "wechat" ? "微信" : "手动"}</td>
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
              <td style="text-align:right;font-weight:600;
                color:${tx.direction === "income" ? "var(--income)" : tx.direction === "expense" ? "var(--expense)" : "inherit"}">
                ${fmtMoney(tx.amount)}
              </td>
              <td style="max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                ${tx.payment_method || "—"}
              </td>
              <td>
                <button class="btn btn-danger btn-sm btn-delete" data-id="${tx.id}"
                  style="padding:2px 8px;font-size:12px">删除</button>
              </td>
            </tr>`).join("")}
        </tbody>
      </table>
      ${Transactions._renderPagination(data)}
    `;

    // Bind category inline edit
    wrap.querySelectorAll(".category-cell").forEach(cell => {
      cell.addEventListener("click", () => Transactions._inlineEdit(cell, container));
    });

    // Bind delete buttons
    wrap.querySelectorAll(".btn-delete").forEach(btn => {
      btn.addEventListener("click", async () => {
        if (!confirm("确认删除这条账单记录？")) return;
        try {
          await API.transactions.delete(parseInt(btn.dataset.id));
          Transactions._load(container);
        } catch (err) {
          alert("删除失败: " + err.message);
        }
      });
    });

    // Bind pagination
    wrap.querySelectorAll(".page-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const p = parseInt(btn.dataset.page);
        if (p && p !== Transactions._state.page) {
          Transactions._state.page = p;
          Transactions._load(container);
        }
      });
    });
  },

  _renderPagination(data) {
    const { page, total_pages, total } = { page: data.page, total_pages: data.total_pages, total: data.total };
    const pgs = [];
    const start = Math.max(1, page - 2);
    const end = Math.min(total_pages, page + 2);
    for (let i = start; i <= end; i++) {
      pgs.push(`<button class="page-btn ${i === page ? "active" : ""}" data-page="${i}">${i}</button>`);
    }
    return `
      <div class="pagination">
        <span class="info">共 ${total} 条</span>
        <button class="page-btn" data-page="${page - 1}" ${page <= 1 ? "disabled" : ""}>‹ 上一页</button>
        ${pgs.join("")}
        <button class="page-btn" data-page="${page + 1}" ${page >= total_pages ? "disabled" : ""}>下一页 ›</button>
      </div>
    `;
  },

  _inlineEdit(cell, container) {
    if (cell.querySelector("input")) return;
    const id = parseInt(cell.dataset.id);
    const current = cell.textContent.trim();
    cell.innerHTML = `<input class="inline-input" value="${current}" />`;
    const input = cell.querySelector("input");
    input.focus();
    input.select();

    const commit = async () => {
      const val = input.value.trim();
      try {
        await API.transactions.update(id, { category: val });
        cell.textContent = val || "—";
        cell.classList.add("editable");
        cell.addEventListener("click", () => Transactions._inlineEdit(cell, container));
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
