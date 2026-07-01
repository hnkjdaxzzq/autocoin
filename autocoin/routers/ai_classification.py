import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from autocoin.auth import get_current_user
from autocoin.database import get_db
from autocoin.models.user import User
from autocoin.repository.sqlite import SQLiteRepository

logger = logging.getLogger("autocoin")

router = APIRouter(prefix="/ai-classification", tags=["ai-classification"])

BATCH_SIZE = 100
MAX_WORKERS = 5
MAX_RETRIES = 3
RETRY_DELAY = 2
PREF_KEY_AI_CLASSIFICATION = "ai_classification.preferences"

DEFAULT_PROMPT_TEMPLATE = """你是一个严格的记账交易分类助手。用户指定的全部可用分类如下，左侧是分类编号，右侧是分类名称：

分类编号：
{category_map}

你的任务：把每一条交易都归类到上述分类编号中的某一个编号。你必须严格只使用列表中的编号，不允许输出列表外的编号、分类名称、同义词、近义词、变体或额外解释。

重要规则：
- 如果交易当前分类和某个用户分类接近但不完全一致，请映射到最接近的分类编号。
- 示例：分类包含 1=餐饮，2=交通，current_category = "餐饮美食" → 必须输出编号 1。
- 示例：分类包含 1=餐饮，2=交通，current_category = "打车" → 必须输出编号 2。
- 示例：分类包含 1=购物，2=交通，current_category = "餐饮" → 必须选择最接近的一项，例如编号 1。
- 永远不要输出分类编号列表之外的任何编号。
- 每一条交易都必须给出一个分类编号，不能跳过。

待分类交易如下，每行格式为：id|当前分类|交易对方|商品说明
{transactions}

请只返回合法 JSON 对象，格式必须为：{"t":[[id,分类编号]]}
不要返回 Markdown，不要返回代码块，不要返回任何额外文字。"""

DEFAULT_AI_CLASSIFICATION_PREFERENCES = {
    "categories": "",
    "api_key": "",
    "prompt_template": DEFAULT_PROMPT_TEMPLATE,
    "only_expense": True,
}


class ClassifyRequest(BaseModel):
    api_key: str
    categories: str  # comma-separated, e.g. "美食,交通,旅游"
    prompt_template: str = DEFAULT_PROMPT_TEMPLATE
    only_expense: bool = True


class ClassifyResponse(BaseModel):
    total: int
    classified: int
    results: list[dict]


class AIClassificationPreferences(BaseModel):
    categories: str = ""
    api_key: str = ""
    prompt_template: str = DEFAULT_PROMPT_TEMPLATE
    only_expense: bool = True
    default_prompt_template: str = DEFAULT_PROMPT_TEMPLATE


class ConfirmRequest(BaseModel):
    results: list[dict]  # [{id, category}]


class ConfirmResponse(BaseModel):
    updated: int
    total: int


