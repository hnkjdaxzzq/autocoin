/* ===== AiClassification page - AI自动分类 ===== */
const AiClassification = {
  _state: {
    previewPage: 1,
    previewPageSize: 50,
    allResults: [],
    filteredResults: [],
    completeData: null,
    latestFailedDetails: [],
    latestTotalBatches: 0,
    promptExpanded: true,
    dateRangeExpanded: false,
    defaultPromptTemplate: "",
    defaultCategories: "餐饮美食，交通出行，汽车，母婴儿童，娱乐，购物，生活缴费，社保费用，医疗，旅游，其他",
  },

  render(container) {
    AiClassification._state.promptExpanded = true;
    AiClassification._state.dateRangeExpanded = false;
    container.innerHTML = `
      <div class="page-header">
        <h1 class="page-title">AI分析</h1>
      </div>

      <div class="card" style="max-width:640px;margin-bottom:24px">
        <div class="card-title">AI 自动分类（实验性功能）</div>

        <div style="margin-bottom:16px">
          <label style="display:block;font-weight:600;margin-bottom:6px;font-size:14px">
            使用AI将数据做以下分类
          </label>
          <input type="text" id="ai-categories" class="ai-input"
            value="${AiClassification._state.defaultCategories}"
            placeholder="${AiClassification._state.defaultCategories}"
            style="width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:var(--radius-sm);
                   font-size:14px;background:var(--input-bg);color:var(--text)">
          <div style="margin-top:4px;font-size:12px;color:var(--text-muted)">
            请填写希望将数据分类的[全部]类型，不同分类之间用英文或中文逗号隔开，AI将把所有数据识别为以上分类，不保留你没有填写的类型。
          </div>
          <div style="margin-top:12px">
            <button id="ai-date-range-toggle" type="button" aria-expanded="false"
              style="display:flex;align-items:center;gap:6px;width:100%;padding:0;
                     border:0;background:transparent;color:var(--text);font-weight:600;font-size:14px;cursor:pointer">
              <span>选择时间范围</span>
              <span id="ai-date-range-toggle-icon" style="font-size:16px;color:var(--text-muted)">▸</span>
            </button>
            <div id="ai-date-range-panel" style="display:none;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px">
              <label style="display:flex;flex-direction:column;gap:5px;font-size:12px;color:var(--text-muted)">
                <span>开始日期</span>
                <input type="date" id="ai-start-date"
                  style="width:100%;padding:9px 10px;border:1px solid var(--border);border-radius:var(--radius-sm);
                         font-size:13px;background:var(--input-bg);color:var(--text)">
              </label>
              <label style="display:flex;flex-direction:column;gap:5px;font-size:12px;color:var(--text-muted)">
                <span>结束日期</span>
                <input type="date" id="ai-end-date"
                  style="width:100%;padding:9px 10px;border:1px solid var(--border);border-radius:var(--radius-sm);
                         font-size:13px;background:var(--input-bg);color:var(--text)">
              </label>
            </div>
          </div>
        </div>

        <label style="display:flex;align-items:center;gap:8px;margin-bottom:14px;font-size:14px;color:var(--text);cursor:pointer">
          <input type="checkbox" id="ai-only-expense" checked
            style="width:16px;height:16px;accent-color:var(--primary)">
          <span>仅分类支出数据</span>
        </label>

        <button id="btn-ai-classify" class="btn btn-primary" style="width:100%;padding:10px;font-size:15px;font-weight:600">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
               style="width:16px;height:16px;vertical-align:middle;margin-right:6px">
            <path d="M12 2a4 4 0 014 4c0 2-2 4-4 6-2-2-4-4-4-6a4 4 0 014-4z"/>
            <path d="M5 22a7 7 0 0114 0"/>
          </svg>
          AI自动分类
        </button>

        <div style="margin-top:16px">
          <label style="display:block;font-weight:600;margin-bottom:6px;font-size:14px">
            API key
          </label>
          <input type="text" id="ai-api-key" class="ai-input"
            placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            style="width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:var(--radius-sm);
                   font-size:14px;background:var(--input-bg);color:var(--text);
                   font-family:monospace">
          <div style="margin-top:4px;font-size:12px;color:var(--text-muted)">
            请填写Deepseek官方网站里的API key
          </div>
        </div>

        <div style="margin-top:16px;border-top:1px solid var(--border);padding-top:12px">
          <button id="ai-prompt-toggle" type="button" aria-expanded="true"
            style="display:flex;align-items:center;gap:6px;width:100%;padding:0;
                   border:0;background:transparent;color:var(--text);font-weight:600;font-size:14px;cursor:pointer">
            <span>AI Prompt</span>
            <span id="ai-prompt-toggle-icon" style="font-size:16px;color:var(--text-muted)">▾</span>
          </button>
          <div id="ai-prompt-panel" style="display:block;margin-top:10px">
            <textarea id="ai-prompt-template" class="ai-input" rows="16"
              style="width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:var(--radius-sm);
                     font-size:13px;background:var(--input-bg);color:var(--text);
                     font-family:monospace;line-height:1.5;resize:vertical"></textarea>
            <div style="margin-top:4px;font-size:12px;color:var(--text-muted)">
              可使用 {category_map} 表示分类编号，{transactions} 表示本批交易数据。
            </div>
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:8px">
              <button id="btn-reset-ai-prompt" type="button" class="btn btn-ghost"
                style="padding:8px 10px;font-size:13px">
                重置为默认Prompt
              </button>
              <label style="display:flex;align-items:center;gap:8px;margin-left:auto;font-size:12px;color:var(--text-muted)">
                <span style="white-space:nowrap">本次最多处理</span>
                <input type="text" id="ai-limit" inputmode="numeric" value="无限制"
                  style="width:120px;padding:8px 10px;border:1px solid var(--border);border-radius:var(--radius-sm);
                         font-size:13px;background:var(--input-bg);color:var(--text);text-align:right">
              </label>
              <label style="display:flex;align-items:center;gap:6px;font-size:12px;color:var(--text-muted);cursor:pointer">
                <input type="checkbox" id="ai-debug-mode"
                  style="width:14px;height:14px;accent-color:var(--primary)">
                <span>调试模式</span>
              </label>
            </div>
          </div>
        </div>
      </div>

      <div id="ai-status"></div>
      <div id="ai-results"></div>
    `;

    AiClassification._bindEvents(container);
    AiClassification._loadPreferences(container);
  },

  _bindEvents(container) {
    const btn = container.querySelector("#btn-ai-classify");
    btn.addEventListener("click", () => AiClassification._startClassification(container));
    container.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-ai-debug-download]");
      if (!btn) return;
      e.preventDefault();
      AiClassification._downloadDebugLog(btn.dataset.aiDebugDownload || "");
    });

    // Enter key to trigger
    container.querySelector("#ai-categories").addEventListener("keydown", (e) => {
      if (e.key === "Enter") btn.click();
    });
    container.querySelector("#ai-api-key").addEventListener("keydown", (e) => {
      if (e.key === "Enter") btn.click();
    });

    container.querySelector("#ai-date-range-toggle").addEventListener("click", () => {
      AiClassification._setDateRangeExpanded(
        container,
        !AiClassification._state.dateRangeExpanded,
      );
    });

    container.querySelector("#ai-prompt-toggle").addEventListener("click", () => {
      AiClassification._setPromptExpanded(
        container,
        !AiClassification._state.promptExpanded,
      );
    });

    container.querySelector("#btn-reset-ai-prompt").addEventListener("click", () => {
      const promptEl = container.querySelector("#ai-prompt-template");
      if (promptEl) {
        promptEl.value = AiClassification._state.defaultPromptTemplate || "";
        AiClassification._showToast("已重置为默认 Prompt");
      }
    });

    const limitEl = container.querySelector("#ai-limit");
    limitEl.addEventListener("focus", () => {
      if (limitEl.value.trim() === "无限制") limitEl.value = "";
    });
    limitEl.addEventListener("blur", () => {
      const value = parseInt(limitEl.value, 10) || 0;
      limitEl.value = value > 0 ? String(value) : "无限制";
    });
  },

  async _loadPreferences(container) {
    try {
      const prefs = await API.aiClassification.getPreferences();
      const categoriesEl = container.querySelector("#ai-categories");
      const apiKeyEl = container.querySelector("#ai-api-key");
      const promptEl = container.querySelector("#ai-prompt-template");
      const onlyExpenseEl = container.querySelector("#ai-only-expense");
      AiClassification._state.defaultPromptTemplate = prefs.default_prompt_template || "";
      if (categoriesEl) categoriesEl.value = prefs.categories || AiClassification._state.defaultCategories;
      if (apiKeyEl) apiKeyEl.value = prefs.api_key || "";
      if (promptEl) promptEl.value = prefs.prompt_template || "";
      if (onlyExpenseEl) onlyExpenseEl.checked = prefs.only_expense !== false;
    } catch (err) {
      AiClassification._showToast("读取 AI 配置失败: " + err.message);
    }
  },

  _setPromptExpanded(container, expanded) {
    AiClassification._state.promptExpanded = expanded;
    const panel = container.querySelector("#ai-prompt-panel");
    const toggle = container.querySelector("#ai-prompt-toggle");
    const icon = container.querySelector("#ai-prompt-toggle-icon");
    if (panel) panel.style.display = expanded ? "block" : "none";
    if (toggle) toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
    if (icon) icon.textContent = expanded ? "▾" : "▸";
  },

  _setDateRangeExpanded(container, expanded) {
    AiClassification._state.dateRangeExpanded = expanded;
    const panel = container.querySelector("#ai-date-range-panel");
    const toggle = container.querySelector("#ai-date-range-toggle");
    const icon = container.querySelector("#ai-date-range-toggle-icon");
    if (panel) panel.style.display = expanded ? "grid" : "none";
    if (toggle) toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
    if (icon) icon.textContent = expanded ? "▾" : "▸";
  },

  async _startClassification(container) {
    const categories = container.querySelector("#ai-categories").value.trim();
    const apiKey = container.querySelector("#ai-api-key").value.trim();
    const promptTemplate = container.querySelector("#ai-prompt-template").value.trim();
    const onlyExpense = container.querySelector("#ai-only-expense").checked;
    const limit = Math.max(0, parseInt(container.querySelector("#ai-limit").value, 10) || 0);
    const debug = container.querySelector("#ai-debug-mode").checked;
    const startDate = container.querySelector("#ai-start-date").value;
    const endDate = container.querySelector("#ai-end-date").value;

    if (!categories) {
      AiClassification._showToast("请填写分类");
      return;
    }
    if (!apiKey) {
      AiClassification._showToast("请填写 API key");
      return;
    }

    const btn = container.querySelector("#btn-ai-classify");
    const statusEl = container.querySelector("#ai-status");
    AiClassification._state.completeData = null;
    AiClassification._state.latestFailedDetails = [];
    AiClassification._state.latestTotalBatches = 0;

    btn.disabled = true;
    btn.textContent = "分类中...";

    // Show progress UI
    statusEl.innerHTML = `
      <div class="card" style="margin-top:16px">
        <div class="card-title">分类进度</div>
        <div id="ai-progress-status" style="font-size:14px;margin-bottom:12px;font-weight:500">
          ⏳ 正在启动...
        </div>
        <div class="progress-track" id="ai-progress-track">
          <div class="progress-fill" id="ai-progress-fill" style="width:0%"></div>
        </div>
        <div id="ai-progress-detail" style="font-size:12px;color:var(--text-muted);margin-top:8px">
          准备中...
        </div>
        <div id="ai-failure-details" style="display:none;margin-top:10px;padding:10px;
             border:1px solid rgba(239,68,68,.28);border-radius:var(--radius-sm);
             background:rgba(239,68,68,.06);color:var(--expense);font-size:12px;line-height:1.5">
        </div>
      </div>`;

    const progressStatus = document.getElementById("ai-progress-status");
    const progressFill = document.getElementById("ai-progress-fill");
    const progressDetail = document.getElementById("ai-progress-detail");
    const failureDetailsEl = document.getElementById("ai-failure-details");

    const updateProgress = (phase, message, pct) => {
      if (progressStatus) progressStatus.textContent = message;
      if (progressFill) progressFill.style.width = Math.min(pct, 100) + "%";
    };

    // Use fetch directly for SSE streaming
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 660000);

    try {
      const token = Auth.getToken();
      const response = await fetch("/api/v1/ai-classification/classify", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify({
          api_key: apiKey,
          categories: categories,
          prompt_template: promptTemplate,
          only_expense: onlyExpense,
          limit: limit,
          debug: debug,
          start_date: startDate || null,
          end_date: endDate || null,
        }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        let msg = `HTTP ${response.status}`;
        try { const j = await response.json(); msg = j.detail || msg; } catch (_) {}
        throw new Error(msg);
      }

      // Read SSE stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let completeData = null;
      let latestFailedDetails = [];
      let latestTotalBatches = 0;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse SSE events from buffer
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";  // keep incomplete chunk

        for (const rawEvent of events) {
          if (!rawEvent.trim()) continue;

          const lines = rawEvent.split("\n");
          let eventType = "";
          let dataStr = "";

          for (const line of lines) {
            if (line.startsWith("event: ")) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              dataStr = line.slice(6);
            }
          }

          if (!dataStr) continue;

          try {
            const data = JSON.parse(dataStr);

            if (eventType === "progress") {
              const phase = data.phase;
              let pct = 0;
              let msg = "";

              if (phase === "reading") {
                pct = 5;
                msg = "⏳ 正在读取数据库中的交易数据...";
              } else if (phase === "preparing") {
                pct = 10;
                msg = `📦 共 ${data.total} 条数据，分为 ${data.total_batches} 批处理`;
              } else if (phase === "classifying") {
                const done = data.completed_batches || 0;
                const totalB = data.total_batches || 1;
                pct = 10 + Math.round((done / totalB) * 80);
                const classified = data.classified_so_far || 0;
                const total = data.total || 0;
                msg = `🤖 正在分类... ${done}/${totalB} 批，已处理 ${classified}/${total} 条`;
                if (data.failed_batches > 0) {
                  msg += ` (${data.failed_batches} 批失败，已保留原分类)`;
                }
              } else if (phase === "timeout") {
                pct = 95;
                msg = `⏰ 处理超时，已部分完成 ${data.classified_so_far || 0}/${data.total} 条`;
              }

              updateProgress(phase, msg, pct);
              if (progressDetail) progressDetail.textContent = msg.replace(/^[^\s]+\s/, "");
              latestFailedDetails = data.failed_details || latestFailedDetails;
              latestTotalBatches = data.total_batches || latestTotalBatches;
              AiClassification._state.latestFailedDetails = latestFailedDetails;
              AiClassification._state.latestTotalBatches = latestTotalBatches;
              AiClassification._renderFailureDetails(failureDetailsEl, data.failed_details, data.total_batches);

            } else if (eventType === "complete") {
              completeData = data;
              // Fill the bar
              updateProgress("complete", "✅ 分类完成", 100);
              if (progressDetail) progressDetail.textContent = `共处理 ${data.classified} 条，${data.changed} 条分类发生变更`;
              latestFailedDetails = data.failed_details || latestFailedDetails;
              latestTotalBatches = data.total_batches || latestTotalBatches;
              AiClassification._state.latestFailedDetails = latestFailedDetails;
              AiClassification._state.latestTotalBatches = latestTotalBatches;
              AiClassification._renderFailureDetails(failureDetailsEl, data.failed_details, data.total_batches);
            }
          } catch (e) {
            // ignore parse errors for incomplete chunks
          }
        }
      }

      if (!completeData || !completeData.results || completeData.results.length === 0) {
        statusEl.innerHTML = `<div class="empty">没有需要分类的数据</div>`;
        return;
      }

      // Store results
      AiClassification._state.allResults = completeData.results;
      AiClassification._state.completeData = completeData;

      // Update status to summary
      const finalFailureDetails = AiClassification._failureDetailsHtml(
        completeData.failed_details,
        completeData.total_batches,
      );
      statusEl.innerHTML = `
        <div class="summary-grid" style="margin-top:16px">
          <div class="summary-card">
            <div class="label">总数据</div>
            <div class="value" style="color:var(--primary);font-size:22px">${completeData.total}</div>
          </div>
          <div class="summary-card">
            <div class="label">已分类</div>
            <div class="value" style="color:var(--income);font-size:22px">${completeData.classified}</div>
          </div>
          <div class="summary-card">
            <div class="label">分类改变</div>
            <div class="value" style="color:var(--expense);font-size:22px">${completeData.changed}</div>
          </div>
        </div>
        ${completeData.failed_batches > 0 ? `
          <div style="margin-top:12px;padding:12px;border:1px solid rgba(239,68,68,.28);
                      border-radius:var(--radius-sm);background:rgba(239,68,68,.06);
                      color:var(--expense);font-size:13px;line-height:1.5">
            <strong>${completeData.failed_batches} 批处理失败，失败批次已保留原分类。</strong>
            ${finalFailureDetails}
          </div>
        ` : ""}
      `;

      AiClassification._showResultModal(container);
    } catch (err) {
      clearTimeout(timeoutId);
      const isTimeout = err.name === "AbortError";
      statusEl.innerHTML = `
        <div style="padding:16px;background:rgba(239,68,68,.08);border-radius:var(--radius-sm);
                    color:var(--expense);font-weight:500">
          ❌ ${isTimeout ? "请求超时：DeepSeek API 响应超过11分钟，请检查网络或 API key 是否正确" : "分类失败: " + err.message}
        </div>`;
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
               style="width:16px;height:16px;vertical-align:middle;margin-right:6px">
            <path d="M12 2a4 4 0 014 4c0 2-2 4-4 6-2-2-4-4-4-6a4 4 0 014-4z"/>
            <path d="M5 22a7 7 0 0114 0"/>
          </svg>
          AI自动分类`;
    }
  },

  _showResultModal(container) {
    AiClassification._removeModal();

    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";

    const allResults = AiClassification._state.allResults;
    const completeData = AiClassification._state.completeData || {};
    const pageSize = AiClassification._state.previewPageSize;
    let currentPage = 1;

    const renderTable = (page) => {
      const results = allResults;
      const totalPages = Math.ceil(results.length / pageSize) || 1;
      const start = (page - 1) * pageSize;
      const end = Math.min(start + pageSize, results.length);
      const pageItems = results.slice(start, end);

      return `
        <div class="modal-table-wrap">
          <table class="modal-table">
            <thead>
              <tr>
                <th style="width:50px">#</th>
                <th style="width:140px">交易时间</th>
                <th>交易对方</th>
                <th>商品</th>
                <th style="width:100px">旧分类</th>
                <th style="width:100px">新分类</th>
              </tr>
            </thead>
            <tbody>
              ${pageItems.map((item, i) => `
                <tr>
                  <td style="color:var(--text-muted)">${start + i + 1}</td>
                  <td>${AiClassification._fmtDate(item.transaction_time)}</td>
                  <td style="max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
                      title="${item.counterparty || ""}">${item.counterparty || "—"}</td>
                  <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
                      title="${item.product || ""}">${item.product || "—"}</td>
                  <td><span class="badge badge-old">${item.old_category || "—"}</span></td>
                  <td><span class="badge badge-new">${item.new_category || "—"}</span></td>
                </tr>
              `).join("")}
              ${pageItems.length === 0 ? '<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:20px">没有数据</td></tr>' : ""}
            </tbody>
          </table>
        </div>
        <div class="pagination" style="margin-top:8px">
          <span class="info">共 ${results.length} 条</span>
          <button class="page-btn" data-page="${page - 1}" ${page <= 1 ? "disabled" : ""}>‹ 上一页</button>
          <span style="font-size:13px;color:var(--text-muted);padding:0 8px">第${page}/${totalPages}页</span>
          <button class="page-btn" data-page="${page + 1}" ${page >= totalPages ? "disabled" : ""}>下一页 ›</button>
        </div>
      `;
    };

    const goToPage = (page) => {
      const totalPages = Math.ceil(allResults.length / pageSize) || 1;
      if (page < 1 || page > totalPages) return;
      currentPage = page;
      const body = overlay.querySelector(".modal-body-content");
      if (body) {
        body.innerHTML = renderTable(currentPage);
        AiClassification._bindModalPagination(overlay, goToPage);
      }
    };

    overlay.innerHTML = `
      <div class="modal-dialog modal-dialog-lg" style="max-width:960px;width:90vw">
        <div class="modal-title">AI分类结果预览</div>
        <div class="modal-body">
          ${completeData.failed_batches > 0 ? `
            <div style="margin-bottom:12px;padding:12px;border:1px solid rgba(239,68,68,.28);
                        border-radius:var(--radius-sm);background:rgba(239,68,68,.06);
                        color:var(--expense);font-size:13px;line-height:1.5">
              <strong>${completeData.failed_batches} 批处理失败，失败批次已保留原分类。</strong>
              ${AiClassification._failureDetailsHtml(completeData.failed_details, completeData.total_batches)}
            </div>
          ` : ""}
          <div style="margin-bottom:12px;font-size:13px;color:var(--text-muted)">
            共 <strong style="color:var(--text)">${allResults.length}</strong> 条数据，
            其中 <strong style="color:var(--expense)">${allResults.filter(r => r.old_category !== r.new_category).length}</strong> 条分类发生变更。
            每页展示 ${pageSize} 条。
          </div>
          <div class="modal-body-content">
            ${renderTable(1)}
          </div>
        </div>
        <div class="modal-buttons">
          <button class="btn btn-primary" id="modal-confirm-ai">确认修改</button>
          <button class="btn btn-ghost" id="modal-cancel-ai">取消</button>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);
    AiClassification._bindModalPagination(overlay, goToPage);

    overlay.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-ai-debug-download]");
      if (!btn) return;
      e.preventDefault();
      AiClassification._downloadDebugLog(btn.dataset.aiDebugDownload || "");
    });

    overlay.querySelector("#modal-confirm-ai").addEventListener("click", async () => {
      await AiClassification._confirmChanges(container, overlay);
    });

    overlay.querySelector("#modal-cancel-ai").addEventListener("click", () => {
      AiClassification._removeModal();
    });
  },

  _bindModalPagination(overlay, goToPage) {
    overlay.querySelectorAll(".page-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const p = parseInt(e.currentTarget.dataset.page);
        if (p && p > 0) {
          goToPage(p);
        }
      });
    });
  },

  async _confirmChanges(container, overlay) {
    const btn = overlay.querySelector("#modal-confirm-ai");
    btn.disabled = true;
    btn.textContent = "提交中...";

    try {
      // Only write records where category actually changed
      const changedResults = AiClassification._state.allResults.filter(
        r => r.old_category !== r.new_category
      );
      const payload = changedResults.map(r => ({
        id: r.id,
        category: r.new_category,
      }));

      const res = await API.aiClassification.confirm({ results: payload });

      AiClassification._removeModal();
      AiClassification._showToast(`✅ 已更新 ${res.updated} / ${res.total} 条记录`);

      // Update status
      const statusEl = container.querySelector("#ai-status");
      if (statusEl) {
        statusEl.innerHTML = `
          <div style="padding:16px;background:rgba(16,185,129,.08);border-radius:var(--radius-sm);
                      color:var(--income);font-weight:500">
            ✅ 已成功更新 ${res.updated} 条数据
          </div>`;
      }
    } catch (err) {
      AiClassification._showToast("❌ 更新失败: " + err.message);
      btn.disabled = false;
      btn.textContent = "确认修改";
    }
  },

  _removeModal() {
    const existing = document.querySelector(".modal-overlay");
    if (existing) existing.remove();
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

  _renderFailureDetails(container, details, totalBatches) {
    if (!container || !Array.isArray(details) || details.length === 0) return;
    container.style.display = "block";
    container.innerHTML = AiClassification._failureDetailsHtml(details, totalBatches);
  },

  _failureDetailsHtml(details, totalBatches) {
    if (!Array.isArray(details) || details.length === 0) return "";
    const recent = details.slice(-5);
    const rows = recent.map((item) => {
      const batch = item.batch || "?";
      const totalB = item.total_batches || totalBatches || "?";
      const count = item.count || 0;
      const splitDepth = item.split_depth || 0;
      const splitText = splitDepth > 0 ? `，已自动拆批 ${splitDepth} 层` : "";
      const reason = AiClassification._escapeHtml(item.reason || "未知错误");
      const prompt = item.prompt_preview ? `
        <details style="margin-top:4px">
          <summary style="cursor:pointer">本批 Prompt</summary>
          <pre style="white-space:pre-wrap;overflow:auto;max-height:220px;margin:6px 0 0;padding:8px;
                      border-radius:var(--radius-sm);background:rgba(0,0,0,.06);color:var(--text)">${AiClassification._escapeHtml(item.prompt_preview)}</pre>
        </details>` : "";
      const requestDebug = item.request_debug_preview ? `
        <details style="margin-top:4px">
          <summary style="cursor:pointer">DeepSeek 请求内容</summary>
          <pre style="white-space:pre-wrap;overflow:auto;max-height:260px;margin:6px 0 0;padding:8px;
                      border-radius:var(--radius-sm);background:rgba(0,0,0,.06);color:var(--text)">${AiClassification._escapeHtml(item.request_debug_preview)}</pre>
        </details>` : "";
      const raw = item.raw_response_preview ? `
        <details style="margin-top:4px">
          <summary style="cursor:pointer">DeepSeek 原始返回</summary>
          <pre style="white-space:pre-wrap;overflow:auto;max-height:220px;margin:6px 0 0;padding:8px;
                      border-radius:var(--radius-sm);background:rgba(0,0,0,.06);color:var(--text)">${AiClassification._escapeHtml(item.raw_response_preview)}</pre>
        </details>` : "";
      const responseDebug = item.response_debug_preview ? `
        <details style="margin-top:4px">
          <summary style="cursor:pointer">DeepSeek 响应元信息</summary>
          <pre style="white-space:pre-wrap;overflow:auto;max-height:220px;margin:6px 0 0;padding:8px;
                      border-radius:var(--radius-sm);background:rgba(0,0,0,.06);color:var(--text)">${AiClassification._escapeHtml(item.response_debug_preview)}</pre>
        </details>` : "";
      return `<div style="margin-top:4px">第 ${batch}/${totalB} 批（${count} 条${splitText}）：${reason}${prompt}${requestDebug}${raw}${responseDebug}</div>`;
    }).join("");
    return `
      <div style="margin-top:6px">
        <div style="display:flex;align-items:center;gap:8px;justify-content:space-between;flex-wrap:wrap">
          <strong>失败详情（最近 ${recent.length} 条）</strong>
          <button type="button" class="btn btn-ghost" data-ai-debug-download="latest"
            style="padding:5px 8px;font-size:12px;color:var(--text)">
            下载调试日志
          </button>
        </div>
        ${rows}
      </div>`;
  },

  _downloadDebugLog(source) {
    const data = AiClassification._state.completeData || {};
    const details = (
      Array.isArray(data.failed_details) && data.failed_details.length > 0
        ? data.failed_details
        : AiClassification._state.latestFailedDetails
    ) || [];
    const totalBatches = data.total_batches || AiClassification._state.latestTotalBatches || "";
    if (!Array.isArray(details) || details.length === 0) {
      AiClassification._showToast("暂无可下载的调试日志");
      return;
    }

    const content = AiClassification._buildDebugLogText(details, totalBatches, source);
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    a.href = url;
    a.download = `ai-classification-debug-${stamp}.txt`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },

  _buildDebugLogText(details, totalBatches, source) {
    const lines = [
      "AI 分类调试日志",
      `生成时间: ${new Date().toISOString()}`,
      `来源: ${source || "latest"}`,
      `失败批次数: ${details.length}`,
      `总批次数: ${totalBatches || "未知"}`,
      "",
    ];

    details.forEach((item, idx) => {
      lines.push(`===== 失败 ${idx + 1}/${details.length} =====`);
      lines.push(`批次: ${item.batch || "?"}/${item.total_batches || totalBatches || "?"}`);
      lines.push(`条数: ${item.count || 0}`);
      lines.push(`自动拆批层数: ${item.split_depth || 0}`);
      lines.push(`原因: ${item.reason || "未知错误"}`);
      lines.push("");
      lines.push("----- 本批 Prompt -----");
      lines.push(item.prompt_preview || "<empty>");
      lines.push("");
      lines.push("----- DeepSeek 请求内容 -----");
      lines.push(item.request_debug_preview || "<empty>");
      lines.push("");
      lines.push("----- DeepSeek 原始返回 -----");
      lines.push(item.raw_response_preview || "<empty>");
      lines.push("");
      lines.push("----- DeepSeek 响应元信息 -----");
      lines.push(item.response_debug_preview || "<empty>");
      lines.push("");
    });

    return lines.join("\n");
  },

  _escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  },

  _fmtDate(iso) {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return iso.substring(0, 10);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    } catch {
      return iso ? iso.substring(0, 10) : "—";
    }
  },
};
