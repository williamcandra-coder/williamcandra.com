"""Deterministic, atomic, no-change-no-write file writers.

Two properties matter here and both are load-bearing:

**Determinism.** The same logical content must always produce the same bytes:
sorted keys, sorted rows, fixed separators, LF endings, one trailing newline.
Without this, every scheduled run produces a diff and the review process the
whole commit policy depends on becomes noise.

**No-change means no-write.** Every writer compares against what is already on
disk and returns False without touching the file if the bytes match. That is
what lets a workflow exit successfully having committed nothing.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

#: Compact but readable. `separators` is pinned so a Python version change
#: cannot silently alter whitespace and produce a phantom diff.
_JSON_KWARGS = dict(
    indent=2,
    sort_keys=True,
    ensure_ascii=False,
    separators=(",", ": "),
    allow_nan=False,
)


def canonical_json(obj: Any) -> str:
    """Pretty, stable JSON with a trailing newline."""
    return json.dumps(obj, **_JSON_KWARGS) + "\n"


def compact_json(obj: Any) -> str:
    """Single-line JSON for JSONL rows and for hashing."""
    return json.dumps(
        obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )


def content_hash(obj: Any) -> str:
    """SHA-256 over the compact canonical form.

    Hashing the canonical form rather than the pretty form means the hash is
    stable across formatting changes.
    """
    return hashlib.sha256(compact_json(obj).encode("utf-8")).hexdigest()


def bytes_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write(path: Path, text: str) -> None:
    """Write via a temp file in the same directory, then rename.

    A crash mid-write leaves the previous good file intact rather than a
    truncated one — the on-disk half of "invalid data never replaces the last
    validated data".
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def write_text_if_changed(path: Path, text: str) -> bool:
    """Return True only if the file's bytes actually changed."""
    path = Path(path)
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == text:
                return False
        except UnicodeDecodeError:
            pass  # existing file is not text; overwrite it
    _atomic_write(path, text)
    return True


def write_json_if_changed(path: Path, obj: Any) -> bool:
    return write_text_if_changed(Path(path), canonical_json(obj))


#: Fields that record *when we looked*, not *what we found*. A run that finds
#: identical data must not rewrite a file just because the clock moved — that
#: would turn every scheduled run into a diff and bury real changes in noise.
VOLATILE_FIELDS = ("generatedAt", "retrievedAt", "snapshotAt", "source.retrievedAt")


def _strip_volatile(value: Any, fields: Iterable[str]) -> Any:
    """Copy of ``value`` with the named (possibly dotted) paths removed."""
    if not isinstance(value, dict):
        return value
    out = dict(value)
    for field_path in fields:
        head, _, tail = field_path.partition(".")
        if head not in out:
            continue
        if tail:
            out[head] = _strip_volatile(out[head], [tail])
        else:
            out.pop(head, None)
    return out


def same_ignoring_volatile(
    left: Any, right: Any, fields: Iterable[str] = VOLATILE_FIELDS
) -> bool:
    fields = list(fields)
    return _strip_volatile(left, fields) == _strip_volatile(right, fields)


def stable_content_hash(obj: Any, fields: Iterable[str] = VOLATILE_FIELDS) -> str:
    """Hash of the substantive content, with retrieval timestamps stripped.

    A contentHash that moved every time the clock moved would be useless as a
    change signal — and worse, it would make the document differ from itself and
    defeat no-change-no-write.
    """
    return content_hash(_strip_volatile(obj, list(fields)))


def write_document_if_changed(
    path: Path, document: Any, volatile_fields: Iterable[str] = VOLATILE_FIELDS
) -> bool:
    """Write a generated document, ignoring timestamp-only differences.

    When the substantive content is unchanged the file is left completely
    alone — including its original ``generatedAt``, which stays truthful as
    "when this content was produced" rather than "when we last checked".
    """
    path = Path(path)
    existing = read_json(path)
    if existing is not None and same_ignoring_volatile(existing, document, volatile_fields):
        return False
    return write_text_if_changed(path, canonical_json(document))


def read_json(path: Path, default: Any = None) -> Any:
    path = Path(path)
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# JSONL
# ---------------------------------------------------------------------------


def read_jsonl(path: Path) -> list:
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: malformed JSONL row: {exc}") from exc
    return rows


def write_jsonl_if_changed(
    path: Path, rows: Iterable[dict], sort_key: Optional[Callable] = None
) -> bool:
    rows = list(rows)
    if sort_key is not None:
        rows = sorted(rows, key=sort_key)
    text = "".join(compact_json(r) + "\n" for r in rows)
    return write_text_if_changed(Path(path), text)


