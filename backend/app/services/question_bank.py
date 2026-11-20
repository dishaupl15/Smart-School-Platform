import csv
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import BytesIO, StringIO
import threading
from typing import Any
from uuid import UUID, uuid4
import zipfile

from fastapi import HTTPException, UploadFile, status
from openpyxl import Workbook, load_workbook


MAX_IMPORT_BYTES = 2 * 1024 * 1024
MAX_IMPORT_ROWS = 500
MAX_XLSX_UNCOMPRESSED_BYTES = 20 * 1024 * 1024
IMPORT_TTL = timedelta(minutes=30)
IMPORT_COLUMNS = [
    "class_id",
    "subject_id",
    "chapter_id",
    "difficulty",
    "question_en",
    "question_hi",
    "question_mr",
    "explanation_en",
    "explanation_hi",
    "explanation_mr",
    *[
        f"option_{key}_{language}"
        for key in ("a", "b", "c", "d")
        for language in ("en", "hi", "mr")
    ],
    "correct_option",
]


def _error(message: str, code: int = 422) -> HTTPException:
    return HTTPException(status_code=code, detail=message)


async def parse_question_file(upload: UploadFile) -> list[dict[str, str]]:
    filename = (upload.filename or "").lower()
    content = await upload.read(MAX_IMPORT_BYTES + 1)
    if not content:
        raise _error("The uploaded file is empty.")
    if len(content) > MAX_IMPORT_BYTES:
        raise _error("Import files must not exceed 2 MiB.")

    if filename.endswith(".csv"):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise _error("CSV files must use UTF-8 encoding.") from None
        reader = csv.DictReader(StringIO(text, newline=""))
        rows = _validate_headers(reader.fieldnames)
        for row in reader:
            if None in row and any((value or "").strip() for value in row[None]):
                raise _error(f"CSV row {reader.line_num} contains extra columns.")
            if not any((value or "").strip() for value in row.values()):
                continue
            rows.append({key: (value or "").strip() for key, value in row.items() if key})
            if len(rows) > MAX_IMPORT_ROWS:
                raise _error(f"Import files may contain at most {MAX_IMPORT_ROWS} data rows.")
        return rows

    if filename.endswith(".xlsx"):
        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                if len(archive.infolist()) > 1000 or sum(item.file_size for item in archive.infolist()) > MAX_XLSX_UNCOMPRESSED_BYTES:
                    raise _error("The XLSX file contains too much expanded data.")
            workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        except HTTPException:
            raise
        except Exception:
            raise _error("The uploaded XLSX file is invalid.") from None
        try:
            sheet = workbook.active
            if sheet.max_row is not None and sheet.max_row > MAX_IMPORT_ROWS + 1:
                raise _error(
                    f"Import files may contain at most {MAX_IMPORT_ROWS} data rows."
                )
            if sheet.max_column is not None and sheet.max_column > len(IMPORT_COLUMNS):
                raise _error("The XLSX worksheet contains too many columns.")
            iterator = sheet.iter_rows(values_only=True)
            header_values = next(iterator, None)
            headers = [str(value).strip() if value is not None else "" for value in (header_values or ())]
            rows = _validate_headers(headers)
            for values in iterator:
                if not any(value is not None and str(value).strip() for value in values):
                    continue
                if any(value is not None and str(value).strip() for value in values[len(headers):]):
                    raise _error("An XLSX row contains values beyond the header columns.")
                rows.append(
                    {
                        key: str(values[index]).strip() if index < len(values) and values[index] is not None else ""
                        for index, key in enumerate(headers)
                        if key
                    }
                )
                if len(rows) > MAX_IMPORT_ROWS:
                    raise _error(f"Import files may contain at most {MAX_IMPORT_ROWS} data rows.")
            return rows
        finally:
            workbook.close()

    raise _error("Upload a .csv or .xlsx file.")


def _validate_headers(headers: list[str] | None) -> list[dict[str, str]]:
    if not headers:
        raise _error("The file must include a header row.")
    normalized = [str(header).strip() for header in headers]
    duplicates = {header for header in normalized if normalized.count(header) > 1}
    missing = set(IMPORT_COLUMNS) - set(normalized)
    unknown = set(normalized) - set(IMPORT_COLUMNS)
    if duplicates or missing or unknown:
        details = []
        if missing:
            details.append(f"missing columns: {', '.join(sorted(missing))}")
        if unknown:
            details.append(f"unknown columns: {', '.join(sorted(unknown))}")
        if duplicates:
            details.append(f"duplicate columns: {', '.join(sorted(duplicates))}")
        raise _error("Invalid import headers (" + "; ".join(details) + ").")
    return []


