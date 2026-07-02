# AGENT.md — Autocoin 项目指南

> 本文档面向 AI 开发者，描述 Autocoin 个人记账应用的项目结构、架构模式、数据模型和关键实现细节。
> 最后更新于 2026 年。

---

## 一、项目概述

**Autocoin** 是一款个人记账与统计分析 Web 应用，基于 **FastAPI（Python）后端 + 原生 JavaScript SPA 前端** 的单一仓库架构。支持支付宝/微信账单导入、**多券商收入分析**、**股票详情**、**图片智能识别导入**（多模态 LLM）、**AI 自动分类**、**数据备份还原**、**特殊数据处理**等功能。支持多用户隔离、暗黑模式与移动端适配。

- **后端：** Python 3.9+, FastAPI, SQLAlchemy 2.0 ORM, SQLite（WAL 模式）
- **行情依赖：** yfinance（美股 Yahoo Finance 数据）、AKShare（A 股财经数据）
- **前端：** 原生 JS SPA（无框架）, Chart.js 图表, CSS 自定义属性暗黑模式
- **部署：** Docker + docker-compose, 单进程同时服务 API 和静态文件, 端口 8000

---

## 二、项目结构

```
autocoin-t/
├── main.py                          # 入口：uvicorn 启动
├── AGENT.md                         # 本文档 — AI 项目指南
├── CLAUDE.md                        # 主 AI 上下文文档
├── README.md                        # 用户文档
├── pyproject.toml                   # 项目配置与依赖（uv 包管理器）
├── Dockerfile                       # 多阶段构建（python:3.12-slim + uv）
├── docker-compose.yml               # 单服务部署
├── uv.lock                          # 依赖锁定文件
│
├── autocoin/                        # 后端 Python 包
│   ├── __init__.py
│   ├── app.py                       # FastAPI 应用工厂（中间件、异常处理、路由注册、静态文件挂载）
│   ├── config.py                    # Pydantic Settings（AUTOCOIN_ 环境变量前缀）
│   ├── auth.py                      # JWT 认证（python-jose）、bcrypt 密码哈希、依赖注入
│   ├── database.py                  # SQLAlchemy 引擎、会话工厂、数据库初始化、轻量迁移
│   │
│   ├── models/                      # SQLAlchemy ORM 模型
│   │   ├── user.py                  # 用户模型
│   │   ├── transaction.py           # 交易记录模型（含 product_alias 字段）
│   │   ├── classification_rule.py   # 自动分类规则模型
│   │   ├── alias_rule.py            # 别名映射规则模型（新增）
│   │   ├── import_batch.py          # 导入批次模型
│   │   ├── user_preference.py       # 用户偏好设置模型（key-value 存储，新增）
│   │   ├── stock_data.py            # 股票录入批次数据
│   │   └── stock_api_cache.py       # 股票接口查询缓存（TTL 3 小时）
│   │
│   ├── schemas/                     # Pydantic 请求/响应模型
│   │   ├── auth.py                  # 注册/登录/改密/Token 模型
│   │   ├── transaction.py           # 交易 CRUD 模型
│   │   ├── classification_rule.py   # 分类规则模型
│   │   ├── alias_rule.py            # 别名规则模型（新增）
│   │   ├── import_schema.py         # 导入相关模型
│   │   └── statistics.py            # 统计模型
│   │
│   ├── repository/                  # 数据访问层（Repository 模式）
│   │   ├── base.py                  # DataRepository 抽象基类
│   │   └── sqlite.py                # SQLiteRepository 实现（按用户隔离）
│   │
│   ├── parsers/                     # 账单解析器（策略模式）
│   │   ├── base.py                  # BillParser 抽象基类 + ParsedTransaction 数据类
│   │   ├── alipay.py                # 支付宝 CSV（GBK 编码）解析器
│   │   ├── wechat.py                # 微信支付 XLSX 解析器
│   │   ├── cmb_securities.py        # 招商证券 XLS（GBK TSV）解析器（新增）
│   │   ├── ibkr.py                  # 盈透IBKR CSV 解析器，含汇率转换（新增）
│   │   ├── moomoo.py                # MOOMOO PDF 解析器，含汇率转换（新增）
│   │   └── hsbc_pulse.py           # 汇丰 PULSE 信用卡 PDF 解析器（新增）
│   │
│   ├── services/                    # 业务逻辑层
│   │   ├── import_service.py        # 文件导入服务
│   │   ├── image_recognizer.py      # 图片识别服务（多 LLM 降级链）
│   │   ├── stats_service.py         # 统计服务
│   │   └── stock_market_service.py  # 股票行情查询与缓存服务
│   │
│   └── routers/                     # API 路由（全部在 /api/v1 下）
│       ├── auth.py                  # 注册/登录/改密
│       ├── transactions.py          # 交易 CRUD + 批量操作 + 导出
│       ├── imports.py               # 文件/图片导入流水线
│       ├── rules.py                 # 分类规则 + 别名规则 CRUD
│       ├── statistics.py            # 数据统计
│       ├── broker_income_analysis.py # 券商收入分析（新增）
│       ├── ai_classification.py     # AI 自动分类（新增）
│       ├── stock_management.py      # 股票详情：录入、聚合、明细分页、行情查询
│       ├── data_management.py       # 数据备份还原（新增）
│       └── special_data_processing.py # 特殊数据处理：退款候选匹配与确认
│
├── frontend/                        # 前端静态文件（原生 JS SPA）
│   ├── index.html                   # SPA 外壳（侧边栏、顶部栏、移动端底部栏）
│   ├── css/styles.css               # 响应式布局 + 暗黑模式 + 动画
│   └── js/
│       ├── api.js                   # API 客户端 + JWT Token 管理
│       ├── app.js                   # 哈希路由器 + 鉴权守卫 + 主题切换
│       ├── auth.js                  # 登录/注册页（含邀请码验证）
│       ├── charts.js                # Chart.js 封装 + 格式化工具函数
│       ├── dashboard.js             # 概览页（摘要卡片/月度图表/分类饼图）
│       ├── transactions.js          # 账单页（CRUD/筛选/批量操作/导出）
│       ├── import.js                # 导入页（文件/图片/券商导入）
│       ├── rules.js                 # 规则页（分类规则 + 别名规则）
│       ├── stats.js                 # 统计页（年度/月度/分类/钻取）
│       ├── broker-income-analysis.js # 券商收入分析页（新增）
│       ├── stock-management.js      # 股票详情页（新增）
│       ├── data-management.js       # 数据管理页（备份/还原，新增）
│       ├── special-data-processing.js # 特殊数据处理页：退款数据处理
│       └── ai-classification.js     # AI 自动分类页（新增）
│
├── tests/                           # pytest 自动化测试
│   ├── conftest.py                  # 测试数据库设置/清理
│   ├── test_parsers.py              # 解析器测试（21 个）
│   ├── test_image_recognizer.py     # 图片识别测试（10 个）
│   └── test_api.py                  # API 集成测试（32 个）
│
├── VibeCodeing/                     # 功能实现文档（开发过程记录）
│   ├── alias-rules-implementation.md
│   ├── broker-income-analysis-implementation.md
│   ├── broker-income-analysis-detail-charts-implementation.md
│   ├── data-management-implementation.md
│   ├── full-database-backup-restore-implementation.md
│   ├── hsbc-pulse-import-implementation.md
│   ├── ibkr-import-implementation.md
│   └── moomoo-import-implementation.md
│
├── docs/                            # 截图等文档资源
│   └── images/
│
├── capture_screenshots.py           # 截图工具脚本
└── migrate_add_user.py              # 旧数据库迁移脚本（添加默认用户）
```

