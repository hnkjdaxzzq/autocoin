# CLAUDE.md

1. **语言要求** — 所有对话、思考过程、文档、代码注释使用中文。
2. **执行要求** — 说明、总结、计划、提交说明统一使用中文。新增或修改 Markdown 文档、代码注释统一使用中文。

## 项目概览

**Autocoin (autocoin-t)** 是一个个人记账/财务 Web 应用 — 单体 SPA + REST API 架构，后端 FastAPI（Python），前端纯原生 JavaScript。

- **后端:** Python 3.9+, FastAPI, SQLAlchemy 2.0 ORM, SQLite（WAL 模式）
- **前端:** 原生 JS SPA（无框架），Chart.js 图表，CSS 自定义属性实现暗黑模式
- **部署:** Docker + docker-compose，单进程同时提供 API 和静态文件，端口 8000

## 项目结构

```
autocoin-t/
├── main.py                          # 入口: uvicorn 启动
├── autocoin/                        # Python 后端包 (~5200 行)
│   ├── app.py                       # FastAPI 应用工厂（中间件、异常处理、路由注册、静态文件挂载）
│   ├── config.py                    # Pydantic Settings，AUTOCOIN_ 环境变量前缀
│   ├── auth.py                      # JWT 认证（python-jose）+ bcrypt 密码哈希
│   ├── database.py                  # SQLAlchemy 引擎、会话工厂、init_db（WAL + FK + 轻量迁移）
│   ├── models/                      # 6 个 ORM 模型
│   │   ├── user.py                  # 用户模型
│   │   ├── transaction.py           # 交易记录（含 merchant_order_id、product_alias）
│   │   ├── classification_rule.py    # 自动分类规则
│   │   ├── import_batch.py          # 导入批次
│   │   ├── alias_rule.py            # 商品别名映射规则
│   │   └── user_preference.py       # 用户偏好 KV 存储
│   ├── repository/                  # 数据访问层（Repository 模式）
│   │   ├── base.py                  # DataRepository 抽象接口
│   │   └── sqlite.py                # SQLite 实现（~1044 行，按 user_id 隔离）
│   ├── parsers/                     # 账单解析器（策略模式）
│   │   ├── base.py                  # BillParser 抽象基类 + ParsedTransaction 数据类
│   │   ├── alipay.py                # 支付宝 CSV 解析（GBK 编码）
│   │   ├── wechat.py                # 微信支付 XLSX 解析
│   │   ├── hsbc_pulse.py            # 汇丰 PULSE 信用卡 PDF（pdftotext）
│   │   ├── ibkr.py                  # 盈透 IBKR CSV（自动汇率换算）
│   │   ├── moomoo.py                # MOOMOO 券商 PDF（pdftotext，自动汇率）
│   │   └── cmb_securities.py        # 招商证券 XLS 交割单
│   ├── services/                    # 业务逻辑层
│   │   ├── import_service.py        # 文件导入服务（解析器检测、分类规则应用、批量插入）
│   │   ├── image_recognizer.py      # 图片识别服务（多 LLM Fallback 链）
│   │   └── stats_service.py         # 统计服务
│   ├── routers/                     # 8 个路由模块，挂载于 /api/v1
│   │   ├── auth.py                  # 注册/登录/修改密码/获取当前用户
│   │   ├── transactions.py          # 账单 CRUD + 批量操作 + CSV/Excel 导出
│   │   ├── imports.py               # 文件/图片导入（预览 → 确认 → 入库）
│   │   ├── rules.py                 # 分类规则 + 别名规则 CRUD + 重新归类/映射
│   │   ├── statistics.py            # 统计查询（汇总/月度/分类/每日）
│   │   ├── broker_income_analysis.py # 券商收益分析（来源偏好、各产品收益）
│   │   ├── data_management.py       # 全量数据库备份/恢复（CSV 格式，含校验）
│   │   └── ai_classification.py     # AI 批量分类（DeepSeek API，SSE 流式进度）
│   └── schemas/                     # Pydantic 请求/响应模型
│       ├── auth.py                  # 注册/登录/修改密码 schema（含邀请码校验）
│       ├── transaction.py           # 交易相关 schema（FilteredSummary 等）
│       ├── classification_rule.py   # 分类规则 schema
│       ├── alias_rule.py            # 别名规则 schema
│       ├── import_schema.py         # 导入相关 schema（文件/图片预览、去重）
│       └── statistics.py            # 统计响应 schema
├── frontend/                        # 原生 JS SPA（~6000 行 JS + ~2100 行 CSS）
│   ├── index.html                   # SPA 外壳（侧边栏、底部 Tab 栏）
│   ├── css/styles.css               # 暗黑模式、响应式布局、动画
│   └── js/
│       ├── api.js                   # API 客户端 + JWT Token 管理
│       ├── app.js                   # Hash 路由、鉴权守卫、暗黑模式切换、修改密码弹窗
│       ├── auth.js                  # 登录/注册页
│       ├── dashboard.js             # 总览（汇总卡片、月度柱状图、分类饼图、近期账单）
│       ├── transactions.js          # 账单页（CRUD、筛选、批量操作、导出）
│       ├── import.js                # 导入页（文件拖拽预览 + 图片 LLM 识别）
│       ├── rules.js                 # 分类规则 CRUD + 别名规则 + 重新归类
│       ├── charts.js                # Chart.js 封装
│       ├── stats.js                 # 年度/月度/分类/日统计 + 下钻
│       ├── broker-income-analysis.js # 券商收益分析（按月、按来源、按产品）
│       ├── data-management.js       # 数据管理（全量备份/恢复）
│       └── ai-classification.js     # AI 自动分类（SSE 流式调用 DeepSeek）
├── tests/                           # pytest + httpx + FastAPI TestClient（共 63 个）
│   ├── conftest.py                  # 测试数据库 setup/teardown
│   ├── test_parsers.py              # 解析器测试（21 个）
│   ├── test_image_recognizer.py     # 图片识别测试（10 个）
│   └── test_api.py                  # API 集成测试（32 个）
├── VibeCodeing/                     # 功能实现说明文档
│   ├── alias-rules-implementation.md
│   ├── broker-income-analysis-implementation.md
│   ├── broker-income-analysis-detail-charts-implementation.md
│   ├── data-management-implementation.md
│   ├── full-database-backup-restore-implementation.md
│   ├── hsbc-pulse-import-implementation.md
│   ├── ibkr-import-implementation.md
│   └── moomoo-import-implementation.md
├── docs/                            # 文档资源（营销文案等）
├── README.md                        # 用户文档
├── LICENSE
├── capture_screenshots.py           # 界面截图脚本
├── migrate_add_user.py              # 旧库迁移脚本（添加 user_id 列）
├── .python-version                  # Python 3.9
├── Dockerfile                       # 多阶段构建（python:3.12-slim + uv），清华镜像源
├── docker-compose.yml               # 单服务，持久卷，端口 8000
├── pyproject.toml                   # Python 项目配置（uv 包管理器）
├── AGENT.md                         # 补充 AI 指南（详细表结构、部署细节）
└── uv.lock                          # 依赖锁文件
```

