# AI 分析页持久化与自定义 Prompt 实现

## 背景

AI 分析页的 AI 自动分类功能原先只在页面内临时使用分类列表和 DeepSeek API key，Prompt 由后端硬编码生成。现在改为将分类列表、API key、AI Prompt 三项保存到当前登录用户的持久化配置表，并允许用户编辑 Prompt 模板。

## 持久化配置

- 存储表：`user_preferences`
- 存储方式：`SQLiteRepository.get_user_preference` / `set_user_preference`
- 配置 key：`ai_classification.preferences`
- 配置字段：
  - `categories`：页面“使用AI将数据做以下分类”的输入值
  - `api_key`：页面 DeepSeek API key 输入值
  - `prompt_template`：页面 AI Prompt 文本框内容
- 注意：API key 当前按需求以明文 JSON 文本保存到用户偏好表中。

## 后端接口

- `GET /api/v1/ai-classification/preferences`
  - 返回当前用户保存的三项配置。
  - 如果用户没有保存过配置，返回空分类、空 API key、默认 Prompt 模板。
- `PUT /api/v1/ai-classification/preferences`
  - 保存当前用户的三项配置。
- `POST /api/v1/ai-classification/classify`
  - 请求体包含 `api_key`、`categories`、`prompt_template`。
  - 执行前先保存这三项配置，然后通过 SSE 流式返回分类进度和结果。

## Prompt 模板规则

默认 Prompt 模板是中文完整提示词，也是后端执行时发送给 DeepSeek 的真实用户消息模板。模板内使用两个变量占位：

- `{categories}`：执行时替换为用户填写并解析后的分类列表，例如 `餐饮, 交通`。
- `{transactions}`：执行时替换为当前批次交易数据，每行包含 `id`、`current_category`、`counterparty`、`product`，不包含备注。

执行分类时，后端只按用户保存或本次提交的模板做变量替换，不再额外拼接旧版硬编码 Prompt。如果用户删除变量，后端也不会强行补回。

交易方向为“不计”的数据不参与 AI 自动分类。当前数据库内主要存储值为 `neutral`，后端同时兼容过滤 `neutral`、`不计`、`不计收支`。

## 前端交互

- 页面加载后调用偏好接口，回填分类列表、API key 和 AI Prompt。
- AI Prompt 位于 AI 自动分类模块底部，默认折叠。
- 点击 `AI Prompt` 标题可展开或折叠文本框。
- 点击“AI自动分类”时提交当前三项配置，并由后端保存后执行。

## 后续修改注意

- 如果调整默认 Prompt，需同步更新 `DEFAULT_PROMPT_TEMPLATE`，并检查相关测试断言。
- 如果未来不再允许保存 API key，需要同时调整偏好接口、前端回填逻辑和本文档。
- 如果新增模板变量，应在后端 `_render_prompt_template` 中集中处理，并在页面提示文案中同步说明。
