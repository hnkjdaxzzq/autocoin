import logging
import uuid
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from autocoin.auth import get_current_user
from autocoin.database import get_db
from autocoin.models.user import User
from autocoin.repository.sqlite import SQLiteRepository
from autocoin.schemas.import_schema import (
    ImageRecognizeResponse,
    ImageTransactionItem,
    ImportBatchResponse,
)
from autocoin.services.image_recognizer import recognize_with_fallback
from autocoin.services.import_service import ImportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/imports", tags=["imports"])


def get_repo(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SQLiteRepository:
    return SQLiteRepository(db, user.id)


@router.post("", response_model=ImportBatchResponse)
async def upload_bill(
    file: UploadFile = File(...),
    repo: SQLiteRepository = Depends(get_repo),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
    if ext not in ("csv", "xlsx"):
        raise HTTPException(
            status_code=400,
            detail="Only .csv (Alipay) and .xlsx (WeChat) files are supported",
        )

    file_bytes = await file.read()
    service = ImportService(repo)

    try:
        result = service.import_file(file_bytes, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

    return result


@router.get("", response_model=list[ImportBatchResponse])
def list_batches(repo: SQLiteRepository = Depends(get_repo)):
    return repo.list_import_batches()


@router.get("/{batch_id}", response_model=ImportBatchResponse)
def get_batch(batch_id: str, repo: SQLiteRepository = Depends(get_repo)):
    batch = repo.get_import_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")
    return batch


# --------------- Image recognition endpoints ---------------

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp"}
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20 MB per image


@router.get("/image/quota")
def get_image_quota(repo: SQLiteRepository = Depends(get_repo)):
    """Return today's image recognition usage and limit."""
    from autocoin.config import settings as _settings
    daily_limit = _settings.image_import_daily_limit
    daily_used = repo.count_today_image_recognitions()
    return {"daily_used": daily_used, "daily_limit": daily_limit, "remaining": max(0, daily_limit - daily_used)}


@router.post("/image/recognize", response_model=ImageRecognizeResponse)
async def recognize_images(
    files: list[UploadFile] = File(...),
    _user: User = Depends(get_current_user),
    repo: SQLiteRepository = Depends(get_repo),
):
    """Upload one or more images and recognize transactions via LLM."""
    from autocoin.config import settings as _settings

    if not files:
        raise HTTPException(status_code=400, detail="No images provided")
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="最多同时上传 10 张图片")

    # Check daily image recognition quota
    daily_limit = _settings.image_import_daily_limit
    daily_used = repo.count_today_image_recognitions()
    if daily_used + len(files) > daily_limit:
        remaining = max(0, daily_limit - daily_used)
        raise HTTPException(
            status_code=429,
            detail=f"今日图片识别额度不足（剩余 {remaining} 张，本次 {len(files)} 张），请明天再试",
        )

    images: list[tuple[bytes, str]] = []
    filenames: list[str] = []
    for f in files:
        content_type = f.content_type or "image/jpeg"
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的图片格式: {f.filename} ({content_type})",
            )
        data = await f.read()
        if len(data) > MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"图片文件过大: {f.filename} (最大 20MB)",
            )
        images.append((data, content_type))
        filenames.append(f.filename or "image")

    try:
        transactions = await recognize_with_fallback(images)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("Image recognition failed")
        raise HTTPException(
            status_code=500,
            detail=f"图片识别失败: {str(e)}",
        )

    # Record recognition usage (counts toward daily quota)
    recognize_batch_id = str(uuid.uuid4())
    repo.create_import_batch({
        "id": recognize_batch_id,
        "filename": f"图片识别 ({len(images)} 张)",
        "source": "image_recognize",
        "status": "success",
        "total_rows": len(images),
        "imported_rows": 0,
        "duplicate_rows": 0,
        "error_rows": 0,
    })
    daily_used += len(images)

    return ImageRecognizeResponse(
        transactions=[ImageTransactionItem(**t) for t in transactions],
        image_count=len(images),
        filenames=filenames,
        daily_used=daily_used,
        daily_limit=daily_limit,
    )


@router.post("/image/check-duplicates")
async def check_image_duplicates(
    transactions: list[ImageTransactionItem] = Body(..., embed=True),
    repo: SQLiteRepository = Depends(get_repo),
):
    """Check which transactions already exist in DB."""
    items = [t.model_dump() for t in transactions]
    flags = repo.check_duplicates(items)
    return {"duplicates": flags}


@router.post("/image/confirm", response_model=ImportBatchResponse)
async def confirm_image_import(
    transactions: list[ImageTransactionItem] = Body(...),
    filenames: list[str] = Body(default=[]),
    repo: SQLiteRepository = Depends(get_repo),
):
    """Confirm and import recognized transactions from images."""

    if not transactions:
        raise HTTPException(status_code=400, detail="No transactions to import")

    # Validate all transactions
    validation_errors = []
    for i, t in enumerate(transactions, 1):
        if not t.transaction_time:
            validation_errors.append(f"第 {i} 条: 缺少交易时间")
        if t.amount <= 0:
            validation_errors.append(f"第 {i} 条: 金额必须大于 0")
    if validation_errors:
        raise HTTPException(
            status_code=422,
            detail="\n".join(validation_errors[:10]),
        )

    # Build display filename from original image names
    if filenames:
        display_name = ", ".join(filenames)
        if len(display_name) > 200:
            display_name = display_name[:197] + "..."
    else:
        display_name = f"图片导入 ({len(transactions)} 条)"

    # De-duplicate: skip items that already exist in DB
    items_dicts = [t.model_dump() for t in transactions]
    dup_flags = repo.check_duplicates(items_dicts)
    unique_transactions = [t for t, is_dup in zip(transactions, dup_flags) if not is_dup]
    duplicate_count = sum(dup_flags)

    if not unique_transactions:
        # All duplicates — still create a batch record for visibility
        batch_id = str(uuid.uuid4())
        repo.create_import_batch({
            "id": batch_id,
            "filename": display_name,
            "source": "image",
            "status": "success",
            "total_rows": len(transactions),
            "imported_rows": 0,
            "duplicate_rows": duplicate_count,
            "error_rows": 0,
        })
        return repo.get_import_batch(batch_id)

    batch_id = str(uuid.uuid4())
    repo.create_import_batch(
        {
            "id": batch_id,
            "filename": display_name,
            "source": "image",
            "status": "pending",
            "total_rows": len(transactions),
            "imported_rows": 0,
            "duplicate_rows": duplicate_count,
            "error_rows": 0,
        }
    )

    inserted = 0
    error_rows = 0
    for t in unique_transactions:
        try:
            repo.create_transaction(
                {
                    "source": "image",
                    "source_order_id": None,
                    "merchant_order_id": None,
                    "transaction_time": t.transaction_time,
                    "transaction_type": t.category or "",
                    "category": t.category or "",
                    "counterparty": t.counterparty or "",
                    "counterparty_account": "",
                    "product": t.product or "",
                    "direction": t.direction,
                    "amount": t.amount,
                    "payment_method": t.payment_method or "",
                    "status": "已完成",
                    "remark": t.remark or "",
                    "import_batch_id": batch_id,
                }
            )
            inserted += 1
        except Exception:
            logger.exception("Failed to insert image transaction")
            error_rows += 1

    status = "success" if error_rows == 0 else ("partial" if inserted > 0 else "failed")
    repo.update_import_batch(
        batch_id,
        {
            "imported_rows": inserted,
            "duplicate_rows": duplicate_count,
            "error_rows": error_rows,
            "status": status,
        },
    )

    return repo.get_import_batch(batch_id)
