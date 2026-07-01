# 数据管理页全库备份与还原实现记录

## 原始需求提示词

数据管理页面需求如下：
一、备份所有数据
1、导出数据按钮改名为备份所有数据，去除下拉菜单，点击后弹出确认框，确认后直接生成备份数据并让浏览器下载该文件。
2、备份所有数据按钮需要新实现方法，与原导出数据逻辑无关。需要将全数据库的所有表和数据均导出为csv文件，需要重新考虑该csv文件的格式设计，因为且该文件后续还需要能导入回来进行全库还原
3、我看到原数据库有users、transactions、import_batches、classification_rules这几个表，如果还有其他也需要备份

二、导入备份数据
1、备份所有数据按钮左侧增加一个导入备份数据按钮，该按钮操作逻辑为点击后弹出本地文件选择框，选择文件并上传后，执行数据规格检查，如与导出csv规格设计一致，则继续，如上传的还原数据格式有误，则提示数据错误，请检查上传的备份数据。

如文件校验通过，则弹出确认对话框，确认框显示”该操作将清空当前所有数据并还原导入的数据，请谨慎操作，如需继续请输入以下数字：“ + 一个随机生成的5位数字，下方有一个输入框，需要在该确认框内输入该随机5位数字，输入内容与显示的数字相同，点击确认后才能继续执行，否则提示”输入有误，请重新输入“的toast，并刷新随机数字。如输入内容一致，则使用刚才上传的备份文件进行还原操作。还原逻辑为清空当前数据库的所有数据，将文件内的数据分表导入数据库，执行完成后提示数据还原成功。

实现完该需求后，将需求实现逻辑及本提示词，写成.md文件，放到项目根目录下的VibeCodeing文件夹下，以供后续参考和修改

## 实现概览

- 新增后端路由 `autocoin/routers/data_management.py`，并在 `autocoin/app.py` 中挂载到 `/api/v1/data-management`。
- 数据管理页 `frontend/js/data-management.js` 去掉原导出下拉菜单，改为两个按钮：
  - `导入备份数据`
  - `备份所有数据`
- 新增前端 API：
  - `API.dataManagement.exportBackup()`
  - `API.dataManagement.validateBackup(file)`
  - `API.dataManagement.restoreBackup(file)`
- 新增样式用于还原确认框的 5 位数字、输入框和 toast。
- 静态资源版本号从 `v=19` 更新到 `v=20`。
- 新增集成测试覆盖备份导出、备份校验、还原清库和非法备份拒绝。

## 备份 CSV 格式

备份文件是单个 CSV 文件，表头固定为：

```csv
autocoin_backup_version,record_type,table_name,row_number,data_json
```

第一条数据行为元数据：

- `autocoin_backup_version`: 当前为 `1`
- `record_type`: `metadata`
- `table_name`: `__backup__`
- `data_json`: JSON，包含格式名、版本、生成时间、所有表名和列清单

后续每一行为一条数据库记录：

- `record_type`: `row`
- `table_name`: 该记录所属表名
- `row_number`: 该表内序号
- `data_json`: 该行完整字段的 JSON

后端通过 `Base.metadata.sorted_tables` 动态枚举当前模型注册的所有表，因此当前会备份：

- `users`
- `transactions`
- `import_batches`
- `classification_rules`

后续如果新增 SQLAlchemy model 并注册到 `Base.metadata`，也会被纳入备份和格式校验。

## 后端逻辑

### 导出

`GET /api/v1/data-management/backup/export`

- 要求登录。
- 独立于原 `/transactions/export/csv` 和 `/transactions/export/excel`。
- 遍历所有 SQLAlchemy 表。
- 按主键排序读取所有记录。
- 将 `datetime/date` 转为 ISO 字符串。
- 返回 `text/csv; charset=utf-8`，文件名形如 `autocoin_full_backup_YYYYMMDD_HHMMSS.csv`。

### 校验

`POST /api/v1/data-management/backup/validate`

- 接收上传 CSV。
- 校验 CSV 表头必须完全一致。
- 校验版本号、格式名、元数据表结构必须与当前数据库模型一致。
- 校验每条 row 的表名存在、字段集合与当前表列一致。
- 尝试按列类型转换 `DateTime`、`Boolean`、`Integer`、`Float`。
- 校验失败统一返回：`数据错误，请检查上传的备份数据。`

### 还原

`POST /api/v1/data-management/backup/restore`

- 重新执行完整规格校验。
- 在一个事务中清空所有表。
- 如 SQLite 存在 `sqlite_sequence`，同步清理相关表的自增序列。
- 按表重新插入备份中的数据，保留原始主键、用户、密码哈希、导入批次和交易记录。
- 成功返回：`数据还原成功`。

## 前端交互

### 备份所有数据

点击 `备份所有数据` 后显示确认框。确认后直接调用后端导出接口，并触发浏览器下载备份 CSV。

### 导入备份数据

点击 `导入备份数据` 后打开本地文件选择框。选择文件后：

1. 上传到 `/backup/validate` 做格式校验。
2. 校验失败时 toast：`数据错误，请检查上传的备份数据。`
3. 校验通过后显示确认框：
   - 显示“该操作将清空当前所有数据并还原导入的数据，请谨慎操作，如需继续请输入以下数字：”
   - 随机生成 5 位数字
   - 用户必须输入相同数字
4. 输入错误时 toast：`输入有误，请重新输入`，并刷新随机数字。
5. 输入正确后将同一个文件上传到 `/backup/restore` 执行还原。
6. 成功后 toast：`数据还原成功`，并刷新当前数据管理页列表和分类。

## 关键文件

- `autocoin/routers/data_management.py`
- `autocoin/app.py`
- `frontend/js/api.js`
- `frontend/js/data-management.js`
- `frontend/css/styles.css`
- `frontend/index.html`
- `tests/test_api.py`