---

## 三、架构模式

| 模式 | 位置 | 说明 |
|------|------|------|
| **Repository** | `autocoin/repository/` | `DataRepository` 抽象基类 + `SQLiteRepository` 实现；所有查询按 `user_id` 隔离 |
| **Parser Strategy** | `autocoin/parsers/` | `BillParser` 抽象基类 + `can_parse()` 自动检测（支付宝/微信/招证/IBKR/MOOMOO/汇丰） |
| **LLM 降级链** | `autocoin/services/image_recognizer.py` | 按优先级依次尝试：智谱 → 通义千问 → DeepSeek → OpenAI → Gemini |
| **分类引擎** | `autocoin/repository/sqlite.py` | 正则匹配 + 优先级排序，创建交易时自动应用分类 + 别名规则 |
| **应用工厂** | `autocoin/app.py` | `create_app()` 组装中间件、异常处理、路由、静态文件挂载 |
| **软删除** | `autocoin/models/transaction.py` | `is_deleted` 标志位（0/1），物理删除独立存在（`hard_delete_transaction`） |
| **多用户隔离** | 所有 Repository 方法 | 通过 JWT 中的 `user_id` 隔离数据，bcrypt 密码哈希 |
| **Hash 路由 SPA** | `frontend/js/app.js` | 客户端哈希路由 + 鉴权守卫，无框架依赖 |
| **SSE 流式更新** | `autocoin/routers/ai_classification.py` | AI 分类时通过 Server-Sent Events 推送进度 |