## 架构模式

| 模式 | 位置 | 描述 |
|------|------|------|
| **Repository** | `autocoin/repository/` | `DataRepository` 抽象 + `SQLiteRepository` 实现；所有查询按 `user_id` 隔离 |
| **Parser 策略** | `autocoin/parsers/` | `BillParser` 抽象基类，`can_parse()` 自动检测，新增 4 个券商解析器 |
| **LLM Fallback 链** | `autocoin/services/image_recognizer.py` | 按优先级尝试：Zhipu → Qwen → DeepSeek → OpenAI → Gemini |
| **分类引擎** | `autocoin/repository/sqlite.py` | 正则匹配 + 优先级排序，创建交易时自动应用分类和别名规则 |
| **别名映射引擎** | `autocoin/repository/sqlite.py` | 与分类引擎类似，但仅映射 `product → product_alias` |
| **App Factory** | `autocoin/app.py` | `create_app()` 组装中间件、异常处理、8 个路由、静态文件挂载 |
| **软删除** | `autocoin/models/transaction.py` | `is_deleted` 标记，不执行物理删除；另提供 `hard_delete` |
| **多用户隔离** | 所有 Repository 方法 | 数据按 `user_id` 从 JWT 提取，bcrypt 密码哈希 |
| **Hash Router SPA** | `frontend/js/app.js` | 客户端路由 + 鉴权守卫，无框架依赖 |
| **SSE 流式处理** | `autocoin/routers/ai_classification.py` | AI 批量分类使用 Server-Sent Events 推送进度 |
| **全量备份/恢复** | `autocoin/routers/data_management.py` | CSV 格式全量备份，含版本校验和元数据验证 |

