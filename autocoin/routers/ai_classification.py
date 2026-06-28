import json
import logging
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

BATCH_SIZE = 100
MAX_WORKERS = 5
MAX_RETRIES = 3
RETRY_DELAY = 2


class ClassifyRequest(BaseModel):
    api_key: str
    categories: str  # comma-separated, e.g. "美食,交通,旅游"


class ClassifyResponse(BaseModel):
    total: int
    classified: int
    results: list[dict]


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


def _build_batch_prompt(transactions: list[dict], categories: list[str]) -> str:
    """Build a prompt for classifying a batch of transactions."""
    cats_str = ", ".join(categories)
    lines = []
    for tx in transactions:
        counterparty = tx.get("counterparty") or ""
        product = tx.get("product") or ""
        remark = tx.get("remark") or ""
        old_cat = tx.get("category") or ""
        lines.append(
            f'id={tx["id"]}, current_category="{old_cat}", counterparty="{counterparty}", product="{product}", remark="{remark}"'
        )
    tx_list = "\n".join(lines)

    return f"""You are a strict transaction classifier. The user has specified EXACTLY these categories: [{cats_str}].

Your task: Assign EVERY transaction to ONE of these exact category strings. You must STRICTLY use only the strings from the list above — nothing else, no variations, no synonyms.

Important rules:
- If a transaction's current category is close to but not exactly one of the user's categories, map it to the closest match from the list.
- Example: user categories = [餐饮,交通], current_category = "餐饮美食" → must map to "餐饮"
- Example: user categories = [餐饮,交通], current_category = "打车" → must map to "交通"
- Example: user categories = [购物,交通], current_category = "餐饮" → must map to the closest match (购物)
- NEVER output a category that is not in the user's list.
- EVERY transaction must get a category — no skipping.

For each transaction, respond with a JSON object containing a "transactions" key, whose value is an array of objects, each with fields "id" (integer) and "category" (string — must be one of [{cats_str}]).

Transactions to classify (each includes current_category for reference):
{tx_list}

Return ONLY a valid JSON object containing the "transactions" array. No other text."""


def _classify_batch(
    api_key: str,
    transactions: list[dict],
    categories: list[str],
) -> list[dict]:
    """Send one batch of transactions to DeepSeek for classification."""
    prompt = _build_batch_prompt(transactions, categories)

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

            # Handle various response shapes
            transactions_result = None
            if isinstance(parsed, dict):
                for key in ("transactions", "results", "data", "classifications"):
                    if key in parsed and isinstance(parsed[key], list):
                        transactions_result = parsed[key]
                        break
            if isinstance(parsed, list):
                transactions_result = parsed

            if transactions_result is None:
                logger.warning("Could not find transaction list in response: %s", content[:300])
                raise ValueError("Unexpected response format")

            # Validate and map results
            tx_map = {tx["id"]: tx for tx in transactions}
            validated = []
            for item in transactions_result:
                tid = item.get("id")
                cat = item.get("category", "").strip()
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
    repo: SQLiteRepository,
):
    """Generator that yields SSE progress events and a final complete event."""
    # Phase 1: reading
    yield _sse_event("progress", {
        "phase": "reading",
        "message": "正在读取数据库中的交易数据...",
    })

    all_tx, total = repo.list_transactions(page=1, page_size=1000000)
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
            executor.submit(_classify_batch, api_key, batch, categories): batch
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

    return StreamingResponse(
        _classify_stream(body.api_key, categories, repo),
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
