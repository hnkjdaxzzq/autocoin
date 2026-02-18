# AutoCoin - 个人记账软件

一款基于 Web 的个人记账与统计分析工具，支持支付宝、微信支付账单导入，提供收支分析、图表可视化和多维度统计功能。

## 功能特性

- **账单导入** — 支持支付宝 CSV（GBK 编码）和微信支付 XLSX 文件，自动去重
- **手动记账** — 可手动录入其他来源的收支记录
- **账单管理** — 分页浏览、筛选（日期/方向/来源）、搜索（对方/商品/备注/支付方式）、分类编辑、删除
- **实时汇总** — 账单页面根据当前筛选条件实时显示总收入、总支出、结余、总笔数
- **数据总览** — Dashboard 展示收支概况、月度柱状图、分类饼图、近期账单
- **统计分析** — 年度汇总卡片（收入/支出/结余）、月度收支趋势图、累计结余、分类占比分析
- **分类钻取** — 统计页面支持展开分类查看明细账单条目
- **可扩展架构** — 抽象 Repository 接口，便于未来对接远程 API

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI |
| 数据库 | SQLite（WAL 模式） |
| ORM | SQLAlchemy 2.0 |
| 数据校验 | Pydantic v2 |
| Excel 解析 | openpyxl |
| 前端 | 原生 HTML/CSS/JS（SPA，Hash 路由） |
| 图表 | Chart.js（CDN） |

## 项目结构

```
autocoin/
├── main.py                  # 应用入口
├── pyproject.toml            # 项目依赖配置
├── autocoin/                 # 后端 Python 包
│   ├── app.py                # FastAPI 应用工厂
│   ├── config.py             # 配置（环境变量 AUTOCOIN_ 前缀）
│   ├── database.py           # 数据库引擎与会话管理
│   ├── models/               # SQLAlchemy ORM 模型
│   │   ├── transaction.py    # 交易记录模型
│   │   └── import_batch.py   # 导入批次模型
│   ├── repository/           # 数据访问层
│   │   ├── base.py           # 抽象接口（DataRepository）
│   │   └── sqlite.py         # SQLite 实现
│   ├── parsers/              # 账单解析器
│   │   ├── base.py           # 解析器抽象基类
│   │   ├── alipay.py         # 支付宝 CSV 解析（GBK）
│   │   └── wechat.py         # 微信支付 XLSX 解析
│   ├── services/             # 业务逻辑层
│   │   ├── import_service.py # 导入服务
│   │   └── stats_service.py  # 统计服务
│   ├── routers/              # API 路由
│   │   ├── transactions.py   # 账单 CRUD
│   │   ├── imports.py        # 文件上传与导入
│   │   └── statistics.py     # 统计查询
│   └── schemas/              # Pydantic 请求/响应模型
│       ├── transaction.py
│       ├── import_schema.py
│       └── statistics.py
├── frontend/                 # 前端静态文件
│   ├── index.html            # SPA 入口
│   ├── css/styles.css        # 样式
│   └── js/
│       ├── api.js            # API 客户端
│       ├── app.js            # 路由与页面切换
│       ├── charts.js         # Chart.js 封装与工具函数
│       ├── dashboard.js      # 总览页
│       ├── transactions.js   # 账单页
│       ├── import.js         # 导入页
│       └── stats.js          # 统计页
└── data/                     # 示例账单文件目录
```

## 快速开始

### 环境要求

- Python >= 3.9
- [uv](https://docs.astral.sh/uv/) 包管理器（推荐）

### 安装与运行

```bash
# 克隆项目
git clone <repo-url>
cd autocoin

# 安装依赖
uv sync

# 启动服务（默认 http://localhost:8000）
uv run python main.py
```

浏览器打开 `http://localhost:8000` 即可使用。

### 环境变量

可通过环境变量覆盖默认配置（前缀 `AUTOCOIN_`）：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `AUTOCOIN_DATABASE_URL` | 数据库连接 | `sqlite:///autocoin.db` |

## API 概览

所有接口前缀为 `/api/v1`。

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/transactions` | 分页查询账单（支持筛选、搜索，返回汇总统计） |
| `POST` | `/transactions` | 手动创建账单 |
| `GET` | `/transactions/{id}` | 获取单条账单 |
| `PUT` | `/transactions/{id}` | 更新账单（分类/备注/方向） |
| `DELETE` | `/transactions/{id}` | 软删除账单 |
| `POST` | `/imports` | 上传并导入账单文件 |
| `GET` | `/imports` | 查看导入历史 |
| `GET` | `/imports/{id}` | 查看单次导入详情 |
| `GET` | `/statistics/summary` | 收支汇总 |
| `GET` | `/statistics/monthly` | 月度统计 |
| `GET` | `/statistics/category` | 分类统计 |
| `GET` | `/statistics/daily` | 每日统计 |

## 支持的账单格式

### 支付宝

- 格式：CSV 文件（GBK 编码）
- 来源：支付宝 App -> 账单 -> 导出

### 微信支付

- 格式：XLSX 文件
- 来源：微信 -> 支付 -> 钱包 -> 账单 -> 导出

导入时自动检测文件类型，支持批量拖拽上传，重复记录自动跳过。

## License

MIT
