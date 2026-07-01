import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
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

BATCH_SIZE = 50
MAX_WORKERS = 5
MAX_RETRIES = 3
MAX_SPLIT_RETRIES = 3
RETRY_DELAY = 2
DEEPSEEK_MAX_TOKENS = 8192
PREF_KEY_AI_CLASSIFICATION = "ai_classification.preferences"
DEFAULT_CATEGORIES = "餐饮美食，交通出行，汽车，母婴儿童，娱乐，购物，生活缴费，社保费用，医疗，旅游，其他"

DEFAULT_PROMPT_TEMPLATE = """你是一个严格的记账交易分类助手。用户指定的全部可用分类如下，左侧是分类编号，右侧是分类名称：

分类编号：
{category_map}

任务：把每一条交易都归类到上述分类编号中的某一个编号。你必须严格只使用列表中的编号，不允许输出列表外的编号。

重要规则：
- 如果交易当前分类和某个用户分类接近但不完全一致，请映射到最接近的分类编号。
- 永远不要输出分类编号列表之外的任何编号。
- 每一条交易都必须给出一个分类编号，不能跳过。

待分类交易如下，每行格式为：id|当前分类|交易对方|商品说明
{transactions}

请只返回合法 JSON 对象，格式必须为：{"t":[[id,分类编号]]}
不要返回 Markdown，不要返回代码块，不要返回任何额外文字。"""

DEFAULT_AI_CLASSIFICATION_PREFERENCES = {
    "categories": DEFAULT_CATEGORIES,
    "api_key": "",
    "prompt_template": DEFAULT_PROMPT_TEMPLATE,
    "only_expense": True,
}


class ClassifyRequest(BaseModel):
    api_key: str
    categories: str  # comma-separated, e.g. "美食,交通,旅游"
    prompt_template: str = DEFAULT_PROMPT_TEMPLATE
    only_expense: bool = True
    only_unclassified: bool = True
    limit: int = 0
    debug: bool = False
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ClassifyResponse(BaseModel):
    total: int
    classified: int
    results: list[dict]


class AIClassificationPreferences(BaseModel):
    categories: str = DEFAULT_CATEGORIES
    api_key: str = ""
    prompt_template: str = DEFAULT_PROMPT_TEMPLATE
    only_expense: bool = True
    default_prompt_template: str = DEFAULT_PROMPT_TEMPLATE


class ConfirmRequest(BaseModel):
    results: list[dict]  # [{id, category}]


class ConfirmResponse(BaseModel):
    updated: int
    total: int


class AIClassificationBatchError(Exception):
    def __init__(
        self,
        message: str,
        prompt: str = "",
        raw_response: str = "",
        response_debug: str = "",
        request_debug: str = "",
        splittable: bool = False,
        split_depth: int = 0,
    ):
        super().__init__(message)
        self.prompt = prompt
        self.raw_response = raw_response
        self.response_debug = response_debug
        self.request_debug = request_debug
        self.splittable = splittable
        self.split_depth = split_depth


