# 券商收入分析页面实现说明

## 原始需求提示词

新增一个页面，排在左侧导航栏“统计分析”后，名称叫券商收入分析，该页面需求如下：

1、新建一个页面，复制账单明细页面代码，但不要在现有账单明细页面上做修改，券商收入分析这个页面后续要大改，不跟现有逻辑混淆。
2、将来源下拉菜单，改为可复选的菜单，即可实现勾选多个来源，该勾选数据要在用户操作时保存在该用户的数据库中，每次读取，该页面所加载的所有数据以及后续该页面实现所有功能所用到的数据，仅包含来源为当前勾选来源的数据，过滤掉其他来源的数据
3、在明细数据上方增加类似统计分析页面内月度收支柱状表及收支净额趋势图标，根据该页面选择的时间范围呈现

实现完该需求后，将需求实现逻辑及本提示词，写成.md文件，放到项目根目录下的VibeCodeing文件夹下，以供后续参考和修改

## 前端实现

- 新增独立页面脚本 `frontend/js/broker-income-analysis.js`，由账单明细页面复制拆出为 `BrokerIncomeAnalysis` 对象，页面状态、筛选、分页、批量操作、图表加载都与原 `Transactions` 对象分离。
- 在 `frontend/js/app.js` 注册路由 `#/broker-income-analysis`。
- 在 `frontend/index.html` 左侧导航“统计分析”后增加“券商收入分析”入口，并加载新增脚本。
- 来源筛选由单选 `select` 改成复选菜单，默认勾选 `招商证券`、`盈透IBKR`、`MOOMOO`、`汇丰PULSE`。
- 用户每次勾选来源后，会调用后端偏好接口保存到数据库；列表、汇总、分类选项、导出和月度图表统一使用当前勾选来源。
- 明细数据上方新增两张图：月度收支柱状图、收支净额趋势图，按页面日期范围和当前来源筛选渲染。
- `frontend/css/styles.css` 增加多选来源菜单样式。

## 后端实现

- 新增模型 `autocoin/models/user_preference.py`，使用 `user_preferences` 表保存用户级页面偏好。
- `autocoin/database.py` 注册新模型，应用启动 `create_all` 时会创建新表。
- 新增路由 `autocoin/routers/broker_income_analysis.py`，并在 `autocoin/app.py` 注册：
  - `GET /api/v1/broker-income-analysis/preferences/sources`
  - `PUT /api/v1/broker-income-analysis/preferences/sources`
  - `GET /api/v1/broker-income-analysis/transactions`
  - `GET /api/v1/broker-income-analysis/categories`
  - `GET /api/v1/broker-income-analysis/monthly`
- `autocoin/repository/sqlite.py` 扩展来源过滤能力，兼容单来源和逗号分隔多来源；新页面无勾选来源时使用 `__none__` 哨兵值，确保不会误加载全部数据。
- 新增 `get_monthly_stats_range`，按日期范围输出 `YYYY-MM` 月度收入、支出、净额和笔数。
- 统计接口和服务层也兼容可选 `source` 参数，但原统计分析页面不传该参数，现有行为不变。

## 验证记录

- 已通过 `node --check frontend/js/broker-income-analysis.js`。
- 已通过 `node --check frontend/js/api.js`。
- 已通过 `node --check frontend/js/app.js`。
- 已通过 `python3 -m compileall autocoin`。
- `python3 -m pytest tests/test_api.py` 未运行成功：当前 Python 环境没有安装 `pytest`。
- `uv run pytest tests/test_api.py` 未运行成功：当前环境未找到 `pytest` 可执行文件。
- 未启动本地服务：当前 Python 环境缺少 `fastapi` 等运行依赖。
