# 分类规则页新增别名规则实现说明

## 原始需求提示词

一、规则页面增加2个tab，默认tab名为“分类规则”，功能及前端效果同现有分类规则页面
二、tab2名为“别名规则”，先复制现有分类规则页面的功能，然后对该tab下的页面和功能做如下修改，但不要影响原有分类规则页面的功能和逻辑：
1、修改”自动分类 *“为”映射别名 *“，修改”立即重新分类“按钮为”立即修改映射别名“
2、别名规则tab下创建的规则，不存在原来的数据中，而是要新建一个表保存
3、在原transactions表中新创建一列product_alias
4、别名规则功能逻辑在原有逻辑的基础上调整，但不要影响原来分类规则的逻辑，要新建一个方法，新方法执行逻辑类似原来分类规则页面，但是不再修改原有字段，而是将匹配到的数据取”映射别名 *“中的内容，修改到product_alias字段
5、在券商收入分析页面的数据详表增加一列“别名”，在商品列之后，数据读取自product_alias字段
6、数据导入以及点击”立即修改映射别名“按钮时，执行别名规则进行修改

实现完该需求后，将需求实现逻辑及本提示词，写成.md文件，放到项目根目录下的VibeCodeing文件夹下，以供后续参考和修改

## 实现逻辑

- 前端 `frontend/js/rules.js` 改为两个 tab：默认“分类规则”仍使用原 `API.rules`，新增“别名规则”使用 `API.aliasRules`。
- 分类规则 tab 保持原有 `category` 和 `remark` 行为；别名规则 tab 使用独立字段 `product_alias`，页面文案显示“映射别名 *”和“立即修改映射别名”。
- 新增模型 `autocoin/models/alias_rule.py`，独立保存别名规则到 `alias_rules` 表，不复用 `classification_rules`。
- `transactions` 模型新增 `product_alias` 列；`autocoin/database.py` 在启动初始化时为旧库执行轻量迁移，自动补充该列和索引。
- 新增 `autocoin/schemas/alias_rule.py` 和 `/api/v1/rules/aliases` 系列接口，支持别名规则的增删改查与 `/api/v1/rules/aliases/realias` 立即执行。
- `SQLiteRepository` 新增 `_apply_alias_rules()` 和 `realias_all_transactions()`：匹配逻辑与分类规则一致，按优先级命中第一条后停止，但只写入 `product_alias`。
- 手动创建和批量导入交易时，先执行原分类规则，再执行别名规则；不会改变原分类规则逻辑。
- 券商收入分析页面 `frontend/js/broker-income-analysis.js` 在“商品”列之后新增“别名”列，读取交易数据中的 `product_alias`。
