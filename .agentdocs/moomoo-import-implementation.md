# 导入 MOOMOO 文件实现记录

## 原始提示词

现在需要实现“导入账单”页面中，“导入moomoo文件”按钮的后端，点击该按钮后逻辑等同于该页面“拖拽账单文件到此处”区域的“选择文件”按钮，但要使用新的文件解析方法。具体文件样例参见moomoo2605.pdf。
读取用户上传的文件后，只保留包含期初現金、期末現金、期末已交收現金、期末未交收現金这些内容页中，包含详细现金变化的表格的内容（含日期/時間、類型、金額、備註这几列）。不保留類型为入金、出金、資金調撥的条目、以及日期/時間无有效值的汇总等条目

该文件导入的数据解析规则为：
1、来源（source）统一为“MOOMOO”；
2、条目的日期/時間列按现有导入逻辑格式化后转换到时间（transaction_time）；
3、類型+備註列转换到商品（product）；
4、分类（category和transaction_type）统一为“股息收入”；
5、交易对方（counterparty）、支付方式（payment_method）统一为“MOOMOO”；
6、方向（direction）若“金額”为正，则为income，若“金額”为负，则为expense；
7、日期/時間+生成唯一GUID转换到source_order_id和merchant_order_id
8、類型+金額+该条目所属的货币类型数据写到备注（remark）
9、get方式调用该接口，base参数为当前货币，symbols为目标货币，https://api.frankfurter.dev/v1/latest?base=USD&symbols=CNY，按每条数据的货币类型（如USD、HKD，货币类型CNH等于接口调用参数的CNY，每条数据所属的货币类型在该数据所在表格最后一行汇总列，如USD 總計、HKD 總計、CNH 總計），统一转换成人民币（接口里参数为CNY），取绝对值转换到金额（amount）

实现完该需求后，将需求实现逻辑及本提示词，写成.md文件，放到项目根目录下的VibeCodeing文件夹下，以供后续参考和修改

## 实现逻辑

- 前端“导入moomoo文件”按钮触发隐藏的 `.pdf` 文件选择器，上传后调用 `POST /api/v1/imports/moomoo/preview`。
- 后端新增 `MoomooParser`，使用系统命令 `pdftotext -layout - -` 将 PDF bytes 转为带布局的文本，再扫描 `現金變動` 到 `Cash Sweep總覽` 之间的现金变化表。
- 解析器只识别包含 `日期/時間`、`類型`、`金額`、`備註` 的币种表格。当前货币来自表头中的 `USD`、`HKD`、`CNH`，汇总行如 `USD 總計` 会跳过。
- `期初現金`、`期末現金`、`期末已交收現金`、`期末未交收現金` 作为现金变化表定位信号，不会生成交易。
- `入金`、`出金`、`資金調撥` 类型会过滤；没有有效 `日期/時間` 的行也会过滤。
- `source`、`counterparty`、`payment_method` 均为 `MOOMOO`；`category` 和 `transaction_type` 均为 `股息收入`；`product` 为 `類型 + 備註`。
- 方向根据原始金额正负判断：非负为 `income`，负数为 `expense`；入库金额始终取绝对值，并按汇率转换为人民币。
- 汇率通过 Frankfurter GET 接口查询：`https://api.frankfurter.dev/v1/latest?base=<当前货币>&symbols=CNY`。同一文件内同币种汇率会缓存；`CNH` 按 `CNY` 处理，不请求接口。
- `source_order_id` 和 `merchant_order_id` 使用 `日期/時間 + uuid5` 生成，uuid5 的 seed 来自行号、货币、日期/时间、类型、金额、备注，因此同一文件重复导入时 ID 稳定，文件内相同内容的不同行也能保持唯一。
- `remark` 写入 `類型 金額 貨幣`，例如 `非美國居民預扣稅 -22.38 USD`。
- 预览和确认导入沿用现有文件导入预览流程，确认时仍走 `/imports/confirm`。
