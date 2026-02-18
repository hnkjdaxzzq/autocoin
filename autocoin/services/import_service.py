import dataclasses
import uuid
from typing import Optional

from autocoin.parsers.alipay import AlipayParser
from autocoin.parsers.base import BillParser
from autocoin.parsers.wechat import WeChatParser
from autocoin.repository.base import DataRepository


class ImportService:

    def __init__(self, repo: DataRepository):
        self._repo = repo
        self._parsers: list[BillParser] = [AlipayParser(), WeChatParser()]

    def detect_parser(self, filename: str, file_bytes: bytes) -> BillParser:
        for parser in self._parsers:
            if parser.can_parse(filename, file_bytes):
                return parser
        raise ValueError(f"No parser available for file: {filename}")

    def import_file(self, file_bytes: bytes, filename: str) -> dict:
        parser = self.detect_parser(filename, file_bytes)
        batch_id = str(uuid.uuid4())

        self._repo.create_import_batch(
            {
                "id": batch_id,
                "filename": filename,
                "source": parser.SOURCE_NAME,
                "status": "pending",
                "total_rows": 0,
                "imported_rows": 0,
                "duplicate_rows": 0,
                "error_rows": 0,
            }
        )

        try:
            parsed = parser.parse(file_bytes)
            raw_dicts = [dataclasses.asdict(p) for p in parsed]
            inserted, duplicates = self._repo.bulk_insert_transactions(raw_dicts, batch_id)
            error_rows = len(parsed) - inserted - duplicates
            status = "success" if error_rows == 0 else "partial"

            self._repo.update_import_batch(
                batch_id,
                {
                    "total_rows": len(parsed),
                    "imported_rows": inserted,
                    "duplicate_rows": duplicates,
                    "error_rows": error_rows,
                    "status": status,
                },
            )
        except Exception:
            self._repo.update_import_batch(batch_id, {"status": "failed"})
            raise

        return self._repo.get_import_batch(batch_id)
