from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from autocoin.database import get_db
from autocoin.repository.sqlite import SQLiteRepository
from autocoin.schemas.import_schema import ImportBatchResponse
from autocoin.services.import_service import ImportService

router = APIRouter(prefix="/imports", tags=["imports"])


def get_repo(db: Session = Depends(get_db)) -> SQLiteRepository:
    return SQLiteRepository(db)


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