def upsert_jsonl(
    path: Path,
    new_rows: Iterable[dict],
    key: Callable[[dict], tuple],
    sort_key: Optional[Callable] = None,
    replace_existing: bool = True,
    volatile_fields: Iterable[str] = VOLATILE_FIELDS,
) -> tuple:
    """Merge rows into a JSONL dataset by primary key.

    This is the idempotency primitive: rerunning a collector over the same
    source produces the same keys, which match themselves in place, so the file
    is byte-identical and no commit happens.

    A row whose only difference is a retrieval timestamp is treated as
    unchanged and the existing row is kept, so the stored ``retrievedAt``
    remains the moment we first saw that content.

    Returns ``(changed, added, updated)``.
    """
    path = Path(path)
    volatile_fields = list(volatile_fields)
    existing = read_jsonl(path)
    index = {key(r): i for i, r in enumerate(existing)}
    merged = list(existing)
    added = updated = 0

    for row in new_rows:
        k = key(row)
        if k in index:
            current = merged[index[k]]
            if replace_existing and not same_ignoring_volatile(current, row, volatile_fields):
                merged[index[k]] = row
                updated += 1
        else:
            index[k] = len(merged)
            merged.append(row)
            added += 1

    if sort_key is None:
        sort_key = key
    changed = write_jsonl_if_changed(path, merged, sort_key=sort_key)
    return changed, added, updated


def append_jsonl_unique(
    path: Path, new_rows: Iterable[dict], key: Callable[[dict], tuple]
) -> tuple:
    """Append rows that are not already present, preserving existing order.

    Used for append-only history: existing rows are never reordered, rewritten
    or removed, so the file's history is a genuine audit trail rather than a
    regenerated view.
    """
    path = Path(path)
    existing = read_jsonl(path)
    seen = {key(r) for r in existing}
    appended = []
    for row in new_rows:
        k = key(row)
        if k in seen:
            continue
        seen.add(k)
        appended.append(row)
    if not appended:
        return False, 0
    text = "".join(compact_json(r) + "\n" for r in existing + appended)
    return write_text_if_changed(path, text), len(appended)


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def _csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        # Render integral floats without a trailing .0 so a value read back and
        # rewritten does not churn the file.
        if value.is_integer() and abs(value) < 1e15:
            return str(int(value))
        return repr(value)
    text = str(value)
    if any(c in text for c in [",", '"', "\n", "\r"]):
        return '"' + text.replace('"', '""') + '"'
    return text


def write_csv_if_changed(
    path: Path, rows: Iterable[dict], columns: list, sort_key: Optional[Callable] = None
) -> bool:
    rows = list(rows)
    if sort_key is not None:
        rows = sorted(rows, key=sort_key)
    lines = [",".join(columns)]
    lines.extend(",".join(_csv_cell(r.get(c)) for c in columns) for r in rows)
    return write_text_if_changed(Path(path), "\n".join(lines) + "\n")


def read_csv(path: Path) -> list:
    """Minimal RFC4180-ish reader. Empty string decodes to None, so a blank
    cell stays missing rather than becoming 0 downstream."""
    import csv as _csv

    path = Path(path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [
            {k: (None if v == "" else v) for k, v in row.items()}
            for row in _csv.DictReader(fh)
        ]


def upsert_csv(
    path: Path,
    new_rows: Iterable[dict],
    columns: list,
    key: Callable[[dict], tuple],
    sort_key: Optional[Callable] = None,
) -> tuple:
    """CSV equivalent of :func:`upsert_jsonl`. Returns ``(changed, added, updated)``."""
    path = Path(path)
    existing = read_csv(path)
    index = {key(r): i for i, r in enumerate(existing)}
    merged = list(existing)
    added = updated = 0

    def as_cells(row: dict) -> tuple:
        # A CSV round-trip turns 9250 into "9250". Comparing the in-memory value
        # against the parsed-back string would report every unchanged row as
        # updated, so both sides are compared as they will actually be written.
        return tuple(_csv_cell(row.get(c)) for c in columns)

    for row in new_rows:
        normalised = {c: row.get(c) for c in columns}
        k = key(normalised)
        if k in index:
            if as_cells(merged[index[k]]) != as_cells(normalised):
                merged[index[k]] = normalised
                updated += 1
        else:
            index[k] = len(merged)
            merged.append(normalised)
            added += 1

    changed = write_csv_if_changed(
        path, merged, columns, sort_key=sort_key or key
    )
    return changed, added, updated
