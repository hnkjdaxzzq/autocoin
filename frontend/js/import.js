/* ===== Import page ===== */
const Import = {
  _recognizedTransactions: [],  // holds preview data for image imports

  render(container) {
    container.innerHTML = `
      <div class="page-header">
        <h1 class="page-title">导入账单</h1>
      </div>

      <!-- Tab switcher -->
      <div class="import-tabs">
        <button class="import-tab active" data-tab="file">📂 文件导入</button>
        <button class="import-tab" data-tab="image">📷 图片导入</button>
      </div>

      <!-- File import panel -->
      <div id="tab-file" class="import-tab-panel active">
        <div id="drop-zone" class="drop-zone">
          <div class="drop-hint">📂 拖拽账单文件到此处</div>
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
        <div id="img-drop-zone" class="drop-zone">
          <div class="drop-hint">📷 拖拽图片到此处</div>
          <div class="drop-sub">支持 JPG / PNG / WebP，单次最多 10 张</div>
          <div class="img-upload-btns">
            <label class="btn btn-ghost" for="img-file-input" style="cursor:pointer">选择图片</label>
            <label class="btn btn-ghost img-camera-label" for="img-camera-input" style="cursor:pointer">📷 拍照</label>
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

    for (const file of files) {
      const formData = new FormData();
      formData.append("file", file);

      const card = document.createElement("div");
      card.className = "import-result";
      card.innerHTML = `<div class="card-title">正在导入 <strong>${file.name}</strong>…</div>`;
      resultsEl.prepend(card);

      try {
        const result = await API.imports.upload(formData);
        const statusColor = result.status === "success" ? "#22c55e" : result.status === "failed" ? "#ef4444" : "#f59e0b";
        card.innerHTML = `
          <div class="card-title">✅ <strong>${result.filename}</strong>
            <span style="color:${statusColor};font-weight:600;margin-left:8px">${result.status.toUpperCase()}</span>
          </div>
          <div class="result-row">
            <div class="stat"><span class="n success">${result.imported_rows}</span><span class="l">成功导入</span></div>
            <div class="stat"><span class="n warn">${result.duplicate_rows}</span><span class="l">重复跳过</span></div>
            <div class="stat"><span class="n danger">${result.error_rows}</span><span class="l">解析错误</span></div>
            <div class="stat"><span class="n">${result.total_rows}</span><span class="l">总行数</span></div>
          </div>
        `;
      } catch (err) {
        card.innerHTML = `<div class="card-title" style="color:#ef4444">❌ 导入失败: ${file.name}</div>
          <div style="color:#64748b;font-size:13px;margin-top:6px">${err.message}</div>`;
      }
    }

    Import._loadHistory(container);
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
    const TIMEOUT_SEC = 90;
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

      if (Import._recognizedTransactions.length === 0) {
        statusEl.innerHTML = `<div class="img-recognize-empty">未能从图片中识别出交易记录，请检查图片内容</div>`;
        return;
      }

      statusEl.innerHTML = `
        <div class="img-recognize-success">
          ✅ 从 ${response.image_count} 张图片中识别出 <strong>${Import._recognizedTransactions.length}</strong> 条交易记录
          <span style="color:var(--text-muted);font-size:12px;margin-left:8px">（可编辑后确认导入）</span>
        </div>
      `;

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
      resultsEl.innerHTML = `
        <div class="card img-preview-card">
          <div class="card-title" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">
            <span>识别结果预览</span>
            <div style="display:flex;gap:8px">
              <button class="btn btn-ghost" id="img-cancel-btn">取消</button>
              <button class="btn btn-primary" id="img-confirm-btn">确认导入 (${txs.length})</button>
            </div>
          </div>
          <div class="img-mobile-cards">
            ${txs.map((t, i) => `
              <div class="img-mobile-card" data-idx="${i}">
                <div class="img-mobile-card-header">
                  <input type="checkbox" class="img-row-check" data-idx="${i}" checked>
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
            `).join("")}
          </div>
        </div>
      `;
    } else {
      // Table layout for desktop
      resultsEl.innerHTML = `
        <div class="card img-preview-card">
          <div class="card-title" style="display:flex;align-items:center;justify-content:space-between">
            <span>识别结果预览</span>
            <div>
              <button class="btn btn-ghost" id="img-cancel-btn">取消</button>
              <button class="btn btn-primary" id="img-confirm-btn">确认导入 (${txs.length})</button>
            </div>
          </div>
          <div class="img-preview-table-wrap">
            <table class="img-preview-table">
              <thead>
                <tr>
                  <th style="width:40px"></th>
                  <th>时间</th>
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
                ${txs.map((t, i) => `
                  <tr data-idx="${i}">
                    <td><input type="checkbox" class="img-row-check" data-idx="${i}" checked></td>
                    <td><input type="text" class="img-cell-input" data-field="transaction_time" value="${Import._escAttr(t.transaction_time)}"></td>
                    <td><select class="img-cell-select" data-field="direction">${directionOptions(t.direction)}</select></td>
                    <td><input type="number" class="img-cell-input img-cell-amount" data-field="amount" value="${t.amount}" step="0.01" min="0"></td>
                    <td><input type="text" class="img-cell-input" data-field="category" value="${Import._escAttr(t.category)}"></td>
                    <td><input type="text" class="img-cell-input" data-field="counterparty" value="${Import._escAttr(t.counterparty)}"></td>
                    <td><input type="text" class="img-cell-input" data-field="product" value="${Import._escAttr(t.product)}"></td>
                    <td><input type="text" class="img-cell-input" data-field="payment_method" value="${Import._escAttr(t.payment_method)}"></td>
                    <td><input type="text" class="img-cell-input" data-field="remark" value="${Import._escAttr(t.remark)}"></td>
                  </tr>
                `).join("")}
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

    // Disable button
    const btn = resultsEl.querySelector("#img-confirm-btn");
    btn.disabled = true;
    btn.textContent = "导入中…";

    try {
      const result = await API.imports.confirmImageImport(txsToImport);
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
    } catch (err) {
      btn.disabled = false;
      btn.textContent = `确认导入 (${txsToImport.length})`;
      alert("导入失败: " + err.message);
    }
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
