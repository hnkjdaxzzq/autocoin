# 导入盈透 IBKR 文件实现记录

## 原始提示词

现在需要实现“导入账单”页面中，“导入盈透文件”按钮的后端，点击该按钮后逻辑等同于该页面“拖拽账单文件到此处”区域的“选择文件”按钮，但要使用新的文件解析方法。具体文件样例参见IBKR1-5.csv。
读取用户上传的文件后，只保留行首为“股息”、“代扣税”、“利息”的相关条目。
该文件导入的数据解析规则为：
0、第二列为header的条目不解析为数据条目
1、来源（source）统一为“盈透IBKR”；
2、条目的支付日期列按现有导入逻辑格式化后转换到时间（transaction_time）；
3、描述列转换到商品（product）；
4、分类（category和transaction_type）统一为“股息收入”；
5、交易对方（counterparty）、支付方式（payment_method）统一为“盈透IBKR”；
6、方向（direction）若“金额”为正，则为income，若“金额”为负，则为expense；
7、日期+生成唯一GUID转换到source_order_id和merchant_order_id
8、数据条目第一列（如股息、代扣税、利息）+ 货币列+金额列数据写到备注（remark）
9、get方式调用该接口，base参数为当前货币，symbols为目标货币，https://api.frankfurter.dev/v1/latest?base=USD&symbols=CNY，按每条数据货币列标注的货币类型（如USD、HKD，货币类型CNH等于接口调用参数的CNY），统一转换成人民币（接口里参数为CNY），取绝对值转换到金额（amount）

实现完该需求后，将需求实现逻辑及本提示词，写成.md文件，放到项目根目录下的VibeCodeing文件夹下，以供后续参考和修改

## 实现逻辑

- 前端“导入盈透文件”按钮触发隐藏的 `.csv` 文件选择器，上传后调用 `POST /api/v1/imports/ibkr/preview`。
- 后端新增 `IbkrParser`，只处理第一列为 `股息`、`代扣税`、`利息` 的 CSV 行；第二列为 `Header` 的行只用于记录当前分段字段名，不生成交易。
- `Data` 行按当前分段 header 读取 `货币`、`日期`、`描述`、`金额`。`货币` 为空或以 `总数` 开头的汇总行会跳过。
- `source`、`counterparty`、`payment_method` 均为 `盈透IBKR`；`category` 和 `transaction_type` 均为 `股息收入`；`product` 来自 `描述`。
- 方向根据原始金额正负判断：非负为 `income`，负数为 `expense`；入库金额始终取绝对值，并按汇率转换为人民币。
- 汇率通过 Frankfurter GET 接口查询：`https://api.frankfurter.dev/v1/latest?base=<当前货币>&symbols=CNY`。同一文件内同币种汇率会缓存；`CNH` 按 `CNY` 处理，不请求接口。
- `source_order_id` 和 `merchant_order_id` 使用 `日期 + uuid5` 生成，uuid5 的 seed 来自行号、分段、货币、日期、描述、金额，因此同一行重复导入时 ID 稳定，文件内相同内容的不同行也能保持唯一。
- `remark` 写入 `第一列 货币 金额`，例如 `代扣税 USD -15.9`。
- 预览和确认导入沿用现有文件导入预览流程，确认时仍走 `/imports/confirm`。
