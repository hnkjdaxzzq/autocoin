/* ===== Rules page ===== */
const RulesPage = {
  _editingId: null,
  _activeTab: "category",

  _tabs: {
    category: {
      label: "分类规则",
      title: "分类规则",
      resultLabel: "自动分类",
      resultField: "category",
      resultPlaceholder: "如：餐饮美食",
      actionText: "立即重新分类",
      confirmText: "是否对现有数据执行重新分类",
      errorText: "重新分类失败: ",
      emptyText: "还没有分类规则，先创建一条试试看。",
      listTitle: "当前规则",
      tipsAction: "规则会在导入数据及点击页面上方立即重新分类按钮时生效",
      api: API.rules,
      run: () => API.rules.reclassify(),
      resultColumns: [
        { header: "原分类", value: (b) => b.category || "" },
        { header: "新分类", value: (_, a) => a.category || "" },
        { header: "原备注", value: (b) => b.remark || "" },
        { header: "新备注", value: (_, a) => a.remark || "" },
      ],
    },
    alias: {
      label: "别名规则",
      title: "别名规则",
      resultLabel: "映射别名",
      resultField: "product_alias",
      resultPlaceholder: "如：AAPL",
      actionText: "立即修改映射别名",
      confirmText: "是否对现有数据执行修改映射别名",
      errorText: "修改映射别名失败: ",
      emptyText: "还没有别名规则，先创建一条试试看。",
      listTitle: "当前别名规则",
      tipsAction: "规则会在导入数据及点击页面上方立即修改映射别名按钮时生效",
      api: API.aliasRules,
      run: () => API.aliasRules.realias(),
      resultColumns: [
        { header: "原别名", value: (b) => b.product_alias || "" },
        { header: "新别名", value: (_, a) => a.product_alias || "" },
      ],
    },
  },

  render(container) {
    RulesPage._editingId = null;
    RulesPage._activeTab = RulesPage._activeTab || "category";
    RulesPage._render(container);
  },

  _current() {
    return RulesPage._tabs[RulesPage._activeTab];
  },

  _render(container) {
    const cfg = RulesPage._current();
    container.innerHTML = `
      <div class="page-header">
        <h1 class="page-title">${cfg.title}</h1>
        <button class="btn btn-ghost" id="rules-run">${cfg.actionText}</button>
        <button class="btn btn-ghost" id="rules-reset">新建规则</button>
      </div>

      <div class="rules-tabs" role="tablist">
        ${Object.entries(RulesPage._tabs).map(([key, tab]) => `
          <button class="rules-tab ${RulesPage._activeTab === key ? "active" : ""}" data-tab="${key}" role="tab">
            ${tab.label}
          </button>
        `).join("")}
      </div>

      <div class="rules-layout">
        <div class="card">
          <div class="card-title">规则说明</div>
          <div class="rules-tips">
            <p>按优先级从小到大匹配，命中第一条后就停止。</p>
            <p>规则内容支持正则</p>
            <p>${cfg.tipsAction}</p>
          </div>
        </div>

        <div class="card">
          <div class="card-title" id="rule-form-title">新建规则</div>
          <form id="rule-form" class="rules-form">
            <label class="form-field">
              <span class="form-label">规则名称 *</span>
              <input type="text" id="rule-name" placeholder="如：美团自动归类餐饮" required>
            </label>
            <label class="form-field">
              <span class="form-label">优先级</span>
              <input type="number" id="rule-priority" min="0" value="100">
            </label>
            <label class="form-field">
              <span class="form-label">交易对方包含</span>
              <input type="text" id="rule-match-counterparty" placeholder="如：美团">
            </label>
            <label class="form-field">
              <span class="form-label">商品说明包含</span>
              <input type="text" id="rule-match-product" placeholder="如：外卖">
            </label>
            <label class="form-field">
              <span class="form-label">支付方式包含</span>
              <input type="text" id="rule-match-payment" placeholder="如：微信支付">
            </label>
            <label class="form-field">
              <span class="form-label">原始交易类型包含</span>
              <input type="text" id="rule-match-type" placeholder="如：商户消费">
            </label>
            <label class="form-field">
              <span class="form-label">${cfg.resultLabel} *</span>
              <input type="text" id="rule-result" placeholder="${cfg.resultPlaceholder}">
            </label>
            ${RulesPage._activeTab === "category" ? `
              <label class="form-field rules-form-span2">
                <span class="form-label">自动备注</span>
                <input type="text" id="rule-remark" placeholder="命中后自动补上的备注">
              </label>
            ` : ""}
            <label class="form-field rules-form-span2">
              <span class="rules-checkbox">
                <input type="checkbox" id="rule-active" checked>
                <span>启用这条规则</span>
              </span>
            </label>
            <div class="rules-form-actions rules-form-span2">
              <button type="submit" class="btn btn-primary" id="rule-submit">保存规则</button>
              <button type="button" class="btn btn-ghost" id="rule-cancel">取消编辑</button>
            </div>
          </form>
          <div id="rule-form-error" class="rules-error"></div>
        </div>
      </div>

      <div class="card">
        <div class="card-title">${cfg.listTitle}</div>
        <div id="rules-list"><div class="loading">加载中...</div></div>
      </div>
    `;

    container.querySelectorAll(".rules-tab").forEach(btn => {
      btn.addEventListener("click", () => {
        RulesPage._activeTab = btn.dataset.tab;
        RulesPage._editingId = null;
        RulesPage._render(container);
      });
    });
    container.querySelector("#rules-reset").addEventListener("click", () => RulesPage._resetForm(container));
    container.querySelector("#rule-cancel").addEventListener("click", () => RulesPage._resetForm(container));
    container.querySelector("#rule-form").addEventListener("submit", (e) => RulesPage._submit(container, e));
    container.querySelector("#rules-run").addEventListener("click", () => RulesPage._runRules(container));

    RulesPage._resetForm(container);
    RulesPage._load(container);
  },

  _collectForm(container) {
    const cfg = RulesPage._current();
    const payload = {
      name: container.querySelector("#rule-name").value.trim(),
      priority: Number(container.querySelector("#rule-priority").value || 100),
      is_active: container.querySelector("#rule-active").checked,
      match_counterparty: container.querySelector("#rule-match-counterparty").value.trim(),
      match_product: container.querySelector("#rule-match-product").value.trim(),
      match_payment_method: container.querySelector("#rule-match-payment").value.trim(),
      match_transaction_type: container.querySelector("#rule-match-type").value.trim(),
    };
    payload[cfg.resultField] = container.querySelector("#rule-result").value.trim();
    if (RulesPage._activeTab === "category") {
      payload.remark = container.querySelector("#rule-remark").value.trim();
    }
    return payload;
  },

  _fillForm(container, rule) {
    const cfg = RulesPage._current();
    RulesPage._editingId = rule ? rule.id : null;
    container.querySelector("#rule-form-title").textContent = rule ? "编辑规则" : "新建规则";
    container.querySelector("#rule-submit").textContent = rule ? "保存修改" : "保存规则";
    container.querySelector("#rule-name").value = rule?.name || "";
    container.querySelector("#rule-priority").value = rule?.priority ?? 100;
    container.querySelector("#rule-match-counterparty").value = rule?.match_counterparty || "";
    container.querySelector("#rule-match-product").value = rule?.match_product || "";
    container.querySelector("#rule-match-payment").value = rule?.match_payment_method || "";
    container.querySelector("#rule-match-type").value = rule?.match_transaction_type || "";
    container.querySelector("#rule-result").value = rule?.[cfg.resultField] || "";
    const remarkEl = container.querySelector("#rule-remark");
    if (remarkEl) remarkEl.value = rule?.remark || "";
    container.querySelector("#rule-active").checked = rule ? !!rule.is_active : true;
    container.querySelector("#rule-form-error").textContent = "";
  },

  _resetForm(container) {
    RulesPage._fillForm(container, null);
  },

  async _submit(container, event) {
    event.preventDefault();
    const cfg = RulesPage._current();
    const errorEl = container.querySelector("#rule-form-error");
    errorEl.textContent = "";
    const payload = RulesPage._collectForm(container);

    try {
      if (RulesPage._editingId) {
        await cfg.api.update(RulesPage._editingId, payload);
      } else {
        await cfg.api.create(payload);
      }
      RulesPage._resetForm(container);
      RulesPage._load(container);
    } catch (err) {
      errorEl.textContent = err.message;
    }
  },

  async _load(container) {
    const cfg = RulesPage._current();
    const listEl = container.querySelector("#rules-list");
    try {
      const rules = await cfg.api.list();
      if (!rules.length) {
        listEl.innerHTML = `<div class="empty">${cfg.emptyText}</div>`;
        return;
      }

      listEl.innerHTML = rules.map(rule => `
        <div class="rule-item ${rule.is_active ? "" : "rule-item--inactive"}" data-id="${rule.id}">
          <div class="rule-item-head">
            <div>
              <div class="rule-item-title">${rule.name}</div>
              <div class="rule-item-meta">优先级 ${rule.priority} · ${rule.is_active ? "启用中" : "已停用"}</div>
            </div>
            <div class="rule-item-actions">
              <button class="btn btn-ghost btn-sm" data-action="edit">编辑</button>
              <button class="btn btn-ghost btn-sm" data-action="delete">删除</button>
            </div>
          </div>
          <div class="rule-item-grid">
            <div><span>匹配交易对方</span><strong>${rule.match_counterparty || "—"}</strong></div>
            <div><span>匹配商品说明</span><strong>${rule.match_product || "—"}</strong></div>
            <div><span>匹配支付方式</span><strong>${rule.match_payment_method || "—"}</strong></div>
            <div><span>匹配原始类型</span><strong>${rule.match_transaction_type || "—"}</strong></div>
            <div><span>${cfg.resultLabel}</span><strong>${rule[cfg.resultField] || "—"}</strong></div>
            ${RulesPage._activeTab === "category" ? `<div><span>自动备注</span><strong>${rule.remark || "—"}</strong></div>` : ""}
          </div>
        </div>
      `).join("");

      listEl.querySelectorAll(".rule-item").forEach(el => {
        const id = Number(el.dataset.id);
        const rule = rules.find(item => item.id === id);
        el.querySelector('[data-action="edit"]').addEventListener("click", () => RulesPage._fillForm(container, rule));
        el.querySelector('[data-action="delete"]').addEventListener("click", async () => {
          if (!confirm(`确定删除规则「${rule.name}」吗？`)) return;
          try {
            await cfg.api.delete(id);
            if (RulesPage._editingId === id) RulesPage._resetForm(container);
            RulesPage._load(container);
          } catch (err) {
            alert("删除失败: " + err.message);
          }
        });
      });
    } catch (err) {
      listEl.innerHTML = `<div class="empty" style="color:var(--danger)">加载失败：${err.message}</div>`;
    }
  },

  _runRules(container) {
    const cfg = RulesPage._current();
    RulesPage._showConfirm(cfg.confirmText).then((confirmed) => {
      if (!confirmed) return;
      cfg.run().then((result) => {
        RulesPage._showResult(result);
      }).catch((err) => {
        alert(cfg.errorText + err.message);
      });
    });
  },

  _showConfirm(message) {
    return new Promise((resolve) => {
      const existing = document.querySelector(".modal-overlay");
      if (existing) existing.remove();
      const overlay = document.createElement("div");
      overlay.className = "modal-overlay";
      overlay.innerHTML = `
        <div class="modal-dialog modal-dialog-sm">
          <div class="modal-body">${message}</div>
          <div class="modal-buttons">
            <button class="btn btn-primary" id="modal-yes">是</button>
            <button class="btn btn-ghost" id="modal-cancel">取消</button>
          </div>
        </div>
      `;
      document.body.appendChild(overlay);
      overlay.querySelector("#modal-yes").addEventListener("click", () => {
        resolve(true);
        overlay.remove();
      });
      overlay.querySelector("#modal-cancel").addEventListener("click", () => {
        resolve(false);
        overlay.remove();
      });
    });
  },

  _showResult(data) {
    const cfg = RulesPage._current();
    const { modified_count, changes } = data;
    const existing = document.querySelector(".modal-overlay");
    if (existing) existing.remove();
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    let rowsHtml = "";
    if (changes && changes.length > 0) {
      rowsHtml = changes.map(change => {
        const b = change.before || {};
        const a = change.after || {};
        const dynamicCells = cfg.resultColumns.map(col => `<td>${col.value(b, a)}</td>`).join("");
        return `
          <tr>
            <td>${b.transaction_time || ""}</td>
            <td>${b.counterparty || ""}</td>
            <td>${b.product || ""}</td>
            <td>${(b.amount != null ? b.amount : "")}</td>
            ${dynamicCells}
          </tr>
        `;
      }).join("");
    } else {
      rowsHtml = `<tr><td colspan="${4 + cfg.resultColumns.length}">没有数据被修改</td></tr>`;
    }
    overlay.innerHTML = `
      <div class="modal-dialog modal-dialog-lg">
        <div class="modal-title">已修改${modified_count}条数据</div>
        <div class="modal-table-wrap">
          <table class="modal-table">
            <thead>
              <tr>
                <th>交易时间</th>
                <th>交易对方</th>
                <th>商品</th>
                <th>金额</th>
                ${cfg.resultColumns.map(col => `<th>${col.header}</th>`).join("")}
              </tr>
            </thead>
            <tbody>
              ${rowsHtml}
            </tbody>
          </table>
        </div>
        <div class="modal-buttons">
          <button class="btn btn-primary" id="modal-close">关闭</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
    overlay.querySelector("#modal-close").addEventListener("click", () => {
      overlay.remove();
    });
  },
};