def get_repo(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SQLiteRepository:
    return SQLiteRepository(db, user.id)


def _normalize_preferences(value) -> AIClassificationPreferences:
    if not isinstance(value, dict):
        value = {}
    return AIClassificationPreferences(
        categories=value.get("categories") or "",
        api_key=value.get("api_key") or "",
        prompt_template=value.get("prompt_template") or DEFAULT_PROMPT_TEMPLATE,
        only_expense=value.get("only_expense", True) is not False,
        default_prompt_template=DEFAULT_PROMPT_TEMPLATE,
    )


def _preference_payload(body: AIClassificationPreferences) -> dict:
    return {
        "categories": body.categories,
        "api_key": body.api_key,
        "prompt_template": body.prompt_template or DEFAULT_PROMPT_TEMPLATE,
        "only_expense": body.only_expense,
    }


def _build_category_map(categories: list[str]) -> dict[int, str]:
    return {i + 1: category for i, category in enumerate(categories)}


def _build_category_map_prompt(categories: list[str]) -> str:
    return "\n".join(
        f"{idx}={category}"
        for idx, category in _build_category_map(categories).items()
    )


def _clean_prompt_field(value) -> str:
    return str(value or "").replace("|", " ").replace("\n", " ").strip()


def _build_transaction_prompt_lines(transactions: list[dict]) -> str:
    lines = []
    for tx in transactions:
        old_cat = _clean_prompt_field(tx.get("category"))
        counterparty = _clean_prompt_field(tx.get("counterparty"))
        product = _clean_prompt_field(tx.get("product"))
        lines.append(f'{tx["id"]}|{old_cat}|{counterparty}|{product}')
    return "\n".join(lines)


def _filter_classifiable_transactions(
    transactions: list[dict],
    only_expense: bool = True,
) -> list[dict]:
    """Exclude transactions that should not participate in AI classification."""
    neutral_values = {"neutral", "不计", "不计收支"}
    if only_expense:
        return [
            tx for tx in transactions
            if (tx.get("direction") or "").strip() == "expense"
        ]
    return [
        tx for tx in transactions
        if (tx.get("direction") or "").strip() not in neutral_values
    ]


def _render_prompt_template(
    prompt_template: str,
    transactions: list[dict],
    categories: list[str],
) -> str:
    """Render the user-configured prompt template for a transaction batch."""
    template = prompt_template or DEFAULT_PROMPT_TEMPLATE
    return (
        template
        .replace("{categories}", ", ".join(categories))
        .replace("{category_map}", _build_category_map_prompt(categories))
        .replace("{transactions}", _build_transaction_prompt_lines(transactions))
    )


def _find_transactions_result(parsed):
    if isinstance(parsed, dict):
        for key in ("t", "transactions", "results", "data", "classifications"):
            if key in parsed and isinstance(parsed[key], list):
                return parsed[key]
    if isinstance(parsed, list):
        return parsed
    return None


def _normalize_ai_result_item(item, category_map: dict[int, str]) -> tuple:
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        tid = item[0]
        category_value = item[1]
    elif isinstance(item, dict):
        tid = item.get("id")
        category_value = item.get("category")
        if category_value is None:
            category_value = item.get("category_id")
        if category_value is None:
            category_value = item.get("c")
    else:
        return None, ""

    try:
        tid = int(tid)
    except (TypeError, ValueError):
        return None, ""

    if isinstance(category_value, int):
        return tid, category_map.get(category_value, "")
    if isinstance(category_value, str):
        cat = category_value.strip()
        if cat.isdigit():
            return tid, category_map.get(int(cat), "")
        return tid, cat
    return None, ""


@router.get("/preferences", response_model=AIClassificationPreferences)
def get_ai_classification_preferences(repo: SQLiteRepository = Depends(get_repo)):
    prefs = repo.get_user_preference(
        PREF_KEY_AI_CLASSIFICATION,
        DEFAULT_AI_CLASSIFICATION_PREFERENCES,
    )
    return _normalize_preferences(prefs)


@router.put("/preferences", response_model=AIClassificationPreferences)
def update_ai_classification_preferences(
    body: AIClassificationPreferences,
    repo: SQLiteRepository = Depends(get_repo),
):
    normalized = _normalize_preferences(_preference_payload(body))
    repo.set_user_preference(PREF_KEY_AI_CLASSIFICATION, normalized.model_dump())
    return normalized


def _classify_batch(
    api_key: str,
    transactions: list[dict],
    categories: list[str],
    prompt_template: str,
) -> list[dict]:
    """Send one batch of transactions to DeepSeek for classification."""
    prompt = _render_prompt_template(prompt_template, transactions, categories)
    category_map = _build_category_map(categories)

    for attempt in range(MAX_RETRIES):
        try:
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com",
                timeout=60.0,           # total timeout 60s per request
                max_retries=0,           # we handle retries ourselves
            )
            response = client.chat.completions.create(
                model="deepseek-v4-flash",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise transaction classifier. Always respond with valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=4096,
            )
            content = response.choices[0].message.content.strip()
            parsed = json.loads(content)

            transactions_result = _find_transactions_result(parsed)

            if transactions_result is None:
                logger.warning("Could not find transaction list in response: %s", content[:300])
                raise ValueError("Unexpected response format")

            # Validate and map results
            tx_map = {tx["id"]: tx for tx in transactions}
            validated = []
            for item in transactions_result:
                tid, cat = _normalize_ai_result_item(item, category_map)
                if tid and cat and tid in tx_map:
                    validated.append({
                        "id": tid,
                        "old_category": tx_map[tid].get("category") or "",
                        "new_category": cat,
                        "counterparty": tx_map[tid].get("counterparty") or "",
                        "product": tx_map[tid].get("product") or "",
                        "transaction_time": tx_map[tid].get("transaction_time") or "",
                    })
                    del tx_map[tid]  # remove from pending

            # Fill in any records DeepSeek missed with original category
            for tid, tx in tx_map.items():
                validated.append({
                    "id": tid,
                    "old_category": tx.get("category") or "",
                    "new_category": tx.get("category") or "",
                    "counterparty": tx.get("counterparty") or "",
                    "product": tx.get("product") or "",
                    "transaction_time": tx.get("transaction_time") or "",
                })
            return validated

        except Exception as e:
            logger.warning(
                "Batch classify attempt %d/%d failed: %s",
                attempt + 1, MAX_RETRIES, e,
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                logger.error("All retries exhausted for a batch")
                raise

    return []


def _sse_event(event: str, data: object) -> str:
    """Format an SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _classify_stream(
    api_key: str,
    categories: list[str],
    prompt_template: str,
    only_expense: bool,
    repo: SQLiteRepository,
):
    """Generator that yields SSE progress events and a final complete event."""
    # Phase 1: reading
    yield _sse_event("progress", {
        "phase": "reading",
        "message": "正在读取数据库中的交易数据...",
    })

    all_tx, _ = repo.list_transactions(page=1, page_size=1000000)
    all_tx = _filter_classifiable_transactions(all_tx, only_expense=only_expense)
    total = len(all_tx)
    if not all_tx:
        yield _sse_event("complete", {
            "total": 0,
            "classified": 0,
            "results": [],
        })
        return

    # Phase 2: preparing
    batches = [
        all_tx[i : i + BATCH_SIZE] for i in range(0, len(all_tx), BATCH_SIZE)
    ]
    total_batches = len(batches)
    logger.info("Classifying %d transactions in %d batches", total, total_batches)

    yield _sse_event("progress", {
        "phase": "preparing",
        "total": total,
        "total_batches": total_batches,
        "message": f"共 {total} 条数据，分为 {total_batches} 批处理",
    })

    # Phase 3: classifying
    all_results = []
    CLASSIFY_TIMEOUT = 600
    completed = 0
    failed_batches = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {
            executor.submit(
                _classify_batch,
                api_key,
                batch,
                categories,
                prompt_template,
            ): batch
            for batch in batches
        }
        try:
            for future in as_completed(future_map, timeout=CLASSIFY_TIMEOUT):
                completed += 1
                try:
                    batch_results = future.result()
                    all_results.extend(batch_results)
                except Exception as e:
                    failed_batches += 1
                    logger.error("Batch %d/%d failed: %s", completed, total_batches, e)
                    failed_batch = future_map[future]
                    for tx in failed_batch:
                        all_results.append({
                            "id": tx["id"],
                            "old_category": tx.get("category") or "",
                            "new_category": tx.get("category") or "",
                            "counterparty": tx.get("counterparty") or "",
                            "product": tx.get("product") or "",
                            "transaction_time": tx.get("transaction_time") or "",
                        })

                yield _sse_event("progress", {
                    "phase": "classifying",
                    "total": total,
                    "total_batches": total_batches,
                    "completed_batches": completed,
                    "classified_so_far": len(all_results),
                    "failed_batches": failed_batches,
                    "message": f"正在分类... 已完成 {completed}/{total_batches} 批，已处理 {len(all_results)}/{total} 条",
                })

        except TimeoutError:
            logger.error("Classification timed out after %d seconds", CLASSIFY_TIMEOUT)
            for f in future_map:
                f.cancel()
            for future in list(future_map.keys()):
                if future.done():
                    try:
                        all_results.extend(future.result())
                    except Exception:
                        pass
            yield _sse_event("progress", {
                "phase": "timeout",
                "total": total,
                "classified_so_far": len(all_results),
                "message": f"处理超时，已部分完成 {len(all_results)}/{total} 条",
            })

    # Phase 4: complete
    changed_count = sum(1 for r in all_results if r["old_category"] != r["new_category"])
    logger.info("Classification done: %d/%d classified, %d changed", len(all_results), total, changed_count)

    yield _sse_event("complete", {
        "total": total,
        "classified": len(all_results),
        "changed": changed_count,
        "results": all_results,
    })


@router.post("/classify")
def classify_transactions(
    body: ClassifyRequest,
    repo: SQLiteRepository = Depends(get_repo),
    _: User = Depends(get_current_user),
):
    """Use DeepSeek API to classify all transactions. Returns SSE stream."""
    categories = [c.strip() for c in body.categories.split(",") if c.strip()]
    if not categories:
        raise HTTPException(status_code=422, detail="请至少填写一个分类")

    prompt_template = body.prompt_template or DEFAULT_PROMPT_TEMPLATE
    repo.set_user_preference(PREF_KEY_AI_CLASSIFICATION, {
        "categories": body.categories,
        "api_key": body.api_key,
        "prompt_template": prompt_template,
        "only_expense": body.only_expense,
    })

    return StreamingResponse(
        _classify_stream(
            body.api_key,
            categories,
            prompt_template,
            body.only_expense,
            repo,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/confirm", response_model=ConfirmResponse)
def confirm_classification(
    body: ConfirmRequest,
    repo: SQLiteRepository = Depends(get_repo),
    _: User = Depends(get_current_user),
):
    """Write AI classification results to the database."""
    updated = 0
    for item in body.results:
        tid = item.get("id")
        category = item.get("category", "")
        if tid and category:
            try:
                result = repo.update_transaction(tid, {"category": category})
                if result:
                    updated += 1
            except Exception as e:
                logger.warning("Failed to update transaction %d: %s", tid, e)

    return ConfirmResponse(updated=updated, total=len(body.results))
