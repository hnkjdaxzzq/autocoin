/* ===== Import page ===== */
const Import = {
  render(container) {
    container.innerHTML = `
      <div class="page-header">
        <h1 class="page-title">导入账单</h1>
      </div>

      <div id="drop-zone" class="drop-zone">
        <div class="drop-hint">📂 拖拽账单文件到此处</div>
        <div class="drop-sub">支持支付宝 .csv 和微信支付 .xlsx 格式</div>
        <div style="margin-top:16px">
          <label class="btn btn-ghost" for="file-input" style="cursor:pointer">选择文件</label>
          <input type="file" id="file-input" accept=".csv,.xlsx" style="display:none" multiple>
        </div>
      </div>

      <div id="import-results"></div>

      <div class="card">
        <div class="card-title">导入历史</div>
        <div id="import-history"><div class="loading">加载中...</div></div>
      </div>
    `;

    Import._bindDrop(container);
    Import._loadHistory(container);
  },

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

  async _loadHistory(container) {
    const el = container.querySelector("#import-history");
    try {
      const batches = await API.imports.list();
      if (!batches.length) {
        el.innerHTML = `<div class="empty">暂无导入记录</div>`;
        return;
      }
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
                <td>${b.source === "alipay" ? "支付宝" : "微信支付"}</td>
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
