#!/usr/bin/env python3
"""Initialize SQLite database (creates file and tables if missing)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app_db import init_db  # noqa: E402


def _default_excel_path() -> Path:
    raw = os.getenv("SUPPLIER_EXCEL_PATH", str(_ROOT / "data" / "baza postavshiki.xlsx"))
    p = Path(raw)
    return p if p.is_absolute() else (_ROOT / p).resolve()


def main() -> None:
    init_db()
    print("Database initialized.")

    (_ROOT / "data").mkdir(parents=True, exist_ok=True)
    excel_path = _default_excel_path()
    if not excel_path.exists():
        sample_script = _ROOT / "scripts" / "create_sample_baza_excel.py"
        if sample_script.is_file():
            r = subprocess.run([sys.executable, str(sample_script)], cwd=str(_ROOT))
            if r.returncode != 0:
                print("Подсказка: python scripts/create_sample_baza_excel.py")
        else:
            print("Подсказка: положите Excel по пути", excel_path)

    if excel_path.exists() and os.getenv("IMPORT_SUPPLIERS_EXCEL_ON_INIT", "true").lower() in (
        "1",
        "true",
        "yes",
    ):
        from app_db.excel_import import import_suppliers_from_excel

        n, skipped = import_suppliers_from_excel(excel_path, project_root=_ROOT)
        print(f"Импорт из Excel ({excel_path.name}): строк={n}, пропущено без названия={skipped}")


if __name__ == "__main__":
    main()