---

## 四、数据库模型（SQLite，6 张表）

### 4.1 users（用户表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | 自增主键 |
| username | String(64) | NOT NULL, UNIQUE | 用户名（字母/数字/下划线/中文） |
| password_hash | String(128) | NOT NULL | bcrypt 哈希 |
| created_at | DateTime | NOT NULL | 创建时间 |

### 4.2 transactions（交易记录表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | 自增主键 |
| user_id | Integer | NOT NULL, indexed | 用户 ID |
| source | String(20) | NOT NULL, indexed | 来源（alipay/wechat/manual/image/招商证券/盈透IBKR/MOOMOO/汇丰PULSE） |
| source_order_id | String(64) | NULLABLE | 来源方订单号 |
| merchant_order_id | String(64) | NULLABLE | 商户订单号 |
| transaction_time | DateTime | NOT NULL, indexed | 交易时间 |
| transaction_type | String(64) | NULLABLE | 原始交易类型 |
| category | String(64) | NULLABLE, indexed | 用户分类（可编辑） |
| counterparty | String(128) | NULLABLE | 交易对方 |
| counterparty_account | String(128) | NULLABLE | 对方账户 |
| product | Text | NULLABLE | 商品说明（原始） |
| product_alias | String(128) | NULLABLE, indexed | 商品别名（由别名规则设置） |
| direction | String(10) | NOT NULL, indexed | 方向（income/expense/neutral） |
| amount | Float | NOT NULL | 金额 |
| payment_method | String(64) | NULLABLE | 支付方式 |
| status | String(32) | NULLABLE | 状态 |
| remark | Text | NULLABLE | 备注 |
| import_batch_id | String(36) | NULLABLE, indexed | 导入批次 UUID |
| created_at | DateTime | NOT NULL | 创建时间 |
| updated_at | DateTime | NOT NULL | 更新时间 |
| is_deleted | Integer | NOT NULL, default=0 | 软删除标志 |
| finishrefundcheck | Integer | NOT NULL, default=0, indexed | 退款检测确认标记（0/NULL 未确认，1 已确认） |
| is_ai_classified | Integer | NOT NULL, default=0, indexed | AI 分类确认标记（0/NULL 未确认，1 已确认） |

> **唯一约束：** `(user_id, source, source_order_id)` — 防止同一来源的相同订单重复导入。

### 4.3 classification_rules（分类规则表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | 自增主键 |
| user_id | Integer | NOT NULL, indexed | 用户 ID |
| name | String(128) | NOT NULL | 规则名称 |
| priority | Integer | NOT NULL, default=100, indexed | 优先级（越小越优先） |
| is_active | Boolean | NOT NULL, default=True, indexed | 是否启用 |
| match_counterparty | String(128) | NOT NULL, default="" | 匹配交易对方（正则） |
| match_product | Text | NOT NULL, default="" | 匹配商品说明（正则） |
| match_payment_method | String(64) | NOT NULL, default="" | 匹配支付方式（正则） |
| match_transaction_type | String(64) | NOT NULL, default="" | 匹配原始交易类型（正则） |
| category | String(64) | NOT NULL | 命中后填充分类 |
| remark | Text | NOT NULL | 命中后填写备注 |
| created_at | DateTime | NOT NULL | 创建时间 |
| updated_at | DateTime | NOT NULL | 更新时间 |

