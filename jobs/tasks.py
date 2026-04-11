"""RQ-задачи для API-поиска (POST /api/v1/search)."""

from __future__ import annotations

import logging
from datetime import datetime

from business_supplier_finder import BusinessSupplierFinder
from app_db.search_jobs import SearchJobRepository

logger = logging.getLogger(__name__)


def run_api_search_job(search_id: str, product: str, region: str, quantity: str) -> None:
    repo = SearchJobRepository()
    try:
        finder = BusinessSupplierFinder()
        suppliers = finder.search_business_suppliers(product, region, quantity)
        payload = {
            "suppliers": suppliers,
            "product": product,
            "region": region,
            "quantity": quantity,
            "completed_at": datetime.now().isoformat(),
            "total": len(suppliers),
        }
        repo.mark_completed(search_id, payload)
        logger.info(f"✅ API поиск [{search_id}] завершен: найдено {len(suppliers)} поставщиков")
    except Exception as e:
        logger.error(f"❌ Ошибка выполнения поиска [{search_id}]: {str(e)}", exc_info=True)
        try:
            repo.mark_failed(search_id, str(e))
        except Exception as db_e:
            logger.error(f"❌ Не удалось записать ошибку задачи: {db_e}", exc_info=True)
    finally:
        repo.close()
