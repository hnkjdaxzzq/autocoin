# AI 分析页持久化与自定义 Prompt 实现

## 背景

AI 分析页的 AI 自动分类功能原先只在页面内临时使用分类列表和 DeepSeek API key，Prompt 由后端硬编码生成。现在改为将分类列表、API key、AI Prompt 和支出筛选开关保存到当前登录用户的持久化配置表，并允许用户编辑 Prompt 模板。

## 持久化配置

- 存储表：`user_preferences`
- 存储方式：`SQLiteRepository.get_user_preference` / `set_user_preference`
- 配置 key：`ai_classification.preferences`
- 配置字段：
  - `categories`：页面“使用AI将数据做以下分类”的输入值
  - `api_key`：页面 DeepSeek API key 输入值
  - `prompt_template`：页面 AI Prompt 文本框内容
  - `only_expense`：是否仅分类支出数据，默认 `true`
- 注意：API key 当前按需求以明文 JSON 文本保存到用户偏好表中。

## 后端接口

- `GET /api/v1/ai-classification/preferences`
  - 返回当前用户保存的配置。
  - 如果用户没有保存过配置，返回空分类、空 API key、默认 Prompt 模板、默认仅分类支出数据。
  - 响应额外包含 `default_prompt_template`，供前端“重置为默认Prompt”使用。
- `PUT /api/v1/ai-classification/preferences`
  - 保存当前用户的三项配置。
- `POST /api/v1/ai-classification/classify`
  - 请求体包含 `api_key`、`categories`、`prompt_template`、`only_expense`、`limit`。
  - 执行前先保存这些配置，然后通过 SSE 流式返回分类进度和结果。
  - `limit` 是一次性运行参数，默认 `0` 表示不限制；大于 `0` 时只处理筛选后的前 N 条交易，不保存到用户偏好。

## Prompt 模板规则

默认 Prompt 模板是中文完整提示词，也是后端执行时发送给 DeepSeek 的真实用户消息模板。它保留完整分类规则和示例，仅将接口协议部分做 token 压缩：分类使用编号，交易使用管道分隔行，返回结果使用紧凑数组。

- `{category_map}`：执行时替换为分类编号映射，例如 `1=餐饮`。
- `{transactions}`：执行时替换为当前批次交易数据，每行格式为 `id|当前分类|交易对方|商品说明`，不包含备注。
- `{categories}`：可选变量，替换为逗号分隔分类列表；默认 Prompt 不使用它。

默认要求 DeepSeek 返回紧凑 JSON：`{"t":[[id,分类编号]]}`。后端只支持该协议，不兼容旧格式 `transactions`、`results`、`data`、`classifications`，也不接受 `{"id": 1, "category": "餐饮"}` 或字符串分类。若 AI 返回 `PULSE交易`、原分类、整段分类列表等越界值，或漏返交易，后端会判定该批无效并进入重试/失败流程。

执行分类时，后端只按用户保存或本次提交的模板做变量替换，不再额外拼接旧版硬编码 Prompt。如果用户删除变量，后端也不会强行补回。

默认只处理交易方向为支出的数据。若用户取消勾选“仅分类支出数据”，则处理所有非“不计”数据；当前数据库内“不计”主要存储值为 `neutral`，后端同时兼容过滤 `neutral`、`不计`、`不计收支`。

## 前端交互

- 页面加载后调用偏好接口，回填分类列表、API key、AI Prompt 和“仅分类支出数据”复选框。
- “仅分类支出数据”复选框位于分类按钮上方，默认勾选。
- AI Prompt 位于 AI 自动分类模块底部，默认展开。
- 点击 `AI Prompt` 标题可展开或折叠文本框。
- AI Prompt 文本框下方有“重置为默认Prompt”按钮，点击后将文本框内容恢复为后端返回的 `default_prompt_template`。
- “重置为默认Prompt”右侧有“本次最多处理”数字输入框，默认 `0` 表示不限制；该值只影响当次分类请求，不会持久化。
- 点击“AI自动分类”时提交当前配置，并由后端保存后执行。
- 分类进度中如果有批次失败，后端会通过 SSE 返回最近失败详情，前端展示批次号、该批条数和错误摘要。错误摘要会截断并对常见密钥片段做脱敏。

## 后续修改注意

- 如果调整默认 Prompt，需同步更新 `DEFAULT_PROMPT_TEMPLATE`，并检查相关测试断言。
- 如果未来不再允许保存 API key，需要同时调整偏好接口、前端回填逻辑和本文档。
- 如果新增模板变量，应在后端 `_render_prompt_template` 中集中处理，并在页面提示文案中同步说明。