### 4.4 alias_rules（别名映射规则表）— 新增

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | 自增主键 |
| user_id | Integer | NOT NULL, indexed | 用户 ID |
| name | String(128) | NOT NULL | 规则名称 |
| priority | Integer | NOT NULL, default=100, indexed | 优先级（越小越优先） |
| is_active | Boolean | NOT NULL, default=True, indexed | 是否启用 |
| match_counterparty | String(128) | NOT NULL, default="" | 匹配交易对方 |
| match_product | Text | NOT NULL, default="" | 匹配商品说明 |
| match_payment_method | String(64) | NOT NULL, default="" | 匹配支付方式 |
| match_transaction_type | String(64) | NOT NULL, default="" | 匹配交易类型 |
| product_alias | String(128) | NOT NULL, default="" | 映射后的商品别名 |
| created_at | DateTime | NOT NULL | 创建时间 |
| updated_at | DateTime | NOT NULL | 更新时间 |

### 4.5 import_batches（导入批次表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK | UUID 主键 |
| user_id | Integer | NOT NULL, indexed | 用户 ID |
| filename | String(256) | NOT NULL | 文件名 |
| source | String(20) | NULLABLE | 来源 |
| imported_at | DateTime | NOT NULL | 导入时间 |
| total_rows | Integer | NOT NULL, default=0 | 总行数 |
| imported_rows | Integer | NOT NULL, default=0 | 成功导入行数 |
| duplicate_rows | Integer | NOT NULL, default=0 | 重复行数 |
| error_rows | Integer | NOT NULL, default=0 | 错误行数 |
| status | String(20) | NOT NULL | 状态（imported/部分导入等） |

### 4.6 user_preferences（用户偏好表）— 新增

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | 自增主键 |
| user_id | Integer | NOT NULL, indexed | 用户 ID |
| key | String(64) | NOT NULL | 偏好键名 |
| value | Text | NOT NULL, default="" | 偏好值（JSON 序列化） |
| created_at | DateTime | NOT NULL | 创建时间 |
| updated_at | DateTime | NOT NULL | 更新时间 |

> **唯一约束：** `(user_id, key)` — 每个用户每项偏好唯一。

### 4.7 stockdata（股票录入批次表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| stock_vid | String(16) | UNIQUE, indexed | 64 位随机 ID 的 16 位十六进制表示 |
| user_id | Integer | NOT NULL, indexed | 用户 ID |
| stock_market | String(8) | NOT NULL, indexed | 市场：CN/US |
| stock_id | String(32) | NOT NULL, indexed | 股票代码 |
| stock_name | String(128) | NULLABLE | 股票名称 |
| stock_alias | String(128) | NULLABLE, indexed | 别名，同用户同市场同代码最后修改会同步历史批次 |
| stock_amount | Float | NOT NULL | 数量 |
| stock_average_price | Float | NULLABLE | 批次平均成本 |
| stock_currency | String(8) | NOT NULL | CN=CNY，US=USD |
| stock_remark | Text | NULLABLE | 备注，最多 50 字 |
| stock_transaction_date | DateTime | NULLABLE | 成交日期，用户选填 |
| stock_entry_time | DateTime | NOT NULL | 录入时间，保存时自动写入 |

### 4.8 stock_api_cache（股票行情缓存表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| stock_market | String(8) | NOT NULL, indexed | 市场：CN/US |
| stock_id | String(32) | NOT NULL, indexed | 股票代码 |
| stock_name | String(128) | NULLABLE | 接口返回名称 |
| current_price | Float | NULLABLE | 实时价格 |
| stock_currency | String(8) | NOT NULL | 币种 |
| queried_at | DateTime | NOT NULL, indexed | 查询时间，TTL 3 小时 |

> **唯一约束：** `(stock_market, stock_id)` — 同一市场同一股票只保留一份行情缓存。

---

## 五、API 路由

所有 API 路由前缀为 `/api/v1`，除注册/登录外均需 JWT Bearer 认证。

