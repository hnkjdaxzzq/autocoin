/* ===== Statistics page ===== */
const Stats = {
  render(container) {
    const year = new Date().getFullYear();
    const month = new Date().getMonth() + 1;

    container.innerHTML = `
      <div class="page-header">
        <h1 class="page-title">统计分析</h1>
      </div>

      <!-- Year controls -->
      <div class="stats-controls">
        <label style="font-weight:600">年份</label>
        <select id="stat-year">
          ${[year, year - 1, year - 2].map(y => `<option value="${y}" ${y === year ? "selected" : ""}>${y}年</option>`).join("")}
        </select>
        <button class="btn btn-primary" id="btn-load-year">加载年度数据</button>
      </div>

      <!-- Year summary cards -->
      <div class="summary-grid" id="stat-year-summary"></div>

      <!-- Monthly overview charts for the year -->
      <div class="charts-grid" style="margin-bottom:24px">
        <div class="card">
          <div class="card-title" id="monthly-title">月度收支（${year}年）</div>
          <div class="chart-canvas-wrap"><canvas id="stat-monthly-bar"></canvas></div>
        </div>
        <div class="card">
          <div class="card-title">收支净额趋势</div>
          <div class="chart-canvas-wrap"><canvas id="stat-net-line"></canvas></div>
        </div>
      </div>

      <!-- Monthly detail -->
      <div class="card" style="margin-bottom:24px">
        <div class="card-title">月度明细列表</div>
        <div id="stat-monthly-table"></div>
      </div>

      <!-- Category analysis -->
      <div class="page-header" style="margin-top:8px">
        <h2 style="font-size:16px;font-weight:700">分类分析</h2>
      </div>
      <div class="stats-controls">
        <label>日期范围
          <input type="date" id="cat-start">
          <span style="color:#94a3b8">—</span>
          <input type="date" id="cat-end">
        </label>
        <select id="cat-direction">
          <option value="expense">支出</option>
          <option value="income">收入</option>
        </select>
        <button class="btn btn-primary" id="btn-cat">分析</button>
      </div>

      <div class="charts-grid">
        <div class="card">
          <div class="card-title">分类金额排行</div>
          <div class="chart-canvas-wrap"><canvas id="stat-cat-bar"></canvas></div>
        </div>
        <div class="card">
          <div class="card-title">分类占比</div>
          <div class="chart-canvas-wrap"><canvas id="stat-cat-donut"></canvas></div>
        </div>
      </div>

      <div class="card" style="margin-top:16px">
        <div class="card-title">分类明细</div>
        <div id="stat-cat-table"></div>
      </div>
    `;

    // Set default category date range to current year
    container.querySelector("#cat-start").value = `${year}-01-01`;
    container.querySelector("#cat-end").value = `${year}-12-31`;

    // Bind events
    container.querySelector("#btn-load-year").addEventListener("click", () => {
      Stats._loadYear(container);
    });
    container.querySelector("#btn-cat").addEventListener("click", () => {
      Stats._loadCategory(container);
    });

    // Initial load
    Stats._loadYear(container);
    Stats._loadCategory(container);
  },

  async _loadYear(container) {
    const year = parseInt(container.querySelector("#stat-year").value);
    container.querySelector("#monthly-title").textContent = `月度收支（${year}年）`;

    try {
      const data = await API.stats.monthly(year);
      Stats._renderYearSummary(container, data.months, year);
      Stats._renderMonthlyCharts(container, data, year);
      Stats._renderMonthlyTable(container, data.months);
    } catch (err) {
      showError(container.querySelector("#stat-monthly-table"), err.message);
    }
  },

  _renderYearSummary(container, months, year) {
    const totalIncome = months.reduce((s, m) => s + m.income, 0);
    const totalExpense = months.reduce((s, m) => s + m.expense, 0);
    const balance = totalIncome - totalExpense;
    const totalCount = months.reduce((s, m) => s + m.count, 0);

    container.querySelector("#stat-year-summary").innerHTML = `
      <div class="summary-card">
        <div class="label">${year}年 总收入</div>
        <div class="value income">${fmtMoney(totalIncome)}</div>
      </div>
      <div class="summary-card">
        <div class="label">${year}年 总支出</div>
        <div class="value expense">${fmtMoney(totalExpense)}</div>
      </div>
      <div class="summary-card">
        <div class="label">${year}年 结余</div>
        <div class="value net ${balance >= 0 ? "positive" : "negative"}">${fmtMoney(balance)}</div>
      </div>
      <div class="summary-card">
        <div class="label">${year}年 总笔数</div>
        <div class="value" style="color:var(--primary)">${totalCount}</div>
      </div>
    `;
  },

  _renderMonthlyCharts(container, data, year) {
    const labels = data.months.map(m => `${m.month}月`);

    Charts.createBar("stat-monthly", container.querySelector("#stat-monthly-bar"), labels, [
      { label: "支出", data: data.months.map(m => m.expense), backgroundColor: "rgba(239,68,68,0.75)" },
      { label: "收入", data: data.months.map(m => m.income), backgroundColor: "rgba(34,197,94,0.75)" },
    ]);

    Charts.createLine("stat-net", container.querySelector("#stat-net-line"), labels, [
      {
        label: "净结余",
        data: data.months.map(m => m.net),
        borderColor: "#4f6ef7",
        backgroundColor: "rgba(79,110,247,0.1)",
        fill: true,
        pointBackgroundColor: data.months.map(m => m.net >= 0 ? "#22c55e" : "#ef4444"),
      },
    ]);
  },

  _renderMonthlyTable(container, months) {
    const el = container.querySelector("#stat-monthly-table");
    const totalIncome = months.reduce((s, m) => s + m.income, 0);
    const totalExpense = months.reduce((s, m) => s + m.expense, 0);
    const totalNet = totalIncome - totalExpense;

    // Compute cumulative balance
    let cumulative = 0;
    const activeMonths = months.filter(m => m.income > 0 || m.expense > 0);
    const cumulativeData = activeMonths.map(m => {
      cumulative += m.net;
      return cumulative;
    });

    el.innerHTML = `
      <table>
        <thead>
          <tr><th>月份</th><th style="text-align:right">收入</th><th style="text-align:right">支出</th><th style="text-align:right">月结余</th><th style="text-align:right">累计结余</th><th style="text-align:right">笔数</th></tr>
        </thead>
        <tbody>
          ${activeMonths.map((m, i) => `
            <tr>
              <td>${m.month}月</td>
              <td style="text-align:right;color:var(--income)">${fmtMoney(m.income)}</td>
              <td style="text-align:right;color:var(--expense)">${fmtMoney(m.expense)}</td>
              <td style="text-align:right;font-weight:600;color:${m.net >= 0 ? "var(--income)" : "var(--expense)"}">
                ${fmtMoney(m.net)}
              </td>
              <td style="text-align:right;font-weight:600;color:${cumulativeData[i] >= 0 ? "var(--income)" : "var(--expense)"}">
                ${fmtMoney(cumulativeData[i])}
              </td>
              <td style="text-align:right">${m.count}</td>
            </tr>`).join("")}
          <tr style="font-weight:700;border-top:2px solid var(--border)">
            <td>合计</td>
            <td style="text-align:right;color:var(--income)">${fmtMoney(totalIncome)}</td>
            <td style="text-align:right;color:var(--expense)">${fmtMoney(totalExpense)}</td>
            <td style="text-align:right;color:${totalNet >= 0 ? "var(--income)" : "var(--expense)"}">${fmtMoney(totalNet)}</td>
            <td style="text-align:right;color:${totalNet >= 0 ? "var(--income)" : "var(--expense)"}">${fmtMoney(totalNet)}</td>
            <td style="text-align:right">${months.reduce((s, m) => s + m.count, 0)}</td>
          </tr>
        </tbody>
      </table>
    `;
  },

  async _loadCategory(container) {
    const params = {
      start_date: container.querySelector("#cat-start").value,
      end_date: container.querySelector("#cat-end").value,
      direction: container.querySelector("#cat-direction").value,
    };

    try {
      const data = await API.stats.category(params);
      Stats._renderCategoryCharts(container, data);
      Stats._renderCategoryTable(container, data);
    } catch (err) {
      showError(container.querySelector("#stat-cat-table"), err.message);
    }
  },

  _renderCategoryCharts(container, data) {
    const top = data.items.slice(0, 12);
    const labels = top.map(i => i.category || "其他");
    const amounts = top.map(i => i.amount);

    Charts.createBar("stat-cat-bar", container.querySelector("#stat-cat-bar"), labels, [
      { label: "金额", data: amounts, backgroundColor: "rgba(79,110,247,0.75)" },
    ]);

    Charts.createDonut(
      "stat-cat-donut",
      container.querySelector("#stat-cat-donut"),
      top.map(i => `${i.category || "其他"} ${i.percentage}%`),
      amounts
    );
  },

  _renderCategoryTable(container, data) {
    const el = container.querySelector("#stat-cat-table");
    if (!data.items.length) {
      el.innerHTML = `<div class="empty">暂无数据</div>`;
      return;
    }

    // Store current filter params for drill-down queries
    Stats._catParams = {
      start_date: container.querySelector("#cat-start").value,
      end_date: container.querySelector("#cat-end").value,
      direction: container.querySelector("#cat-direction").value,
    };

    el.innerHTML = `
      <table>
        <thead>
          <tr>
            <th style="width:24px"></th>
            <th>分类</th>
            <th style="text-align:right">金额</th>
            <th style="text-align:right">笔数</th>
            <th style="text-align:right">占比</th>
          </tr>
        </thead>
        <tbody>
          ${data.items.map((item, idx) => `
            <tr class="cat-row" data-cat="${item.category || ""}" data-idx="${idx}">
              <td><span class="expand-icon">&#9654;</span></td>
              <td>${item.category || "其他"}</td>
              <td style="text-align:right;font-weight:600">${fmtMoney(item.amount)}</td>
              <td style="text-align:right">${item.count}</td>
              <td style="text-align:right">
                <div style="display:flex;align-items:center;justify-content:flex-end;gap:8px">
                  <div style="background:var(--primary);height:6px;border-radius:3px;width:${Math.max(2, item.percentage)}px"></div>
                  ${item.percentage}%
                </div>
              </td>
            </tr>
            <tr class="cat-detail-row" data-idx="${idx}" style="display:none">
              <td colspan="5">
                <div class="cat-detail-wrap" id="cat-detail-${idx}"></div>
              </td>
            </tr>
          `).join("")}
          <tr style="font-weight:700;border-top:2px solid var(--border)">
            <td></td>
            <td>合计</td>
            <td style="text-align:right">${fmtMoney(data.total)}</td>
            <td style="text-align:right">${data.items.reduce((s, i) => s + i.count, 0)}</td>
            <td style="text-align:right">100%</td>
          </tr>
        </tbody>
      </table>
    `;

    // Bind expand/collapse
    el.querySelectorAll(".cat-row").forEach(row => {
      row.addEventListener("click", () => {
        const idx = row.dataset.idx;
        const detailRow = el.querySelector(`.cat-detail-row[data-idx="${idx}"]`);
        const isOpen = row.classList.contains("expanded");

        if (isOpen) {
          row.classList.remove("expanded");
          detailRow.style.display = "none";
        } else {
          row.classList.add("expanded");
          detailRow.style.display = "";
          Stats._loadCategoryDetail(el, row.dataset.cat, idx, 1);
        }
      });
    });
  },

  async _loadCategoryDetail(el, category, idx, page) {
    const wrap = el.querySelector(`#cat-detail-${idx}`);
    wrap.innerHTML = `<div class="loading" style="padding:16px;font-size:13px">加载中...</div>`;

    const pageSize = 10;
    try {
      const data = await API.transactions.list({
        category: category,
        direction: Stats._catParams.direction,
        start_date: Stats._catParams.start_date,
        end_date: Stats._catParams.end_date,
        page: page,
        page_size: pageSize,
        sort_by: "transaction_time",
        sort_dir: "desc",
      });

      if (!data.items.length) {
        wrap.innerHTML = `<div style="padding:16px;text-align:center;color:var(--text-muted);font-size:13px">暂无明细</div>`;
        return;
      }

      const totalPages = data.total_pages;
      wrap.innerHTML = `
        <table class="cat-detail-table">
          <colgroup>
            <col style="width: 150px">
            <col style="width: 90px">
            <col style="width: 140px">
            <col style="width: 180px">
            <col style="width: 100px">
            <col style="width: 120px">
            <col>
          </colgroup>
          <thead>
            <tr>
              <th>时间</th>
              <th>来源</th>
              <th>交易对方</th>
              <th>商品</th>
              <th style="text-align:right">金额</th>
              <th>支付方式</th>
              <th>备注</th>
            </tr>
          </thead>
          <tbody>
            ${data.items.map(tx => `
              <tr>
                <td style="white-space:nowrap">${fmtDate(tx.transaction_time)}</td>
                <td>${tx.source === "alipay" ? "支付宝" : tx.source === "wechat" ? "微信" : tx.source === "image" ? "图片" : "手动"}</td>
                <td style="max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${tx.counterparty || ""}">${tx.counterparty || "—"}</td>
                <td style="max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${tx.product || ""}">${tx.product || "—"}</td>
                <td style="text-align:right;font-weight:600;color:${tx.direction === "income" ? "var(--income)" : "var(--expense)"}">${fmtMoney(tx.amount)}</td>
                <td>${tx.payment_method || "—"}</td>
                <td style="max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${tx.remark || ""}">${tx.remark || "—"}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
        ${totalPages > 1 ? `
          <div class="detail-pager">
            <span>第 ${page}/${totalPages} 页，共 ${data.total} 条</span>
            <button class="dp-prev" ${page <= 1 ? "disabled" : ""}>上一页</button>
            <button class="dp-next" ${page >= totalPages ? "disabled" : ""}>下一页</button>
          </div>
        ` : `<div class="detail-pager"><span>共 ${data.total} 条</span></div>`}
      `;

      // Bind detail pagination (stopPropagation prevents toggling the parent row)
      const prev = wrap.querySelector(".dp-prev");
      const next = wrap.querySelector(".dp-next");
      if (prev) prev.addEventListener("click", (e) => { e.stopPropagation(); Stats._loadCategoryDetail(el, category, idx, page - 1); });
      if (next) next.addEventListener("click", (e) => { e.stopPropagation(); Stats._loadCategoryDetail(el, category, idx, page + 1); });
    } catch (err) {
      wrap.innerHTML = `<div style="padding:16px;color:var(--expense);font-size:13px">加载失败: ${err.message}</div>`;
    }
  },
};
