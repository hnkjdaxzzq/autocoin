# 券商收入分析页面新增明细与图表实现说明

## 原始需求提示词

1、修改券商收入分析页面，增加月度明细列表，类似统计分析页面中的月度明细列表，数据只统计当前页面筛选的数据。
2、增加一个”分券商统计“饼形图，根据数据”来源“进行分组统计，汇总收入金额，并在饼形图图例上显示占比和收入金额
3、增加一个”分股票统计“柱状图，按”别名“进行分组统计，如别名不存在则按照商品名称分组，汇总收入金额

实现完该需求后，将需求实现逻辑及本提示词，写成.md文件，放到项目根目录下的VibeCodeing文件夹下，以供后续参考和修改

## 实现范围

- 券商收入分析页面新增“月度明细列表”，复用统计分析页的表格口径：月份、收入、支出、月结余、累计结余、笔数、合计。
- 新增“分券商统计”饼形图，按交易 `source` 分组，仅汇总收入金额，图例显示来源、占比和收入金额。
- 新增“分股票统计”柱状图，按 `product_alias` 分组；当别名为空时使用 `product`；两者都为空时显示“未命名商品”。柱状图展示收入金额排行，前端最多展示前 20 项。
- 三类新增统计均基于券商收入分析页面当前筛选条件：日期范围、方向、来源多选、分类、搜索关键词。

## 后端实现逻辑

- `autocoin/repository/sqlite.py`
  - 扩展 `get_monthly_stats_range`，新增 `direction`、`category`、`search` 参数，并统一通过 `_build_filter_query` 套用页面筛选条件。
  - 新增 `get_income_stats_by_source`，在当前筛选数据上追加 `direction == "income"`，按 `Transaction.source` 分组汇总收入金额、笔数和占比。
  - 新增 `get_income_stats_by_product`，在当前筛选数据上追加 `direction == "income"`，按 `coalesce(nullif(product_alias, ""), nullif(product, ""), "未命名商品")` 分组汇总收入金额、笔数和占比。

- `autocoin/routers/broker_income_analysis.py`
  - `/broker-income-analysis/monthly` 接收完整页面筛选参数，返回当前筛选范围内的月度统计。
  - 新增 `/broker-income-analysis/income-by-source`，返回分券商收入统计。
  - 新增 `/broker-income-analysis/income-by-product`，返回分股票收入统计。

## 前端实现逻辑

- `frontend/js/api.js`
  - 新增 `API.brokerIncomeAnalysis.incomeBySource(params)`。
  - 新增 `API.brokerIncomeAnalysis.incomeByProduct(params)`。

- `frontend/js/broker-income-analysis.js`
  - 在原有月度图表下方新增两个图表卡片和一个月度明细列表卡片。
  - `_load` 获取当前页面过滤条件后调用 `_loadAnalysis(container, filters)`，所有新增分析都使用同一份 `filters`。
  - `_loadAnalysis` 负责加载月度数据并渲染月度柱状图、净额趋势图和月度明细列表，然后加载分券商饼图和分股票柱状图。
  - `_renderMonthlyTable` 按统计分析页的月度明细样式渲染券商页当前筛选数据。
  - `_loadSourceChart` 使用饼形图图例展示 `来源 占比 金额`。
  - `_loadProductChart` 使用柱状图展示别名或商品名称对应的收入金额，tooltip 展示金额和占比。

## 统计口径说明

- “当前页面筛选的数据”指券商收入分析页面顶部和筛选栏当前所有条件的交集。
- 月度明细统计收入和支出，仅包含 `income` 与 `expense`，不包含 `neutral`。
- 分券商统计和分股票统计汇总“收入金额”，因此会在当前筛选条件基础上进一步限定 `direction == "income"`。
- 如果页面方向筛选被设置为“支出”或“不计收支”，分券商和分股票收入图会显示暂无收入数据，这是当前筛选条件下没有收入数据的结果。

## 验证记录

- `node --check frontend/js/broker-income-analysis.js` 通过。
- `node --check frontend/js/api.js` 通过。
- `python3 -m py_compile autocoin/repository/sqlite.py autocoin/routers/broker_income_analysis.py` 通过。
- 当前环境无 `python` 命令，因此使用 `python3` 完成后端语法检查。