### 5.1 认证 `/auth`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/register` | 注册（需邀请码 `tarikz`，自动登录返回 Token） |
| POST | `/auth/login` | 登录 |
| GET | `/auth/me` | 获取当前用户信息 |
| POST | `/auth/change-password` | 修改密码（需旧密码验证） |

### 5.2 交易 `/transactions`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/transactions` | 分页查询（日期/方向/分类/来源/搜索/排序） |
| POST | `/transactions` | 手动创建（自动应用分类+别名规则） |
| GET | `/transactions/{id}` | 获取单条 |
| PUT | `/transactions/{id}` | 更新（分类/备注/方向） |
| DELETE | `/transactions/{id}` | 软删除 |
| GET | `/transactions/categories` | 获取已有分类列表 |
| GET | `/transactions/export/csv` | 导出 CSV |
| GET | `/transactions/export/excel` | 导出 Excel |
| POST | `/transactions/batch/delete` | 批量软删除 |
| POST | `/transactions/batch/hard-delete` | 批量物理删除（新增） |
| POST | `/transactions/batch/update` | 批量更新分类/方向 |

### 5.3 导入 `/imports`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/imports` | 上传并直接导入 |
| POST | `/imports/preview` | 预览账单文件（支付宝/微信） |
| POST | `/imports/preview/cmb-securities` | 预览招商证券文件（新增） |
| POST | `/imports/preview/ibkr` | 预览盈透IBKR文件（新增） |
| POST | `/imports/preview/moomoo` | 预览MOOMOO文件（新增） |
| POST | `/imports/preview/hsbc-pulse` | 预览汇丰PULSE文件（新增） |
| POST | `/imports/confirm` | 确认导入预览结果 |
| POST | `/imports/image/recognize` | 上传图片，LLM 识别交易信息 |
| POST | `/imports/image/confirm` | 确认导入识别结果 |
| POST | `/imports/image/check-duplicates` | 检测重复交易 |
| GET | `/imports/image/quota` | 查询今日识别额度 |
| GET | `/imports` | 导入历史列表 |
| GET | `/imports/{id}` | 导入详情 |

### 5.4 规则 `/rules`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/rules` | 分类规则列表 |
| POST | `/rules` | 创建分类规则 |
| PUT | `/rules/{rule_id}` | 更新分类规则 |
| DELETE | `/rules/{rule_id}` | 删除分类规则 |
| POST | `/rules/reclassify` | 对所有交易重新分类（返回差异） |
| GET | `/rules/aliases` | 别名规则列表（新增） |
| POST | `/rules/aliases` | 创建别名规则（新增） |
| PUT | `/rules/aliases/{rule_id}` | 更新别名规则（新增） |
| DELETE | `/rules/aliases/{rule_id}` | 删除别名规则（新增） |
| POST | `/rules/aliases/realias` | 对所有交易重新映射别名（新增） |

### 5.5 统计 `/statistics`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/statistics/summary` | 收支汇总（支持来源筛选） |
| GET | `/statistics/monthly` | 月度统计（支持来源筛选 + 自定义日期范围） |
| GET | `/statistics/category` | 分类统计（支持来源筛选） |
| GET | `/statistics/daily` | 每日统计（支持来源筛选） |

### 5.6 券商收入分析 `/broker-income-analysis`（新增）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/broker-income-analysis/preferences/sources` | 获取用户选定的收入来源偏好 |
| PUT | `/broker-income-analysis/preferences/sources` | 更新来源偏好 |
| GET | `/broker-income-analysis/transactions` | 查询券商收入交易 |
| GET | `/broker-income-analysis/categories` | 获取分类列表（可按来源过滤） |
| GET | `/broker-income-analysis/monthly` | 月度收入统计 |
| GET | `/broker-income-analysis/income-by-source` | 按来源汇总收入 |
| GET | `/broker-income-analysis/income-by-product` | 按产品汇总收入 |

### 5.7 AI 分类 `/ai-classification`（新增）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/ai-classification/preferences` | 获取 AI 自动分类用户偏好（分类列表、DeepSeek API key、Prompt 模板） |
| PUT | `/ai-classification/preferences` | 更新 AI 自动分类用户偏好 |
| POST | `/ai-classification/classify` | 调用 DeepSeek API 进行 AI 自动分类（SSE 流式返回进度） |
| POST | `/ai-classification/confirm` | 确认并写入 AI 分类结果 |