## 数据库模型（SQLite，6 张表）

- **users** — `id`, `username`(unique), `password_hash`, `created_at`
- **transactions** — `id`, `user_id`(FK), `source`, `source_order_id`, `merchant_order_id`, `transaction_time`, `transaction_type`, `category`, `counterparty`, `counterparty_account`, `product`, `product_alias`, `direction`(income/expense/neutral), `amount`, `payment_method`, `status`, `remark`, `import_batch_id`(FK), `is_deleted`(软删除), timestamps。唯一约束: (user_id, source, source_order_id)
- **classification_rules** — `id`, `user_id`(FK), `name`, `priority`, `is_active`, `match_counterparty`(正则), `match_product`(正则), `match_payment_method`(正则), `match_transaction_type`(正则), `category`, `remark`, timestamps
- **alias_rules** — `id`, `user_id`(FK), `name`, `priority`, `is_active`, 4 个 match 字段（同分类规则）, `product_alias`(映射目标), timestamps
- **import_batches** — `id`(UUID PK), `user_id`(FK), `filename`, `source`, `imported_at`, `total_rows`, `imported_rows`, `duplicate_rows`, `error_rows`, `status`
- **user_preferences** — `id`, `user_id`(FK), `key`, `value`, timestamps，唯一约束: (user_id, key)

## API 路由（全部在 `/api/v1` 下，JWT Bearer 认证）

| 模块 | 关键端点 | 描述 |
|------|----------|------|
| `/auth` | `POST /register`(需要邀请码), `/login`, `GET /me`, `POST /change-password` | 注册（自动登录）、登录、当前用户、修改密码；邀请码硬编码于 `schemas/auth.py` |
| `/transactions` | `GET/POST /`, `PUT/DELETE /{id}`, `POST /batch/delete`, `/batch/hard-delete`, `/batch/update`, `GET /export/csv`, `/export/excel`, `/categories` | 完整 CRUD、批量操作、导出（筛选条件联动） |
| `/imports` | `POST /`, `/preview`, `/confirm`, `GET /`, `GET /{batch_id}`, `/cmb-securities/preview`, `/ibkr/preview`, `/moomoo/preview`, `/hsbc-pulse/preview`, `/image/recognize`, `/image/check-duplicates`, `/image/confirm`, `/image/quota` | 文件导入（预览→确认）、券商专用预览、导入批次查询、图片 LLM 识别 |
| `/rules` | `GET/POST /`, `PUT/DELETE /{id}`, `POST /reclassify` | 分类规则 CRUD，重新归类（返回 diff） |
| `/rules/aliases` | `GET/POST /`, `PUT/DELETE /{id}`, `POST /realias` | 别名规则 CRUD，重新映射（返回 diff） |
| `/statistics` | `GET /summary`, `/monthly`, `/category`, `/daily` | 收支汇总、月度趋势、分类占比、每日明细 |
| `/broker-income-analysis` | `GET /preferences/sources`, `PUT /preferences/sources`, `GET /transactions`, `/categories`, `/monthly`, `/income-by-source`, `/income-by-product` | 券商收益分析（来源偏好设置、按来源/产品统计收益） |
| `/data-management` | `GET /backup/export`, `POST /backup/validate`, `POST /backup/restore` | 全量数据库备份/恢复（CSV，需校验通过） |
| `/ai-classification` | `POST /classify`(SSE 流), `POST /confirm` | DeepSeek 批量 AI 分类，SSE 推送进度 |

## 关键实现细节

### 文件导入流程
上传账单 → 自动检测解析器（支付宝 CSV GBK / 微信 XLSX / 招商证券 XLS / 盈透 IBKR CSV / MOOMOO PDF / 汇丰 PULSE PDF） → 预览（去重高亮、异常标记、每文件摘要卡片） → 用户逐份确认 → 批量插入（规则自动分类 + 别名映射）

