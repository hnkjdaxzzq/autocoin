import csv
from datetime import date, datetime
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from sqlalchemy.sql.sqltypes import Boolean, DateTime, Float, Integer

from autocoin.auth import get_current_user
from autocoin.database import Base, get_db
from autocoin.models.user import User

router = APIRouter(prefix="/data-management", tags=["data-management"])

BACKUP_VERSION = "1"
BACKUP_HEADER = [
    "autocoin_backup_version",
    "record_type",
    "table_name",
    "row_number",
    "data_json",
]
ERROR_MESSAGE = "数据错误，请检查上传的备份数据。"


def _model_tables():
    return list(Base.metadata.sorted_tables)


def _table_specs() -> dict[str, list[str]]:
    return {
        table.name: [column.name for column in table.columns]
        for table in _model_tables()
    }


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return value


def _parse_column_value(column, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(column.type, DateTime):
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("T", " "))
    if isinstance(column.type, Boolean):
        return bool(value)
    if isinstance(column.type, Integer) and value != "":
        return int(value)
    if isinstance(column.type, Float) and value != "":
        return float(value)
    return value


def _build_backup_csv(db: Session) -> str:
    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf)
    writer.writerow(BACKUP_HEADER)

    specs = _table_specs()
    metadata = {
        "format": "autocoin_full_database_backup",
        "version": BACKUP_VERSION,
        "generated_at": datetime.utcnow().isoformat(sep=" "),
        "tables": specs,
    }
    writer.writerow([
        BACKUP_VERSION,
        "metadata",
        "__backup__",
        "",
        json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
    ])

    for table in _model_tables():
        order_cols = [col for col in table.primary_key.columns]
        stmt = select(table)
        if order_cols:
            stmt = stmt.order_by(*order_cols)
        rows = db.execute(stmt).mappings().all()
        for idx, row in enumerate(rows, 1):
            data = {
                column.name: _json_value(row[column.name])
                for column in table.columns
            }
            writer.writerow([
                BACKUP_VERSION,
                "row",
                table.name,
                str(idx),
                json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            ])
    return buf.getvalue()


def _read_backup(file_bytes: bytes) -> dict[str, list[dict]]:
    try:
        text_content = file_bytes.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text_content))
    except UnicodeDecodeError as exc:
        raise ValueError(ERROR_MESSAGE) from exc

    if reader.fieldnames != BACKUP_HEADER:
        raise ValueError(ERROR_MESSAGE)

    tables = {table.name: table for table in _model_tables()}
    expected_specs = _table_specs()
    parsed_rows = {name: [] for name in tables}
    metadata_seen = False

    try:
        for row in reader:
            if row.get("autocoin_backup_version") != BACKUP_VERSION:
                raise ValueError(ERROR_MESSAGE)

            record_type = row.get("record_type")
            table_name = row.get("table_name")
            try:
                data = json.loads(row.get("data_json") or "{}")
            except json.JSONDecodeError as exc:
                raise ValueError(ERROR_MESSAGE) from exc

            if record_type == "metadata":
                if metadata_seen or table_name != "__backup__":
                    raise ValueError(ERROR_MESSAGE)
                if data.get("format") != "autocoin_full_database_backup":
                    raise ValueError(ERROR_MESSAGE)
                if data.get("version") != BACKUP_VERSION:
                    raise ValueError(ERROR_MESSAGE)
                if data.get("tables") != expected_specs:
                    raise ValueError(ERROR_MESSAGE)
                metadata_seen = True
                continue

            if record_type != "row" or table_name not in tables:
                raise ValueError(ERROR_MESSAGE)
            if not metadata_seen:
                raise ValueError(ERROR_MESSAGE)

            table = tables[table_name]
            expected_columns = expected_specs[table_name]
            if set(data.keys()) != set(expected_columns):
                raise ValueError(ERROR_MESSAGE)

            parsed = {}
            for column in table.columns:
                parsed[column.name] = _parse_column_value(column, data.get(column.name))
            parsed_rows[table_name].append(parsed)
    except csv.Error as exc:
        raise ValueError(ERROR_MESSAGE) from exc

    if not metadata_seen:
        raise ValueError(ERROR_MESSAGE)
    return parsed_rows


def _restore_backup(db: Session, rows_by_table: dict[str, list[dict]]) -> None:
    tables = _model_tables()
    table_names = [table.name for table in tables]

    try:
        for table in reversed(tables):
            db.execute(table.delete())

        has_sequence = db.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'")
        ).first()
        if has_sequence and table_names:
            placeholders = ", ".join(f":name{i}" for i in range(len(table_names)))
            params = {f"name{i}": name for i, name in enumerate(table_names)}
            db.execute(
                text(f"DELETE FROM sqlite_sequence WHERE name IN ({placeholders})"),
                params,
            )

        for table in tables:
            rows = rows_by_table.get(table.name, [])
            if rows:
                db.execute(table.insert(), rows)
        db.commit()
    except Exception:
        db.rollback()
        raise


@router.get("/backup/export")
def export_full_backup(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    content = _build_backup_csv(db)
    filename = f"autocoin_full_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/backup/validate")
async def validate_full_backup(
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
):
    try:
        rows_by_table = _read_backup(await file.read())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=ERROR_MESSAGE) from exc

    return {
        "valid": True,
        "tables": {
            table_name: len(rows)
            for table_name, rows in rows_by_table.items()
        },
    }


@router.post("/backup/restore")
async def restore_full_backup(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        rows_by_table = _read_backup(await file.read())
        _restore_backup(db, rows_by_table)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=ERROR_MESSAGE) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="数据还原失败") from exc

    return {"message": "数据还原成功"}