### 5.8 股票详情 `/stock-management`（新增）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/stock-management/lookup` | 查询股票名称、实时价和已有别名，行情缓存 TTL 3 小时 |
| POST | `/stock-management/stocks` | 新增股票批次记录；查询行情失败仍允许保存；平均成本为空时优先取当前价 |
| GET | `/stock-management/stocks/summary` | 按用户、市场、股票代码聚合资产；返回资产列表和按币种/CNY 折算的组合统计 |
| GET | `/stock-management/stocks/{stock_market}/{stock_id}/records` | 查询某只股票批次明细，最多每页 5 条 |

### 5.9 数据管理 `/data-management`（新增）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/data-management/backup/export` | 导出完整数据库备份（CSV，UTF-8 BOM） |
| POST | `/data-management/backup/validate` | 验证备份文件格式 |
| POST | `/data-management/backup/restore` | 还原备份数据 |

### 5.10 特殊数据处理 `/special-data-processing`（新增）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/special-data-processing/refunds/search` | 查询当前用户未确认的疑似退款数据，并返回匹配支出候选 |
| POST | `/special-data-processing/refunds/confirm` | 确认退款处理结果，标记疑似退款和被选中的支出候选 |
| POST | `/special-data-processing/wealth/search` | 查询当前用户支付宝余额宝疑似理财数据 |
| POST | `/special-data-processing/wealth/confirm` | 将用户勾选的疑似理财数据标为不计 |

---

## 六、关键实现细节

### 6.1 交易分类引擎

**分类规则**和**别名规则**是两套独立的规则系统，结构相似但作用不同：

- **分类规则（`classification_rules`）：** 命中后设置交易的 `category` 和 `remark` 字段。原始分类会被追加入 remark（记录变更历史）。
- **别名规则（`alias_rules`）：** 命中后设置交易的 `product_alias` 字段（商品别名），不影响分类。

**匹配逻辑：**
1. 规则按 `priority`（升序）排序，优先级相同按 `id`（升序）
2. 对每条规则，用 `re.search(IGNORECASE)` 依次匹配 `counterparty`、`product`、`payment_method`、`transaction_type`
3. **第一条命中的规则生效**（不继续匹配后续规则）
4. 创建交易时自动应用，也可通过 `/rules/reclassify` 和 `/rules/aliases/realias` 批量重算

### 6.2 文件导入流水线（6 种文件格式）

| 来源 | 文件格式 | 解析方式 | 特点 |
|------|---------|---------|------|
| 支付宝 | `.csv`（GBK） | `csv.DictReader` | 方向由"收/支"字段决定 |
| 微信支付 | `.xlsx` | `openpyxl` | 处理 `¥` 前缀，合成订单 ID |
| 招商证券 | `.xls`（实际是 GBK TSV） | 手动解析 | 仅提取股息/红利记录 |
| 盈透IBKR | `.csv`（UTF-8 BOM） | 按章节解析 | 多区域活动账单，**自动汇率转换**（USD/HKD → CNY） |
| MOOMOO | `.pdf` | `pdftotext -layout` | 列位置解析**现金变动**，**自动汇率转换** |
| 汇丰PULSE | `.pdf` | `pdftotext -layout` | 正则解析信用卡交易，**年份跨边界处理** |

