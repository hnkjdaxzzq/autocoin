# 导入汇丰 PULSE 信用卡文件实现记录

## 原始提示词

现在需要实现“导入账单”页面中，“导入汇丰PULSE信用卡文件”按钮的后端，点击该按钮后逻辑等同于该页面“拖拽账单文件到此处”区域的“选择文件”按钮，但要使用新的文件解析方法。具体文件样例参见eStatementFile_6月.pdf。
读取用户上传的文件后，只保留完整包含Post date、Trans date、Description of transaction和Amount的条目，其他汇总及说明内容不需要。

该文件导入的数据解析规则为：
1、来源（source）统一为“汇丰PULSE”；
2、条目的Trans date按现有导入逻辑格式化后转换到时间（transaction_time）；
3、Description of transaction列转换到商品（product），若该条目“Amount”的数字后有CR，则再加上”退款“字符；
4、分类（category和transaction_type）统一为“PULSE交易”；
5、交易对方（counterparty）为“PULSE“、支付方式（payment_method）为“Pulse双币卡”；
6、方向（direction）若“Amount”只有数字，为expense，则为，若“Amount”的数字后还有CR，则为income；
7、Trans date+生成唯一GUID转换到source_order_id和merchant_order_id
8、记账日期+Post date 放到备注（remark），若该条目“Amount”的数字后有CR，则在加上”退款“二字
9、Amount列（去除CR字符）转换到金额（amount）

实现完该需求后，将需求实现逻辑及本提示词，写成.md文件，放到项目根目录下的VibeCodeing文件夹下，以供后续参考和修改

## 实现逻辑

- 前端“导入汇丰PULSE信用卡文件”按钮触发隐藏的 `.pdf` 文件选择器，上传后调用 `POST /api/v1/imports/hsbc-pulse/preview`。
- 后端新增 `HsbcPulseParser`，使用系统命令 `pdftotext -layout - -` 将 PDF bytes 转为带布局的文本。
- 解析器只保留匹配 `Post date + Trans date + Description of transaction + Amount` 的完整交易行；`PREVIOUS BALANCE`、`STATEMENT BALANCE`、奖励积分、费用、还款说明等汇总/说明段不会生成交易。
- 交易行后的 `APPLE PAY-MOBILE:xxxx`、`UNIONPAY QR` 等大写续行会合并到 `Description of transaction`，作为商品描述的一部分。
- 年份来自账单中的 `Statement Date`。`Trans date` 和 `Post date` 只有日月时，默认使用账单年份；如果交易月份大于账单月份，则按上一年处理，用于跨年账单。
- `source` 为 `汇丰PULSE`；`counterparty` 为 `PULSE`；`payment_method` 为 `Pulse双币卡`；`category` 和 `transaction_type` 均为 `PULSE交易`。
- `Amount` 带 `CR` 时视为退款：`direction=income`，`product` 末尾追加 `退款`，`remark` 末尾追加 `退款`；否则 `direction=expense`。
- `amount` 为去除 `CR` 和千分位后的数字。
- `source_order_id` 和 `merchant_order_id` 使用 `Trans date + uuid5` 生成，uuid5 的 seed 来自行号、Post date、Trans date、描述和金额，因此同一文件重复导入时 ID 稳定。
- `remark` 写入 `记账日期 YYYY-MM-DD`，退款行写入 `记账日期 YYYY-MM-DD 退款`。
- 预览和确认导入沿用现有文件导入预览流程，确认时仍走 `/imports/confirm`。
