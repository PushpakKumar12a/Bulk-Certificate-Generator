import csv
import io

from pydantic import ValidationError

from app.jobs.schemas import RecipientIn

def read_csv(data: bytes, max_rows: int) -> list[tuple[int, RecipientIn]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must use UTF-8 encoding") from exc

    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    if "full_name" not in (reader.fieldnames or []):
        raise ValueError("CSV must contain a full_name column")

    rows: list[tuple[int, RecipientIn]] = []

    try:
        for line, row in enumerate(reader, start=2):
            if line - 1 > max_rows:
                raise ValueError(f"CSV cannot contain more than {max_rows} rows")
            if None in row:
                raise ValueError(f"Invalid CSV row {line}")

            try:
                item = RecipientIn(
                    name=(row.get("full_name") or "").strip(),
                    email=(row.get("email") or "").strip() or None,
                )
            except ValidationError as exc:
                message = exc.errors()[0].get("msg", "Invalid recipient")
                raise ValueError(f"Invalid row {line}: {message}") from exc

            rows.append((line, item))
    except csv.Error as exc:
        raise ValueError("Invalid CSV format") from exc

    if not rows:
        raise ValueError("CSV must contain at least one recipient")
    return rows