def get_repo(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SQLiteRepository:
    return SQLiteRepository(db, user.id)


def _normalize_preferences(value) -> AIClassificationPreferences:
    if not isinstance(value, dict):
        value = {}
    return AIClassificationPreferences(
        categories=value.get("categories") or DEFAULT_CATEGORIES,
        api_key=value.get("api_key") or "",
        prompt_template=value.get("prompt_template") or DEFAULT_PROMPT_TEMPLATE,
        only_expense=True,
        default_prompt_template=DEFAULT_PROMPT_TEMPLATE,
    )


def _preference_payload(body: AIClassificationPreferences) -> dict:
    return {
        "categories": body.categories,
        "api_key": body.api_key,
        "prompt_template": body.prompt_template or DEFAULT_PROMPT_TEMPLATE,
    }


def _parse_categories(categories: str) -> list[str]:
    return [
        c.strip()
        for c in re.split(r"[,，]", categories or "")
        if c.strip()
    ]


def _build_category_map(categories: list[str]) -> dict[int, str]:
    return {i + 1: category for i, category in enumerate(categories)}


def _build_category_map_prompt(categories: list[str]) -> str:
    return "\n".join(
        f"{idx}={category}"
        for idx, category in _build_category_map(categories).items()
    )


def _clean_prompt_field(value) -> str:
    return str(value or "").replace("|", " ").replace("\n", " ").strip()


def _transaction_line(tx: dict) -> str:
    old_cat = _clean_prompt_field(tx.get("category"))
    counterparty = _clean_prompt_field(tx.get("counterparty"))
    product = _clean_prompt_field(tx.get("product"))
    return f'{tx["id"]}|{old_cat}|{counterparty}|{product}'


def _build_transaction_prompt_lines(transactions: list[dict]) -> str:
    return "\n".join(_transaction_line(tx) for tx in transactions)


def _filter_classifiable_transactions(
    transactions: list[dict],
    only_expense: bool = True,
    only_unclassified: bool = True,
) -> list[dict]:
    """Exclude transactions that should not participate in AI classification."""
    neutral_values = {"neutral", "不计", "不计收支"}
    if only_expense:
        filtered = [
            tx for tx in transactions
            if (tx.get("direction") or "").strip() == "expense"
        ]
    else:
        filtered = [
            tx for tx in transactions
            if (tx.get("direction") or "").strip() not in neutral_values
        ]
    if only_unclassified:
        filtered = [
            tx for tx in filtered
            if int(tx.get("is_ai_classified") or 0) != 1
        ]
    return filtered


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
        result = parsed.get("t")
        if isinstance(result, list):
            return result
    return None


def _normalize_ai_result_item(item, category_map: dict[int, str]) -> tuple:
    if not isinstance(item, (list, tuple)) or len(item) < 2:
        return None, ""
    tid = item[0]
    category_value = item[1]

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
    return None, ""


def _summarize_error(error: Exception) -> str:
    raw = str(error).strip() or error.__class__.__name__
    text = " ".join(raw.split())
    if len(text) > 1000:
        text = text[:997] + "..."
    return text


def _content_preview(content: str) -> str:
    text = " ".join((content or "").split())
    if not text:
        return "<empty>"
    if len(text) > 1000:
        text = text[:997] + "..."
    return text


def _debug_preview(content: str) -> str:
    text = content or ""
    if len(text) > 4000:
        text = text[:3997] + "..."
    return text


def _response_debug_preview(response) -> str:
    """Summarize DeepSeek response metadata for debugging empty/invalid content."""
    if response is None:
        return ""
    choices = []
    for choice in getattr(response, "choices", []) or []:
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None) if message else None
        if hasattr(message, "model_dump"):
            message_keys = sorted(message.model_dump(exclude_none=True).keys())
        else:
            message_keys = []
        choices.append({
            "index": getattr(choice, "index", None),
            "finish_reason": getattr(choice, "finish_reason", None),
            "message_role": getattr(message, "role", None) if message else None,
            "content_length": len(content or ""),
            "content_preview": _content_preview(content or ""),
            "message_keys": message_keys,
        })

    usage = getattr(response, "usage", None)
    if hasattr(usage, "model_dump"):
        usage_payload = usage.model_dump(exclude_none=True)
    elif usage is not None:
        usage_payload = str(usage)
    else:
        usage_payload = None

    payload = {
        "id": getattr(response, "id", None),
        "model": getattr(response, "model", None),
        "created": getattr(response, "created", None),
        "object": getattr(response, "object", None),
        "choices": choices,
        "usage": usage_payload,
    }
    return _debug_preview(json.dumps(payload, ensure_ascii=False, default=str, indent=2))


def _response_finished_by_length(response) -> bool:
    for choice in getattr(response, "choices", []) or []:
        if getattr(choice, "finish_reason", None) == "length":
            return True
    return False


def _looks_like_incomplete_json(content: str) -> bool:
    text = (content or "").strip()
    if not text:
        return False
    return (
        text.startswith("{")
        and not text.endswith("}")
    ) or (
        text.startswith("[")
        and not text.endswith("]")
    )


