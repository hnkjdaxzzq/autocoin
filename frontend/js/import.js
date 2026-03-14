/* ===== Import page ===== */
const Import = {
  _recognizedTransactions: [],  // holds preview data for image imports
  _categories: [],
  _filePreview: null,
  _fileSelectedIdxs: new Set(),

  render(container) {
    container.innerHTML = `
      <div class="page-header">
        <h1 class="page-title">导入账单</h1>
      </div>

      <!-- Tab switcher -->
      <div class="import-tabs">
        <button class="import-tab active" data-tab="file">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="width:15px;height:15px"><path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>
          文件导入
        </button>
        <button class="import-tab" data-tab="image">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="width:15px;height:15px"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
          图片导入
        </button>
      </div>

      <!-- File import panel -->
      <div id="tab-file" class="import-tab-panel active">
        <div id="drop-zone" class="drop-zone">
          <div class="drop-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:40px;height:40px;color:var(--primary)"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          </div>
          <div class="drop-hint">拖拽账单文件到此处</div>
          <div class="drop-sub">支持支付宝 .csv 和微信支付 .xlsx 格式</div>
          <div style="margin-top:16px">
            <label class="btn btn-ghost" for="file-input" style="cursor:pointer">选择文件</label>
            <input type="file" id="file-input" accept=".csv,.xlsx" style="display:none" multiple>
          </div>
        </div>
        <div id="import-results"></div>
      </div>

      <!-- Image import panel -->
      <div id="tab-image" class="import-tab-panel">
        <div id="img-quota-bar" class="img-quota-bar" style="display:none"></div>
        <div id="img-drop-zone" class="drop-zone">
          <div class="drop-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:40px;height:40px;color:var(--primary)"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
          </div>
          <div class="drop-hint">拖拽图片到此处</div>
          <div class="drop-sub">支持 JPG / PNG / WebP，单次最多 10 张</div>
          <div class="img-upload-btns">
            <label class="btn btn-ghost" for="img-file-input" style="cursor:pointer">选择图片</label>
            <label class="btn btn-ghost img-camera-label" for="img-camera-input" style="cursor:pointer">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="width:15px;height:15px"><path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z"/><circle cx="12" cy="13" r="4"/></svg>
              拍照
            </label>
            <input type="file" id="img-file-input" accept="image/*" style="display:none" multiple>
            <input type="file" id="img-camera-input" accept="image/*" capture="environment" style="display:none">
          </div>
        </div>

        <!-- Image preview thumbnails -->
        <div id="img-preview-list" class="img-preview-list"></div>

        <!-- Recognition status -->
        <div id="img-recognize-status"></div>

        <!-- Preview table for recognized transactions -->
        <div id="img-recognize-results"></div>
      </div>

      <div class="card">
        <div class="card-title">导入历史</div>
        <div id="import-history"><div class="loading">加载中...</div></div>
      </div>
    `;

    Import._bindTabs(container);
    Import._bindDrop(container);
    Import._bindImageDrop(container);
    Import._loadHistory(container);
    Import._loadImageQuota(container);
    Import._loadCategories();
  },

  /* ---- Tab switching ---- */
  _bindTabs(container) {
    const tabs = container.querySelectorAll(".import-tab");
    tabs.forEach(tab => {
      tab.addEventListener("click", () => {
        tabs.forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        container.querySelectorAll(".import-tab-panel").forEach(p => p.classList.remove("active"));
        container.querySelector(`#tab-${tab.dataset.tab}`).classList.add("active");
      });
    });
  },

  /* ---- File import (existing) ---- */
  _bindDrop(container) {
    const zone = container.querySelector("#drop-zone");
    const fileInput = container.querySelector("#file-input");

    zone.addEventListener("dragover", (e) => {
      e.preventDefault();
      zone.classList.add("dragover");
    });
    zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
    zone.addEventListener("drop", (e) => {
      e.preventDefault();
      zone.classList.remove("dragover");
      Import._uploadFiles(Array.from(e.dataTransfer.files), container);
    });

    fileInput.addEventListener("change", () => {
      Import._uploadFiles(Array.from(fileInput.files), container);
      fileInput.value = "";
    });
  },

  async _uploadFiles(files, container) {
    const resultsEl = container.querySelector("#import-results");
    if (!files.length) return;
    const file = files[0];
    if (files.length > 1) {
      resultsEl.innerHTML = `<div class="img-recognize-empty">当前版本一次先预览 1 份账单，请确认后再继续下一份。</div>`;
    } else {
      resultsEl.innerHTML = "";
    }

    const formData = new FormData();
    formData.append("file", file);

    const card = document.createElement("div");
    card.className = "import-result";
    card.innerHTML = `<div class="card-title">正在解析 <strong>${file.name}</strong>…</div>`;
    resultsEl.prepend(card);

    try {
      const preview = await API.imports.preview(formData);
      Import._filePreview = preview;
      Import._fileSelectedIdxs = new Set(
        preview.items.map((_, idx) => idx).filter(idx => !(preview.duplicates && preview.duplicates[idx]))
      );
      Import._renderFilePreview(container);
    } catch (err) {
      card.innerHTML = `<div class="card-title" style="color:#ef4444">❌ 解析失败: ${file.name}</div>
        <div style="color:#64748b;font-size:13px;margin-top:6px">${err.message}</div>`;
    }
  },

  async _loadCategories() {
    try {
      const res = await API.transactions.categories();
      Import._categories = res.categories || [];
    } catch (_) {
      Import._categories = [];
    }
  },

  /* ---- Image import ---- */
  _bindImageDrop(container) {
    const zone = container.querySelector("#img-drop-zone");
    const fileInput = container.querySelector("#img-file-input");
    const cameraInput = container.querySelector("#img-camera-input");

    zone.addEventListener("dragover", (e) => {
      e.preventDefault();
      zone.classList.add("dragover");
    });
    zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
    zone.addEventListener("drop", (e) => {
      e.preventDefault();
      zone.classList.remove("dragover");
      const imgFiles = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith("image/"));
      if (imgFiles.length) Import._handleImageFiles(imgFiles, container);
    });

    fileInput.addEventListener("change", () => {
      const imgFiles = Array.from(fileInput.files);
      if (imgFiles.length) Import._handleImageFiles(imgFiles, container);
      fileInput.value = "";
    });

    cameraInput.addEventListener("change", () => {
      const imgFiles = Array.from(cameraInput.files);
      if (imgFiles.length) Import._handleImageFiles(imgFiles, container);
      cameraInput.value = "";
    });
  },

  async _loadImageQuota(container) {
    const bar = container.querySelector("#img-quota-bar");
    if (!bar) return;
    try {
      const q = await API.imports.imageQuota();
      Import._quotaData = q;
      const remaining = q.remaining;
      bar.style.display = "";
      if (remaining <= 0) {
        bar.className = "img-quota-bar img-quota-bar--exhausted";
        bar.innerHTML = `⚠️ 今日图片识别额度已用完（${q.daily_used}/${q.daily_limit}），请明天再试`;
      } else {
        bar.className = "img-quota-bar";
        bar.innerHTML = `今日图片识别额度：已用 <strong>${q.daily_used}</strong> / ${q.daily_limit} 张，剩余 <strong>${remaining}</strong> 张`;
      }
    } catch (_) { bar.style.display = "none"; }
  },

  async _handleImageFiles(files, container) {
    if (files.length > 10) {
      alert("最多同时上传 10 张图片");
      files = files.slice(0, 10);
    }

    // Show thumbnails
    const previewList = container.querySelector("#img-preview-list");
    previewList.innerHTML = "";
    for (const file of files) {
      const thumb = document.createElement("div");
      thumb.className = "img-thumb";
      const url = URL.createObjectURL(file);
      thumb.innerHTML = `<img src="${url}" alt="${file.name}"><span class="img-thumb-name">${file.name}</span>`;
      previewList.appendChild(thumb);
    }

    // Show loading with countdown
    const statusEl = container.querySelector("#img-recognize-status");
    const TIMEOUT_SEC = 30;
    let countdown = TIMEOUT_SEC;
    statusEl.innerHTML = `
      <div class="img-recognize-loading">
        <div class="spinner"></div>
        <span>正在识别图片中的交易信息，请稍候… <em id="img-countdown">${countdown}s</em></span>
      </div>
    `;
    const countdownEl = statusEl.querySelector("#img-countdown");
    const countdownTimer = setInterval(() => {
      countdown--;
      if (countdownEl) countdownEl.textContent = countdown + "s";
      if (countdown <= 0) clearInterval(countdownTimer);
    }, 1000);

    const resultsEl = container.querySelector("#img-recognize-results");
    resultsEl.innerHTML = "";

    // Call recognition API
    const formData = new FormData();
    for (const file of files) {
      formData.append("files", file);
    }

    try {
      const response = await API.imports.recognizeImages(formData, { timeoutMs: TIMEOUT_SEC * 1000 });
      clearInterval(countdownTimer);
      Import._recognizedTransactions = response.transactions || [];
      Import._imageFilenames = response.filenames || [];

      if (Import._recognizedTransactions.length === 0) {
        statusEl.innerHTML = `<div class="img-recognize-empty">未能从图片中识别出交易记录，请检查图片内容</div>`;
        return;
      }

      // Update quota display after recognition
      if (response.daily_used != null && response.daily_limit != null) {
        Import._quotaData = { daily_used: response.daily_used, daily_limit: response.daily_limit, remaining: Math.max(0, response.daily_limit - response.daily_used) };
        Import._loadImageQuota(container);
      }

      statusEl.innerHTML = `
        <div class="img-recognize-success">
          ✅ 从 ${response.image_count} 张图片中识别出 <strong>${Import._recognizedTransactions.length}</strong> 条交易记录
          <span style="color:var(--text-muted);font-size:12px;margin-left:8px">（可编辑后确认导入）</span>
        </div>
      `;

      // Check for duplicates
      Import._dupFlags = [];
      try {
        const dupResult = await API.imports.checkDuplicates(Import._recognizedTransactions);
        Import._dupFlags = dupResult.duplicates || [];
        const dupCount = Import._dupFlags.filter(Boolean).length;
        if (dupCount > 0) {
          statusEl.innerHTML = `
            <div class="img-recognize-success">
              ✅ 从 ${response.image_count} 张图片中识别出 <strong>${Import._recognizedTransactions.length}</strong> 条交易记录
              <span style="color:#f59e0b;font-size:13px;margin-left:8px">⚠️ ${dupCount} 条疑似重复（已标黄，确认时自动跳过）</span>
            </div>
          `;
        }
      } catch (_) { /* non-critical */ }

      Import._renderPreviewTable(container);
    } catch (err) {
      clearInterval(countdownTimer);
      statusEl.innerHTML = `
        <div class="img-recognize-error">
          ❌ 识别失败: ${err.message}
        </div>
      `;
    }
  },

  _renderPreviewTable(container) {
    const resultsEl = container.querySelector("#img-recognize-results");
    const txs = Import._recognizedTransactions;
    const isMobile = window.innerWidth <= 768;

    const directionOptions = (val) => {
      const opts = [
        { v: "expense", l: "支出" },
        { v: "income", l: "收入" },
        { v: "neutral", l: "不计收支" },
      ];
      return opts.map(o => `<option value="${o.v}" ${o.v === val ? "selected" : ""}>${o.l}</option>`).join("");
    };

    const directionLabel = (val) => {
      return { expense: "支出", income: "收入", neutral: "不计收支" }[val] || val;
    };

    if (isMobile) {
      // Card-based layout for mobile
      const nonDupCount = txs.filter((_, i) => !(Import._dupFlags && Import._dupFlags[i])).length;
      resultsEl.innerHTML = `
        <div class="card img-preview-card">
          <div class="card-title" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">
            <span>识别结果预览</span>
            <div style="display:flex;gap:8px">
              <button class="btn btn-ghost" id="img-cancel-btn">取消</button>
              <button class="btn btn-primary" id="img-confirm-btn">确认导入 (${nonDupCount})</button>
            </div>
          </div>
          <div class="img-mobile-cards">
            ${txs.map((t, i) => {
              const isDup = Import._dupFlags && Import._dupFlags[i];
              return `
              <div class="img-mobile-card${isDup ? " img-dup-row" : ""}" data-idx="${i}">
                <div class="img-mobile-card-header">
                  <input type="checkbox" class="img-row-check" data-idx="${i}" ${isDup ? "" : "checked"}>
                  ${isDup ? '<span class="img-dup-badge">重复</span>' : ""}
                  <span class="img-mobile-card-dir ${t.direction}">${directionLabel(t.direction)}</span>
                  <span class="img-mobile-card-amount ${t.direction}">¥${t.amount.toFixed(2)}</span>
                </div>
                <div class="img-mobile-card-body">
                  <div class="img-mobile-field">
                    <label>时间</label>
                    <input type="text" class="img-cell-input" data-field="transaction_time" value="${Import._escAttr(t.transaction_time)}">
                  </div>
                  <div class="img-mobile-field">
                    <label>类型</label>
                    <select class="img-cell-select" data-field="direction">${directionOptions(t.direction)}</select>
                  </div>
                  <div class="img-mobile-field">
                    <label>金额</label>
                    <input type="number" class="img-cell-input" data-field="amount" value="${t.amount}" step="0.01" min="0">
                  </div>
                  <div class="img-mobile-field">
                    <label>分类</label>
                    <input type="text" class="img-cell-input" data-field="category" value="${Import._escAttr(t.category)}">
                  </div>
                  <div class="img-mobile-field">
                    <label>对方</label>
                    <input type="text" class="img-cell-input" data-field="counterparty" value="${Import._escAttr(t.counterparty)}">
                  </div>
                  <div class="img-mobile-field">
                    <label>商品</label>
                    <input type="text" class="img-cell-input" data-field="product" value="${Import._escAttr(t.product)}">
                  </div>
                  <div class="img-mobile-field">
                    <label>支付</label>
                    <input type="text" class="img-cell-input" data-field="payment_method" value="${Import._escAttr(t.payment_method)}">
                  </div>
                  <div class="img-mobile-field">
                    <label>备注</label>
                    <input type="text" class="img-cell-input" data-field="remark" value="${Import._escAttr(t.remark)}">
                  </div>
                </div>
              </div>
            `}).join("")}
          </div>
        </div>
      `;
    } else {
      // Table layout for desktop
      const nonDupCount = txs.filter((_, i) => !(Import._dupFlags && Import._dupFlags[i])).length;
      resultsEl.innerHTML = `
        <div class="card img-preview-card">
          <div class="card-title" style="display:flex;align-items:center;justify-content:space-between">
            <span>识别结果预览</span>
            <div>
              <button class="btn btn-ghost" id="img-cancel-btn">取消</button>
              <button class="btn btn-primary" id="img-confirm-btn">确认导入 (${nonDupCount})</button>
            </div>
          </div>
          <div class="img-preview-table-wrap">
            <table class="img-preview-table">
              <thead>
                <tr>
                  <th style="width:40px"></th>
                  <th style="min-width:155px">时间</th>
                  <th>类型</th>
                  <th>金额</th>
                  <th>分类</th>
                  <th>交易对方</th>
                  <th>商品/描述</th>
                  <th>支付方式</th>
                  <th>备注</th>
                </tr>
              </thead>
              <tbody>
                ${txs.map((t, i) => {
                  const isDup = Import._dupFlags && Import._dupFlags[i];
                  return `
                  <tr data-idx="${i}" class="${isDup ? "img-dup-row" : ""}">
                    <td style="white-space:nowrap">
                      <input type="checkbox" class="img-row-check" data-idx="${i}" ${isDup ? "" : "checked"}>
                      ${isDup ? '<span class="img-dup-badge" title="数据库中已存在">重复</span>' : ""}
                    </td>
                    <td><input type="text" class="img-cell-input img-cell-time" data-field="transaction_time" value="${Import._escAttr(t.transaction_time)}" placeholder="YYYY-MM-DD HH:MM:SS"></td>
                    <td><select class="img-cell-select" data-field="direction">${directionOptions(t.direction)}</select></td>
                    <td><input type="number" class="img-cell-input img-cell-amount" data-field="amount" value="${t.amount}" step="0.01" min="0"></td>
                    <td><input type="text" class="img-cell-input" data-field="category" value="${Import._escAttr(t.category)}"></td>
                    <td><input type="text" class="img-cell-input" data-field="counterparty" value="${Import._escAttr(t.counterparty)}"></td>
                    <td><input type="text" class="img-cell-input" data-field="product" value="${Import._escAttr(t.product)}"></td>
                    <td><input type="text" class="img-cell-input" data-field="payment_method" value="${Import._escAttr(t.payment_method)}"></td>
                    <td><input type="text" class="img-cell-input" data-field="remark" value="${Import._escAttr(t.remark)}"></td>
                  </tr>`;
                }).join("")}
              </tbody>
            </table>
          </div>
        </div>
      `;
    }

    // Bind inline edits (works for both mobile cards and desktop table)
    resultsEl.querySelectorAll(".img-cell-input, .img-cell-select").forEach(el => {
      el.addEventListener("change", () => {
        const parent = el.closest("[data-idx]");
        const idx = parseInt(parent.dataset.idx);
        const field = el.dataset.field;
        let val = el.value;
        if (field === "amount") val = parseFloat(val) || 0;
        Import._recognizedTransactions[idx][field] = val;
      });
    });

    // Cancel button
    resultsEl.querySelector("#img-cancel-btn").addEventListener("click", () => {
      Import._recognizedTransactions = [];
      resultsEl.innerHTML = "";
      container.querySelector("#img-recognize-status").innerHTML = "";
      container.querySelector("#img-preview-list").innerHTML = "";
    });

    // Update confirm button count when checkboxes change
    const updateConfirmCount = () => {
      const checked = resultsEl.querySelectorAll(".img-row-check:checked").length;
      const btn = resultsEl.querySelector("#img-confirm-btn");
      if (btn) btn.textContent = `确认导入 (${checked})`;
    };
    resultsEl.querySelectorAll(".img-row-check").forEach(cb => {
      cb.addEventListener("change", updateConfirmCount);
    });

    // Confirm button
    resultsEl.querySelector("#img-confirm-btn").addEventListener("click", () => {
      Import._confirmImageImport(container);
    });
  },

  async _confirmImageImport(container) {
    const resultsEl = container.querySelector("#img-recognize-results");
    const statusEl = container.querySelector("#img-recognize-status");

    // Collect checked rows only
    const checkedIdxs = new Set();
    resultsEl.querySelectorAll(".img-row-check:checked").forEach(cb => {
      checkedIdxs.add(parseInt(cb.dataset.idx));
    });

    const txsToImport = Import._recognizedTransactions.filter((_, i) => checkedIdxs.has(i));
    if (!txsToImport.length) {
      alert("请至少选择一条记录");
      return;
    }

    // Validate fields before submitting
    const errors = [];
    const timeRe = /^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?$/;
    txsToImport.forEach((t, i) => {
      const idx = i + 1;
      if (!t.transaction_time || !timeRe.test(t.transaction_time.trim())) {
        errors.push(`第 ${idx} 条：时间格式无效，请使用 YYYY-MM-DD HH:MM:SS`);
      } else {
        const d = new Date(t.transaction_time.replace(" ", "T"));
        if (isNaN(d.getTime())) errors.push(`第 ${idx} 条：时间日期无效`);
      }
      if (!t.amount || t.amount <= 0) errors.push(`第 ${idx} 条：金额必须大于 0`);
      if (!["expense", "income", "neutral"].includes(t.direction)) errors.push(`第 ${idx} 条：类型无效`);
    });
    if (errors.length) {
      // Highlight error fields in UI
      resultsEl.querySelectorAll(".img-cell-input").forEach(el => el.classList.remove("input-error"));
      checkedIdxs.forEach(idx => {
        const t = Import._recognizedTransactions[idx];
        const row = resultsEl.querySelector(`[data-idx="${idx}"]`);
        if (!row) return;
        if (!t.transaction_time || !timeRe.test(t.transaction_time.trim()) || isNaN(new Date(t.transaction_time.replace(" ", "T")).getTime())) {
          const el = row.querySelector('[data-field="transaction_time"]');
          if (el) el.classList.add("input-error");
        }
        if (!t.amount || t.amount <= 0) {
          const el = row.querySelector('[data-field="amount"]');
          if (el) el.classList.add("input-error");
        }
      });
      alert("请修正以下问题：\n" + errors.slice(0, 5).join("\n") + (errors.length > 5 ? `\n…等共 ${errors.length} 个错误` : ""));
      return;
    }

    // Disable button
    const btn = resultsEl.querySelector("#img-confirm-btn");
    btn.disabled = true;
    btn.textContent = "导入中…";

    try {
      const result = await API.imports.confirmImageImport(txsToImport, Import._imageFilenames || []);
      const statusColor = result.status === "success" ? "#22c55e" : result.status === "failed" ? "#ef4444" : "#f59e0b";

      resultsEl.innerHTML = `
        <div class="import-result">
          <div class="card-title">✅ 图片导入完成
            <span style="color:${statusColor};font-weight:600;margin-left:8px">${result.status.toUpperCase()}</span>
          </div>
          <div class="result-row">
            <div class="stat"><span class="n success">${result.imported_rows}</span><span class="l">成功导入</span></div>
            <div class="stat"><span class="n danger">${result.error_rows}</span><span class="l">失败</span></div>
            <div class="stat"><span class="n">${result.total_rows}</span><span class="l">总条数</span></div>
          </div>
        </div>
      `;
      statusEl.innerHTML = "";
      container.querySelector("#img-preview-list").innerHTML = "";
      Import._recognizedTransactions = [];
      Import._loadHistory(container);
      Import._loadImageQuota(container);
    } catch (err) {
      btn.disabled = false;
      btn.textContent = `确认导入 (${txsToImport.length})`;
      alert("导入失败: " + err.message);
    }
  },

  _renderFilePreview(container) {
    const resultsEl = container.querySelector("#import-results");
    const preview = Import._filePreview;
    if (!preview) return;

    const summary = Import._getFileReviewSummary();
    const categoryOptions = Import._categories.map(c => `<option value="${Import._escAttr(c)}">`).join("");
    resultsEl.innerHTML = `
      <div class="card img-preview-card">
        <div class="card-title" style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap">
          <span>文件导入预览 · ${preview.filename}</span>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <button class="btn btn-ghost" id="file-cancel-btn">取消</button>
            <button class="btn btn-primary" id="file-confirm-btn">确认导入 (${summary.selected})</button>
          </div>
        </div>
        <div class="img-review-toolbar">
          <div class="img-review-summary-grid">
            <div class="img-review-summary-card"><span class="label">总条数</span><strong>${summary.total}</strong></div>
            <div class="img-review-summary-card"><span class="label">将导入</span><strong>${summary.selected}</strong></div>
            <div class="img-review-summary-card"><span class="label">总收入</span><strong>${fmtMoney(preview.total_income || 0)}</strong></div>
            <div class="img-review-summary-card"><span class="label">总支出</span><strong>${fmtMoney(preview.total_expense || 0)}</strong></div>
            <div class="img-review-summary-card ${summary.anomalyCount ? "is-warn" : ""}"><span class="label">异常条数</span><strong>${summary.anomalyCount}</strong></div>
            <div class="img-review-summary-card ${summary.duplicateCount ? "is-warn" : ""}"><span class="label">重复条数</span><strong>${summary.duplicateCount}</strong></div>
          </div>
          <div class="img-review-actions">
            <button class="btn btn-ghost btn-sm" id="file-select-valid-btn">全选有效项</button>
            <button class="btn btn-ghost btn-sm" id="file-select-anomaly-btn">选中异常项</button>
            <div class="img-review-batch">
              <input type="text" id="file-batch-category" list="file-category-datalist" placeholder="批量改分类">
              <datalist id="file-category-datalist">${categoryOptions}</datalist>
              <button class="btn btn-ghost btn-sm" id="file-apply-category-btn">应用</button>
            </div>
            <button class="btn btn-ghost btn-sm" id="file-delete-selected-btn">删除选中</button>
          </div>
        </div>
        <div class="img-preview-table-wrap">
          <table class="img-preview-table file-preview-table">
            <thead>
              <tr>
                <th style="width:40px"></th>
                <th style="min-width:155px">时间</th>
                <th>方向</th>
                <th>金额</th>
                <th>分类</th>
                <th>交易对方</th>
                <th>商品</th>
                <th>支付方式</th>
                <th>备注</th>
                <th>提示</th>
              </tr>
            </thead>
            <tbody>
              ${preview.items.map((item, idx) => {
                const issues = Import._getFileRowIssues(item, idx);
                return `
                <tr data-file-idx="${idx}" class="${issues.length ? " img-anomaly-row" : ""}${preview.duplicates[idx] ? " img-dup-row" : ""}">
                  <td style="white-space:nowrap">
                    <input type="checkbox" class="file-row-check" data-idx="${idx}" ${Import._fileSelectedIdxs.has(idx) ? "checked" : ""}>
                    ${preview.duplicates[idx] ? '<span class="img-dup-badge">重复</span>' : ""}
                  </td>
                  <td>${fmtDate(item.transaction_time)}</td>
                  <td>${item.direction === "income" ? "收入" : item.direction === "expense" ? "支出" : "不计收支"}</td>
                  <td style="font-weight:600;color:${item.direction === "income" ? "var(--income)" : item.direction === "expense" ? "var(--expense)" : "inherit"}">${fmtMoney(item.amount)}</td>
                  <td><input type="text" class="img-cell-input ${Import._fileHasIssue(issues, "category") ? "input-warning" : ""}" list="file-category-datalist" data-field="category" value="${Import._escAttr(item.category)}"></td>
                  <td>${item.counterparty || "—"}</td>
                  <td>${item.product || "—"}</td>
                  <td>${item.payment_method || "—"}</td>
                  <td><input type="text" class="img-cell-input" data-field="remark" value="${Import._escAttr(item.remark)}"></td>
                  <td><div class="img-issue-list">${issues.length ? issues.map(issue => `<span class="img-issue-badge">${issue.label}</span>`).join("") : '<span class="img-issue-ok">正常</span>'}</div></td>
                </tr>`;
              }).join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;

    resultsEl.querySelectorAll(".file-row-check").forEach(cb => {
      cb.addEventListener("change", () => {
        Import._fileSelectedIdxs = new Set(
          Array.from(resultsEl.querySelectorAll(".file-row-check:checked")).map(el => parseInt(el.dataset.idx))
        );
        Import._renderFilePreview(container);
      });
    });

    resultsEl.querySelectorAll("[data-file-idx] .img-cell-input").forEach(input => {
      input.addEventListener("change", () => {
        const row = input.closest("[data-file-idx]");
        const idx = parseInt(row.dataset.fileIdx);
        const field = input.dataset.field;
        Import._filePreview.items[idx][field] = input.value.trim();
        Import._renderFilePreview(container);
      });
    });

    resultsEl.querySelector("#file-cancel-btn")?.addEventListener("click", () => {
      Import._filePreview = null;
      Import._fileSelectedIdxs = new Set();
      resultsEl.innerHTML = "";
    });

    resultsEl.querySelector("#file-select-valid-btn")?.addEventListener("click", () => {
      Import._fileSelectedIdxs = new Set(
        preview.items.map((_, idx) => idx).filter(idx => !Import._getFileRowIssues(preview.items[idx], idx).some(issue => issue.type === "duplicate"))
      );
      Import._renderFilePreview(container);
    });

    resultsEl.querySelector("#file-select-anomaly-btn")?.addEventListener("click", () => {
      Import._fileSelectedIdxs = new Set(
        preview.items.map((_, idx) => idx).filter(idx => Import._getFileRowIssues(preview.items[idx], idx).length > 0)
      );
      Import._renderFilePreview(container);
    });

    resultsEl.querySelector("#file-apply-category-btn")?.addEventListener("click", () => {
      const category = (resultsEl.querySelector("#file-batch-category")?.value || "").trim();
      if (!category) return alert("请先填写要批量应用的分类");
      if (!Import._fileSelectedIdxs.size) return alert("请先选择要修改的记录");
      Import._fileSelectedIdxs.forEach(idx => {
        if (Import._filePreview.items[idx]) Import._filePreview.items[idx].category = category;
      });
      Import._renderFilePreview(container);
    });

    resultsEl.querySelector("#file-delete-selected-btn")?.addEventListener("click", () => {
      if (!Import._fileSelectedIdxs.size) return alert("请先选择要删除的记录");
      const keepIdxs = preview.items.map((_, idx) => idx).filter(idx => !Import._fileSelectedIdxs.has(idx));
      Import._filePreview.items = keepIdxs.map(idx => preview.items[idx]);
      Import._filePreview.duplicates = keepIdxs.map(idx => preview.duplicates[idx]);
      Import._fileSelectedIdxs = new Set(
        Import._filePreview.items.map((_, idx) => idx).filter(idx => !Import._filePreview.duplicates[idx])
      );
      Import._renderFilePreview(container);
    });

    resultsEl.querySelector("#file-confirm-btn")?.addEventListener("click", () => {
      Import._confirmFileImport(container);
    });
  },

  async _confirmFileImport(container) {
    const resultsEl = container.querySelector("#import-results");
    const preview = Import._filePreview;
    if (!preview) return;

    const txsToImport = preview.items.filter((_, idx) => Import._fileSelectedIdxs.has(idx));
    if (!txsToImport.length) return alert("请至少选择一条记录");

    const btn = resultsEl.querySelector("#file-confirm-btn");
    btn.disabled = true;
    btn.textContent = `导入中… (${txsToImport.length})`;

    try {
      const result = await API.imports.confirmFileImport(preview.filename, preview.source, txsToImport);
      const statusColor = result.status === "success" ? "#22c55e" : result.status === "failed" ? "#ef4444" : "#f59e0b";
      resultsEl.innerHTML = `
        <div class="import-result">
          <div class="card-title">✅ 文件导入完成
            <span style="color:${statusColor};font-weight:600;margin-left:8px">${result.status.toUpperCase()}</span>
          </div>
          <div class="result-row">
            <div class="stat"><span class="n success">${result.imported_rows}</span><span class="l">成功导入</span></div>
            <div class="stat"><span class="n warn">${result.duplicate_rows}</span><span class="l">重复跳过</span></div>
            <div class="stat"><span class="n danger">${result.error_rows}</span><span class="l">失败</span></div>
            <div class="stat"><span class="n">${result.total_rows}</span><span class="l">总条数</span></div>
          </div>
        </div>
      `;
      Import._filePreview = null;
      Import._fileSelectedIdxs = new Set();
      Import._loadHistory(container);
    } catch (err) {
      btn.disabled = false;
      btn.textContent = `确认导入 (${txsToImport.length})`;
      alert("导入失败: " + err.message);
    }
  },

  _getFileReviewSummary() {
    let anomalyCount = 0;
    let duplicateCount = 0;
    const preview = Import._filePreview;
    if (!preview) return { total: 0, selected: 0, anomalyCount: 0, duplicateCount: 0 };
    preview.items.forEach((item, idx) => {
      const issues = Import._getFileRowIssues(item, idx);
      if (issues.length) anomalyCount += 1;
      if (issues.some(issue => issue.type === "duplicate")) duplicateCount += 1;
    });
    return {
      total: preview.items.length,
      selected: Import._fileSelectedIdxs.size,
      anomalyCount,
      duplicateCount,
    };
  },

  _getFileRowIssues(item, idx) {
    const issues = [];
    if (Import._filePreview?.duplicates?.[idx]) {
      issues.push({ type: "duplicate", field: "row", label: "重复" });
    }
    if (!item.category || !item.category.trim()) {
      issues.push({ type: "missing-category", field: "category", label: "缺分类" });
    }
    return issues;
  },

  _fileHasIssue(issues, field) {
    return issues.some(issue => issue.field === field);
  },

  _escAttr(str) {
    if (!str) return "";
    return String(str).replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  },

  /* ---- Import history ---- */
  async _loadHistory(container) {
    const el = container.querySelector("#import-history");
    try {
      const batches = await API.imports.list();
      if (!batches.length) {
        el.innerHTML = `<div class="empty">暂无导入记录</div>`;
        return;
      }

      const sourceLabel = (s) => {
        if (s === "alipay") return "支付宝";
        if (s === "wechat") return "微信支付";
        if (s === "image") return "图片识别";
        return s;
      };

      el.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>文件名</th>
              <th>来源</th>
              <th>导入时间</th>
              <th>总行数</th>
              <th>成功</th>
              <th>重复</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            ${batches.map(b => `
              <tr>
                <td style="max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${b.filename}">${b.filename}</td>
                <td>${sourceLabel(b.source)}</td>
                <td>${fmtDate(b.imported_at)}</td>
                <td>${b.total_rows}</td>
                <td style="color:#22c55e">${b.imported_rows}</td>
                <td style="color:#f59e0b">${b.duplicate_rows}</td>
                <td>
                  <span class="badge ${b.status === 'success' ? 'badge-income' : b.status === 'failed' ? 'badge-expense' : 'badge-neutral'}">
                    ${b.status}
                  </span>
                </td>
              </tr>`).join("")}
          </tbody>
        </table>
      `;
    } catch (err) {
      showError(el, err.message);
    }
  },
};