### 图片识别流程
上传图片 → 按优先级依次尝试 LLM 提供商（Zhipu GLM-4V → Qwen VL → DeepSeek → OpenAI GPT-4o-mini → Gemini 2.0 Flash） → 解析 JSON 响应 → 去重检测（时间+金额+对方） → 预览编辑 → 确认入库。每日限额默认 10 张/用户。

### AI 批量分类（实验性）
用户在页面填写分类列表 + DeepSeek API Key → SSE 流式请求 `/ai-classification/classify` → 后端分批次（每批 100 条，最多 5 并发）调用 DeepSeek → SSE 推送进度事件（reading → preparing → classifying → complete） → 页面展示 diff 预览 → 用户确认后调用 `/ai-classification/confirm` 更新数据库。

### 分类规则
正则匹配交易字段（counterparty / product / payment_method / transaction_type），优先级高的规则先匹配。创建/导入交易时自动应用。`/rules/reclassify` 重新应用到所有交易并返回 diff。

### 别名规则
与分类规则相同结构的正则匹配引擎，但仅映射 `product → product_alias`。`/rules/aliases/realias` 重新映射所有交易。

### 全量备份/恢复
CSV 格式导出全部 6 张表，包含元数据（版本号、表结构哈希）。恢复时校验版本、表结构、数据完整性，先清空再重建。防止用户上传不匹配的备份文件。

### 券商收益分析
专注分析券商来源交易（招商证券、盈透 IBKR、MOOMOO、汇丰 PULSE），支持按月/按来源/按产品维度统计收益。来源选择偏好存储于 `user_preferences`。

### 前端架构
- Hash 路由: `#/login`, `#/dashboard`, `#/transactions`, `#/import`, `#/rules`, `#/stats`, `#/broker-income-analysis`, `#/data-management`, `#/ai-analysis`
- JWT 存于 localStorage，自动附加到所有 API 请求
- 暗黑模式通过 `data-theme="dark"` 切换，支持系统偏好检测，持久化到 localStorage
- 移动端响应式：小屏幕底部 Tab 栏，桌面侧边栏
- 侧边栏用户悬浮菜单（显示用户名、分类规则入口、修改密码、退出）
- Cache busting: `?v=N` 查询参数
- 无构建工具，Chart.js 从 CDN 加载

## 运行项目

```bash
# 安装依赖
uv sync

# 本地开发
uv run python main.py
# 或
uv run uvicorn main:app --reload

# Docker 部署
docker compose up -d

# 生产环境设置 JWT 密钥
AUTOCOIN_JWT_SECRET=$(openssl rand -hex 32) docker compose up -d

# 运行测试
uv sync --extra dev
uv run pytest tests/ -v
```

## 配置

环境变量前缀 `AUTOCOIN_`：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | SQLite 路径 | `sqlite:///./autocoin.db` |
| `API_PREFIX` | API 路由前缀 | `/api/v1` |
| `FRONTEND_DIR` | 前端静态文件目录 | `./frontend` |
| `DEBUG` | 调试模式 | `false` |
| `JWT_SECRET` | JWT 签名密钥 | 开发用默认值（⚠️ 生产环境务必修改） |
| `CORS_ORIGINS` | CORS 允许的域名列表 | `["*"]` |
| `JWT_EXPIRE_MINUTES` | Token 过期时间（分钟） | 10080（7 天） |
| `LLM_PROVIDER_ORDER` | LLM 提供商优先级列表 | `zhipu,qwen,deepseek,openai,gemini` |
| `LLM_TIMEOUT` | LLM 请求超时（秒） | 60 |
| `OPENAI_API_KEY` / `OPENAI_MODEL` / `OPENAI_BASE_URL` | OpenAI 配置 | gpt-4o-mini |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Gemini 配置 | gemini-2.0-flash |
| `ZHIPU_API_KEY` / `ZHIPU_MODEL` / `ZHIPU_BASE_URL` | 智谱配置 | GLM-4.1V-Thinking-Flash |
| `QWEN_API_KEY` / `QWEN_MODEL` / `QWEN_BASE_URL` | 千问配置 | qwen-vl-max |
| `DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL` / `DEEPSEEK_BASE_URL` | DeepSeek 配置 | deepseek-chat |
| `IMAGE_IMPORT_DAILY_LIMIT` | 每账号每天图片识别上限 | 10 |