def _request_debug_preview(prompt: str, transactions: list[dict], categories: list[str]) -> str:
    payload = {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash",
        "timeout_seconds": 60,
        "max_retries": 0,
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
        "max_tokens": DEEPSEEK_MAX_TOKENS,
        "system_message": "You are a precise transaction classifier. Always respond with valid JSON only.",
        "category_map": _build_category_map(categories),
        "batch_transaction_count": len(transactions),
        "batch_transaction_ids": [tx.get("id") for tx in transactions],
        "transaction_line_format": "id|当前分类|交易对方|商品说明",
        "transaction_lines": [_transaction_line(tx) for tx in transactions],
        "user_prompt": prompt,
    }
    return _debug_preview(json.dumps(payload, ensure_ascii=False, default=str, indent=2))


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
    debug: bool = False,
) -> list[dict]:
    """Send one batch of transactions to DeepSeek for classification."""
    prompt = _render_prompt_template(prompt_template, transactions, categories)
    category_map = _build_category_map(categories)
    request_debug = _request_debug_preview(prompt, transactions, categories) if debug else ""

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
                max_tokens=DEEPSEEK_MAX_TOKENS,
            )
            content = response.choices[0].message.content.strip()
            response_debug = _response_debug_preview(response) if debug else ""
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as e:
                splittable = _response_finished_by_length(response) or _looks_like_incomplete_json(content)
                raise AIClassificationBatchError(
                    f"AI returned non-JSON content: {_content_preview(content)}",
                    prompt=prompt if debug else "",
                    raw_response=content if debug else "",
                    response_debug=response_debug,
                    request_debug=request_debug,
                    splittable=splittable,
                ) from e

            transactions_result = _find_transactions_result(parsed)

            if transactions_result is None:
                logger.warning("Could not find transaction list in response: %s", content[:300])
                raise AIClassificationBatchError(
                    f"Unexpected response format: {_content_preview(content)}",
                    prompt=prompt if debug else "",
                    raw_response=content if debug else "",
                    response_debug=response_debug,
                    request_debug=request_debug,
                )

            # Validate and map results
            tx_map = {tx["id"]: tx for tx in transactions}
            validated = []
            invalid_count = 0
            invalid_examples = []
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
                else:
                    invalid_count += 1
                    if len(invalid_examples) < 3:
                        invalid_examples.append(str(item)[:120])

            if invalid_count:
                examples = "；".join(invalid_examples)
                raise AIClassificationBatchError(
                    f"AI returned {invalid_count} invalid classification item(s), examples: {examples}",
                    prompt=prompt if debug else "",
                    raw_response=content if debug else "",
                    response_debug=response_debug,
                    request_debug=request_debug,
                )
            if tx_map:
                missing_ids = list(tx_map.keys())[:5]
                raise AIClassificationBatchError(
                    f"AI missed {len(tx_map)} transaction(s), sample ids: {missing_ids}",
                    prompt=prompt if debug else "",
                    raw_response=content if debug else "",
                    response_debug=response_debug,
                    request_debug=request_debug,
                )

            # Fill in any records DeepSeek missed with original category.
            # This is kept as a defensive fallback, but tx_map should be empty
            # because missing records are treated as batch failures above.
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


