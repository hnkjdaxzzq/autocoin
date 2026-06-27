# 数据管理页面实现记录

## 原始需求提示词

现在需要实现在左侧导航栏新增一个”数据管理“，放在统计之后，整体先复制现有”账单“页面，新需求在此基础上修改。

数据管理页面需求如下：
1、去除手动记账按钮
2、在批量勾选数据出现的工具栏上，将”批量删除“按钮改名为”软删除数据“，在其右侧增加一个”物理删除数据“按钮。
3、”物理删除数据“按钮逻辑同原”批量删除“按钮，但执行操作时，并不是将数据标记，而是将选定的数据条目从数据库中真实删除

实现完该需求后，将需求实现逻辑及本提示词，写成.md文件，放到项目根目录下的VibeCodeing文件夹下，以供后续参考和修改

## 实现逻辑

- 已按后续维护诉求，将数据管理页从账单页拆成独立文件 `frontend/js/data-management.js`，不再通过 `Transactions.render(container, options)` 共享判断实现。
- `frontend/js/transactions.js` 保持账单页专属实现，保留原“手动记账”和“批量删除”等账单页面行为。
- `frontend/js/data-management.js` 以账单页代码为基线复制后独立维护，拥有自己的 `DataManagement` 对象、状态、渲染、筛选、导出、分页、批量改分类和删除逻辑：
  - 页面标题改为“数据管理”
  - 移除“手动记账”按钮和手动录入表单相关 DOM/绑定
  - 批量工具栏中的软删除按钮文案改为“软删除数据”
  - 在软删除按钮右侧显示“物理删除数据”按钮
- 在 `frontend/js/app.js` 中新增 `"/data-management": DataManagement` 路由。
- 在 `frontend/index.html` 左侧导航栏“统计”之后新增“数据管理”入口，引入 `/js/data-management.js`，并 bump 静态资源版本号到 `v=19`。
- 在 `frontend/js/api.js` 中新增 `API.transactions.batchHardDelete(ids)`，调用后端 `/transactions/batch/hard-delete`。
- 在 `autocoin/routers/transactions.py` 中新增 `POST /transactions/batch/hard-delete`，请求体复用 `BatchDeleteRequest`。
- 在 `autocoin/repository/sqlite.py` 中新增 `hard_delete_transaction(id)`，按当前用户和未删除状态查找记录，调用 SQLAlchemy `delete` 后提交事务，实现真实从数据库删除。
- 在 `tests/test_api.py` 中新增批量物理删除接口测试，创建记录后调用接口，并验证这些记录再通过详情接口查询时返回 `404`。