def import_row_to_payload(row: dict[str, str]) -> dict[str, Any]:
    try:
        class_id = UUID(row.get("class_id", "").strip())
        subject_id = UUID(row.get("subject_id", "").strip())
        chapter_id = UUID(row.get("chapter_id", "").strip())
    except (ValueError, AttributeError):
        raise ValueError("class_id, subject_id, and chapter_id must be valid UUIDs.") from None

    difficulty = row.get("difficulty", "").strip().upper()
    if difficulty not in {"EASY", "MEDIUM", "HARD"}:
        raise ValueError("difficulty must be EASY, MEDIUM, or HARD.")
    if not row.get("question_en", "").strip():
        raise ValueError("question_en is required.")
    question_translations = []
    for language in ("en", "hi", "mr"):
        text = row.get(f"question_{language}", "").strip()
        if text:
            translation = {
                "language_code": language,
                "question_text": text,
            }
            explanation = row.get(f"explanation_{language}", "").strip()
            if explanation:
                translation["explanation"] = explanation
            question_translations.append(translation)

    correct = row.get("correct_option", "").strip().upper()
    if correct not in {"A", "B", "C", "D"}:
        raise ValueError("correct_option must be A, B, C, or D.")
    options = []
    for order, key in enumerate(("A", "B", "C", "D"), start=1):
        if not row.get(f"option_{key.lower()}_en", "").strip():
            raise ValueError(f"option_{key.lower()}_en is required.")
        translations = [
            {"language_code": language, "option_text": row.get(f"option_{key.lower()}_{language}", "").strip()}
            for language in ("en", "hi", "mr")
            if row.get(f"option_{key.lower()}_{language}", "").strip()
        ]
        options.append(
            {
                "option_key": key,
                "display_order": order,
                "is_correct": key == correct,
                "translations": translations,
            }
        )
    return {
        "class_id": class_id,
        "subject_id": subject_id,
        "chapter_id": chapter_id,
        "difficulty": difficulty,
        "question_type": "SINGLE_CHOICE",
        "status": "DRAFT",
        "translations": question_translations,
        "options": options,
    }


class ImportPreviewStore:
    """Short-lived process-local state; entries are private to the initiating admin."""

    def __init__(self) -> None:
        self._entries: dict[UUID, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def _purge(self, now: datetime) -> None:
        expired = [
            import_id
            for import_id, entry in self._entries.items()
            if entry["expires_at"] <= now
        ]
        for import_id in expired:
            self._entries.pop(import_id, None)

    def create(self, user_id: UUID, school_id: UUID, rows: list[dict[str, Any]]) -> tuple[UUID, datetime]:
        now = datetime.now(timezone.utc)
        expires_at = now + IMPORT_TTL
        with self._lock:
            self._purge(now)
            while len(self._entries) >= 100:
                oldest = min(self._entries, key=lambda key: self._entries[key]["created_at"])
                self._entries.pop(oldest, None)
            import_id = uuid4()
            self._entries[import_id] = {
                "user_id": user_id,
                "school_id": school_id,
                "created_at": now,
                "expires_at": expires_at,
                "rows": rows,
                "mode": None,
                "committed_rows": 0,
                "rejected": False,
            }
        return import_id, expires_at

    def get(self, import_id: UUID, user_id: UUID, school_id: UUID) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._purge(now)
            entry = self._entries.get(import_id)
            if (
                entry is None
                or entry["user_id"] != user_id
                or entry["school_id"] != school_id
            ):
                raise _error("Import preview not found or expired.", status.HTTP_404_NOT_FOUND)
            return deepcopy(entry)

    def claim(
        self,
        import_id: UUID,
        user_id: UUID,
        school_id: UUID,
        mode: str,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._purge(now)
            entry = self._entries.get(import_id)
            if (
                entry is None
                or entry["user_id"] != user_id
                or entry["school_id"] != school_id
            ):
                raise _error("Import preview not found or expired.", status.HTTP_404_NOT_FOUND)
            if entry["mode"] is not None:
                raise _error("This import preview has already been confirmed.", status.HTTP_409_CONFLICT)
            entry["mode"] = mode
            return entry


import_preview_store = ImportPreviewStore()


def csv_template() -> bytes:
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(IMPORT_COLUMNS)
    return output.getvalue().encode("utf-8-sig")


def xlsx_template() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Question Bank"
    sheet.append(IMPORT_COLUMNS)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def import_report_csv(entry: dict[str, Any]) -> bytes:
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "row_number",
            "valid",
            "status",
            "question_preview",
            "question_id",
            "errors",
            "warnings",
        ]
    )
    for row in entry["rows"]:
        values = [
            row["row_number"],
            str(row["valid"]).lower(),
            row["status"],
            row.get("question_preview") or "",
            str(row["question_id"]) if row.get("question_id") else "",
            " | ".join(row["errors"]),
            " | ".join(row.get("warnings", [])),
        ]
        writer.writerow(
            [
                "'" + value if str(value).lstrip().startswith(("=", "+", "-", "@")) else value
                for value in values
            ]
        )
    return output.getvalue().encode("utf-8-sig")