> **注：** PDF 解析依赖 `poppler-utils`（Docker 中已安装 `pdftotext`）。汇率转换使用 [frankfurter.dev](https://api.frankfurter.dev) 实时汇率，带缓存（按货币缓存）。

### 6.3 图片识别流水线

1. 上传图片 → 尝试多模态 LLM 识别
2. **LLM 提供商降级链：** 智谱 GLM-4V → 通义千问 Qwen-VL → DeepSeek VL2 → OpenAI GPT-4o → Gemini
3. 按 `AUTOCOIN_LLM_PROVIDER_ORDER` 配置的顺序尝试，跳过未配置 API Key 的提供商
4. 解析 LLM 返回的 JSON → 去重检测（时间 + 金额 + 对方） → 用户预览编辑 → 确认导入
5. 每日识别额度：按识别张数计算（`AUTOCOIN_IMAGE_IMPORT_DAILY_LIMIT`，默认 10）

### 6.4 AI 自动分类

- 使用 **DeepSeek API**，通过 SSE 流式推送进度
- 用户输入分类列表（逗号分隔），AI 将所有交易强制归入这些分类
- 分类列表未配置时默认值为 `餐饮美食，交通出行，汽车，母婴儿童，娱乐，购物，生活缴费，社保费用，医疗，旅游，其他`
- 分类列表、DeepSeek API key、AI Prompt 模板保存于 `user_preferences`，偏好 key 为 `ai_classification.preferences`
- AI Prompt 默认展开展示，默认模板为中文精简分类规则；接口协议部分使用 `{category_map}`、`{transactions}`
- 偏好接口返回 `default_prompt_template`，前端“重置为默认Prompt”按钮用它恢复文本框内容
- “重置为默认Prompt”右侧的“本次最多处理”是 `/classify` 的一次性 `limit` 参数，`0` 表示不限制，不写入 `user_preferences`
- “调试模式”是 `/classify` 的一次性 `debug` 参数，默认关闭，不写入 `user_preferences`；开启后失败详情包含本批 Prompt、DeepSeek 请求内容、原始返回片段和响应元信息，并可在前端下载 `.txt` 调试日志；请求内容包含批次交易数据但不包含 API key
- 分类输入框说明下方有默认收起的“选择时间范围”区域；开始/结束日期是 `/classify` 的一次性 `start_date` / `end_date` 参数，默认不选表示全部日期，不写入 `user_preferences`
- 默认输入协议使用分类编号和紧凑交易行：`id|当前分类|交易对方|商品说明`；不发送备注、金额、时间、订单号等其他字段
- 默认输出协议为 `{"t":[[id,分类编号]]}`，后端会映射回分类名称；不兼容旧版对象格式或字符串分类
- 页面默认勾选“仅分类支出数据”和“只处理未经AI分类的数据”，两者均不持久化；默认只处理 `expense` 且 `is_ai_classified != 1`，取消支出筛选时处理非“不计”数据
- `/ai-classification/classify` 执行前会保存本次提交的分类列表、API key、Prompt 模板，并按用户模板调用 DeepSeek
- 分批处理（每批 50 条，DeepSeek `max_tokens=8192`，最多 5 并发线程，每次请求 3 次重试，超时 600 秒）；若返回 `finish_reason=length` 或不完整 JSON，会自动二分拆批继续处理，最多拆分 3 层
- 批次失败后 SSE 会返回最近失败详情，前端展示批次号、条数和尽量完整的错误摘要；DeepSeek 返回非 JSON 时会展示原始返回片段
- 默认严格提示词确保 AI 只输出指定分类；用户自定义 Prompt 后以后端收到的模板为准
- 预览弹窗确认后才写入数据库；确认时提交全部预览结果并将交易 `is_ai_classified=1`，自定义分类留空用 AI 新分类，填写后用自定义分类，取消弹窗不写入

### 6.5 数据备份还原

- **导出：** 遍历所有 6 张表，每行序列化为 JSON，写入 CSV（UTF-8 BOM 编码），文件名带时间戳
- **验证：** 检查 CSV 版本号、表结构完整性
- **还原：** 先按反向顺序清空所有表 → 重置 SQLite 自增计数器 → 事务性插入所有数据 → 失败回滚

### 6.6 前端路由（11 个页面）

| 路由 | 页面 | 说明 |
|------|------|------|
| `#/login` | 登录/注册 | 含邀请码验证、实时表单校验 |
| `#/dashboard` | 概览 | 摘要卡片 + 月度柱状图 + 分类环形图 + 近期交易 |
| `#/transactions` | 账单明细 | 筛选/搜索/分页/行内编辑/批量操作/导出 |
| `#/broker-income-analysis` | 券商收入分析 | 来源筛选 + 4 个图表 + 导出 |
| `#/stock-management` | 股票详情 | 股票批次录入 + 资产聚合 + 按币种/CNY 折算组合统计 + 明细展开分页 |
| `#/import` | 导入 | 文件导入 + 图片导入 + 券商导入快捷键 |
| `#/rules` | 规则 | 分类规则 + 别名规则双标签，带差异对比对话框 |
| `#/stats` | 统计分析 | 年度/月度/分类分析，分类钻取查看明细 |
| `#/special-data-processing` | 特殊数据处理 | 退款数据处理、理财数据检查 |
| `#/data-management` | 数据管理 | 全量备份导出/导入还原/交易管理 |
| `#/ai-analysis` | AI 分析 | AI 自动分类（SSE 进度 + 预览确认） |

### 6.7 用户认证

- JWT Token 存储于 `localStorage`，所有 API 请求自动附加 `Authorization: Bearer`
- 注册需邀请码（硬编码为 `tarikz`）
- 用户名规则：2-32 位，仅含字母/数字/下划线/中文
- 密码规则：至少 8 位，需同时含字母和数字
- 登录错误信息统一（防枚举攻击）
- 401 响应时前端自动登出并跳转 `/login`
- 启动时验证 JWT 有效性，过期自动跳转登录页

### 6.8 暗黑模式

- CSS 自定义属性（`data-theme="dark"`），所有颜色变量切换
- 自动跟随系统偏好（`prefers-color-scheme`）
- 选择持久化存储于 `localStorage`
- 主题切换时自动刷新 Chart.js 图表颜色

---

## 七、配置说明

所有配置通过 `AUTOCOIN_` 前缀的环境变量设置：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `AUTOCOIN_DATABASE_URL` | 数据库连接 | `sqlite:///./autocoin.db` |
| `AUTOCOIN_JWT_SECRET` | JWT 签名密钥 | ⚠️ 开发用默认值，生产环境必改 |
| `AUTOCOIN_JWT_EXPIRE_MINUTES` | Token 过期（分钟） | `10080`（7 天） |
| `AUTOCOIN_CORS_ORIGINS` | 允许的 CORS 域名 | `["*"]` |
| `AUTOCOIN_LLM_PROVIDER_ORDER` | LLM 提供商优先级 | `zhipu,qwen,deepseek,openai,gemini` |
| `AUTOCOIN_LLM_TIMEOUT` | LLM 请求超时（秒）| `60` |
| `AUTOCOIN_IMAGE_IMPORT_DAILY_LIMIT` | 每日图片识别上限 | `10` |
| `AUTOCOIN_OPENAI_API_KEY` / `_MODEL` / `_BASE_URL` | OpenAI 配置 | — |
| `AUTOCOIN_GEMINI_API_KEY` / `_MODEL` | Gemini 配置 | — |
| `AUTOCOIN_ZHIPU_API_KEY` / `_MODEL` / `_BASE_URL` | 智谱 GLM 配置 | — |
| `AUTOCOIN_QWEN_API_KEY` / `_MODEL` / `_BASE_URL` | 通义千问配置 | — |
| `AUTOCOIN_DEEPSEEK_API_KEY` / `_MODEL` / `_BASE_URL` | DeepSeek 配置 | — |

---

## 八、测试

- 框架：pytest + httpx + FastAPI TestClient
- 测试数据库：内存 SQLite（每次测试自动创建/销毁）
- 测试文件：`tests/test_parsers.py`（21 个）、`tests/test_image_recognizer.py`（10 个）、`tests/test_api.py`（32 个），合计 63 个
- 运行：`pytest tests/ -v`

---

## 九、开发与部署

```bash
# 本地开发
uv sync              # 安装依赖
uv run python main.py  # 启动（默认 http://localhost:8000）

# Docker 部署
docker compose up -d

# 运行测试
uv sync --extra dev
uv run pytest tests/ -v

# 生产环境设置密钥
AUTOCOIN_JWT_SECRET=$(openssl rand -hex 32) docker compose up -d
```

---

## 十、关于本文档

与 `CLAUDE.md` 的关系：

- **CLAUDE.md：** 主 AI 上下文文档，覆盖项目概览、架构、API、配置与运行方式
- **AGENT.md（本文）：** 补充文档，提供更详细的数据库表结构字段说明和部署细节

> 如需了解特定功能的实现细节，可参考 `VibeCodeing/` 目录下的功能实现文档。