def _classify_batch_with_split(
    api_key: str,
    transactions: list[dict],
    categories: list[str],
    prompt_template: str,
    debug: bool = False,
    split_depth: int = 0,
) -> list[dict]:
    try:
        return _classify_batch(api_key, transactions, categories, prompt_template, debug)
    except AIClassificationBatchError as e:
        can_split = (
            e.splittable
            and len(transactions) > 1
            and split_depth < MAX_SPLIT_RETRIES
        )
        if not can_split:
            e.split_depth = split_depth
            raise

        mid = max(1, len(transactions) // 2)
        left = transactions[:mid]
        right = transactions[mid:]
        logger.warning(
            "Splitting AI classification batch of %d transactions at depth %d after splittable error: %s",
            len(transactions), split_depth + 1, e,
        )
        left_results = _classify_batch_with_split(
            api_key,
            left,
            categories,
            prompt_template,
            debug,
            split_depth + 1,
        )
        right_results = _classify_batch_with_split(
            api_key,
            right,
            categories,
            prompt_template,
            debug,
            split_depth + 1,
        )
        return left_results + right_results


def _sse_event(event: str, data: object) -> str:
    """Format an SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _classify_stream(
    api_key: str,
    categories: list[str],
    prompt_template: str,
    only_expense: bool,
    only_unclassified: bool,
    limit: int,
    debug: bool,
    start_date: Optional[str],
    end_date: Optional[str],
    repo: SQLiteRepository,
):
    """Generator that yields SSE progress events and a final complete event."""
    # Phase 1: reading
    yield _sse_event("progress", {
        "phase": "reading",
        "message": "正在读取数据库中的交易数据...",
    })

    all_tx, _ = repo.list_transactions(
        page=1,
        page_size=1000000,
        start_date=start_date,
        end_date=end_date,
    )
    all_tx = _filter_classifiable_transactions(
        all_tx,
        only_expense=only_expense,
        only_unclassified=only_unclassified,
    )
    if limit > 0:
        all_tx = all_tx[:limit]
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
    failed_details = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {
            executor.submit(
                _classify_batch_with_split,
                api_key,
                batch,
                categories,
                prompt_template,
                debug,
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
                    failed_details.append({
                        "batch": completed,
                        "total_batches": total_batches,
                        "count": len(failed_batch),
                        "reason": _summarize_error(e),
                        "split_depth": getattr(e, "split_depth", 0),
                        "prompt_preview": _debug_preview(getattr(e, "prompt", "")) if debug else "",
                        "request_debug_preview": _debug_preview(getattr(e, "request_debug", "")) if debug else "",
                        "raw_response_preview": _debug_preview(getattr(e, "raw_response", "")) if debug else "",
                        "response_debug_preview": _debug_preview(getattr(e, "response_debug", "")) if debug else "",
                    })
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
                    "failed_details": failed_details[-10:],
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
                "failed_details": failed_details[-10:],
                "message": f"处理超时，已部分完成 {len(all_results)}/{total} 条",
            })

    # Phase 4: complete
    changed_count = sum(1 for r in all_results if r["old_category"] != r["new_category"])
    logger.info("Classification done: %d/%d classified, %d changed", len(all_results), total, changed_count)

    yield _sse_event("complete", {
        "total": total,
        "total_batches": total_batches,
        "classified": len(all_results),
        "changed": changed_count,
        "failed_batches": failed_batches,
        "failed_details": failed_details[-10:],
        "results": all_results,
    })


@router.post("/classify")
def classify_transactions(
    body: ClassifyRequest,
    repo: SQLiteRepository = Depends(get_repo),
    _: User = Depends(get_current_user),
):
    """Use DeepSeek API to classify all transactions. Returns SSE stream."""
    categories = _parse_categories(body.categories)
    if not categories:
        raise HTTPException(status_code=422, detail="请至少填写一个分类")

    prompt_template = body.prompt_template or DEFAULT_PROMPT_TEMPLATE
    repo.set_user_preference(PREF_KEY_AI_CLASSIFICATION, {
        "categories": body.categories,
        "api_key": body.api_key,
        "prompt_template": prompt_template,
    })

    return StreamingResponse(
        _classify_stream(
            body.api_key,
            categories,
            prompt_template,
            body.only_expense,
            body.only_unclassified,
            max(body.limit, 0),
            body.debug,
            body.start_date,
            body.end_date,
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
        if tid:
            try:
                update_data = {"is_ai_classified": 1}
                if category:
                    update_data["category"] = category
                result = repo.update_transaction(tid, update_data)
                if result:
                    updated += 1
            except Exception as e:
                logger.warning("Failed to update transaction %d: %s", tid, e)

    return ConfirmResponse(updated=updated, total=len(body.results))
