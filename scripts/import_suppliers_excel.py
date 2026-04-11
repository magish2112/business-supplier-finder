#!/usr/bin/env python3
"""Импорт поставщиков из Excel в SQLite. Пример: python scripts/import_suppliers_excel.py"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")


def main() -> None:
    from app_db import init_db
    from app_db.excel_import import import_suppliers_from_excel

    default_xlsx = _ROOT / "data" / "baza postavshiki.xlsx"
    p = argparse.ArgumentParser(description="Импорт поставщиков из Excel в БД")
    p.add_argument(
        "excel",
        nargs="?",
        default=os.getenv("SUPPLIER_EXCEL_PATH", str(default_xlsx)),
        help="Путь к .xlsx (по умолчанию SUPPLIER_EXCEL_PATH или data/baza postavshiki.xlsx)",
    )
    p.add_argument("--sheet", default=None, help="Имя листа (по умолчанию первый лист)")
    args = p.parse_args()

    init_db()
    n, skipped = import_suppliers_from_excel(
        Path(args.excel),
        sheet_name=args.sheet,
        project_root=_ROOT,
    )
    print(f"Импортировано строк: {n}, пропущено без названия: {skipped}")


if __name__ == "__main__":
    main()
