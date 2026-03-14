/* ===== Classification rules page ===== */
const RulesPage = {
  _editingId: null,

  render(container) {
    container.innerHTML = `
      <div class="page-header">
        <h1 class="page-title">分类规则</h1>
        <button class="btn btn-ghost" id="rules-reset">新建规则</button>
      </div>

      <div class="rules-layout">
        <div class="card">
          <div class="card-title">规则说明</div>
          <div class="rules-tips">
            <p>按优先级从小到大匹配，命中第一条后就停止。</p>
            <p>可以设置“美团 -> 餐饮”“滴滴 -> 交通”“星巴克 + 微信支付 -> 咖啡”这类自动归类规则。</p>
            <p>当前版本会在交易还没有分类或备注时自动补上规则里的结果。</p>
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
              <span class="form-label">自动分类 *</span>
              <input type="text" id="rule-category" placeholder="如：餐饮美食">
            </label>
            <label class="form-field rules-form-span2">
              <span class="form-label">自动备注</span>
              <input type="text" id="rule-remark" placeholder="命中后自动补上的备注">
            </label>
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
        <div class="card-title">当前规则</div>
        <div id="rules-list"><div class="loading">加载中...</div></div>
      </div>
    `;

    container.querySelector("#rules-reset").addEventListener("click", () => RulesPage._resetForm(container));
    container.querySelector("#rule-cancel").addEventListener("click", () => RulesPage._resetForm(container));
    container.querySelector("#rule-form").addEventListener("submit", (e) => RulesPage._submit(container, e));

    RulesPage._resetForm(container);
    RulesPage._load(container);
  },

  _collectForm(container) {
    return {
      name: container.querySelector("#rule-name").value.trim(),
      priority: Number(container.querySelector("#rule-priority").value || 100),
      is_active: container.querySelector("#rule-active").checked,
      match_counterparty: container.querySelector("#rule-match-counterparty").value.trim(),
      match_product: container.querySelector("#rule-match-product").value.trim(),
      match_payment_method: container.querySelector("#rule-match-payment").value.trim(),
      match_transaction_type: container.querySelector("#rule-match-type").value.trim(),
      category: container.querySelector("#rule-category").value.trim(),
      remark: container.querySelector("#rule-remark").value.trim(),
    };
  },

  _fillForm(container, rule) {
    RulesPage._editingId = rule ? rule.id : null;
    container.querySelector("#rule-form-title").textContent = rule ? "编辑规则" : "新建规则";
    container.querySelector("#rule-submit").textContent = rule ? "保存修改" : "保存规则";
    container.querySelector("#rule-name").value = rule?.name || "";
    container.querySelector("#rule-priority").value = rule?.priority ?? 100;
    container.querySelector("#rule-match-counterparty").value = rule?.match_counterparty || "";
    container.querySelector("#rule-match-product").value = rule?.match_product || "";
    container.querySelector("#rule-match-payment").value = rule?.match_payment_method || "";
    container.querySelector("#rule-match-type").value = rule?.match_transaction_type || "";
    container.querySelector("#rule-category").value = rule?.category || "";
    container.querySelector("#rule-remark").value = rule?.remark || "";
    container.querySelector("#rule-active").checked = rule ? !!rule.is_active : true;
    container.querySelector("#rule-form-error").textContent = "";
  },

  _resetForm(container) {
    RulesPage._fillForm(container, null);
  },

  async _submit(container, event) {
    event.preventDefault();
    const errorEl = container.querySelector("#rule-form-error");
    errorEl.textContent = "";
    const payload = RulesPage._collectForm(container);

    try {
      if (RulesPage._editingId) {
        await API.rules.update(RulesPage._editingId, payload);
      } else {
        await API.rules.create(payload);
      }
      RulesPage._resetForm(container);
      RulesPage._load(container);
    } catch (err) {
      errorEl.textContent = err.message;
    }
  },

  async _load(container) {
    const listEl = container.querySelector("#rules-list");
    try {
      const rules = await API.rules.list();
      if (!rules.length) {
        listEl.innerHTML = `<div class="empty">还没有分类规则，先创建一条试试看。</div>`;
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
            <div><span>自动分类</span><strong>${rule.category || "—"}</strong></div>
            <div><span>自动备注</span><strong>${rule.remark || "—"}</strong></div>
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
            await API.rules.delete(id);
            if (RulesPage._editingId === id) RulesPage._resetForm(container);
            RulesPage._load(container);
          } catch (err) {
            alert("删除失败: " + err.message);
          }
        });
      });
    } catch (err) {
      listEl.innerHTML = `<div class="empty" style="color:var(--expense)">加载失败：${err.message}</div>`;
    }
  },
};
