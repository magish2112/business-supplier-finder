#!/usr/bin/env python3
"""
Улучшенное веб-приложение для поиска бизнес-поставщиков
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, Response
from werkzeug.exceptions import HTTPException, NotFound
from business_supplier_finder import BusinessSupplierFinder, OPENAI_AVAILABLE, PERPLEXITY_CONFIG
import json
import logging
import threading
from datetime import datetime
import os
import socket
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional
from dotenv import load_dotenv
from functools import wraps
import time
import uuid

from routes.orchestration_routes import orchestration_bp
from routes.api_security import enforce_api_key, validate_startup_security
from routes.api_errors import api_error
from app_db.search_jobs import SearchJobRepository, ensure_search_jobs_table
from jobs import enqueue_api_search

# Загружаем переменные окружения
load_dotenv()
validate_startup_security()
ensure_search_jobs_table()

# Настройка логирования для веб-приложения
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('web_app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'default_secret_key_change_in_production')

app.register_blueprint(orchestration_bp)


@app.before_request
def _require_api_key_for_protected_api():
    """A1: защита JSON API при заданной переменной API_KEY."""
    return enforce_api_key()


# Глобальные переменные для хранения результатов поиска
search_results = []
search_cache = {}  # Кэш HTTP (@cache_search); не путать с api_search_jobs в SQLite

# Декоратор для кэширования результатов поиска
def cache_search(timeout=300):  # 5 минут кэширования
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Создаем ключ кэша на основе параметров поиска
            cache_key = f"{request.method}_{request.path}_{str(dict(request.args))}_{str(dict(request.form))}"
            cache_key = hash(cache_key)

            # Проверяем кэш
            if cache_key in search_cache:
                cached_result = search_cache[cache_key]
                if time.time() - cached_result['timestamp'] < timeout:
                    logger.info(f"Возвращен результат из кэша для ключа {cache_key}")
                    return cached_result['response']

            # Выполняем функцию
            result = func(*args, **kwargs)

            # Сохраняем в кэш
            search_cache[cache_key] = {
                'response': result,
                'timestamp': time.time()
            }

            # Очищаем старые записи кэша
            current_time = time.time()
            expired_keys = [k for k, v in search_cache.items()
                          if current_time - v['timestamp'] > timeout]
            for key in expired_keys:
                del search_cache[key]

            return result
        return wrapper
    return decorator

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/search', methods=['GET', 'POST'])
@cache_search(timeout=300)  # Кэширование на 5 минут
def search():
    """Страница поиска с улучшенной обработкой"""
    global search_results

    # Обработка GET запросов с параметрами (для быстрого поиска)
    if request.method == 'GET' and request.args:
        product = request.args.get('product', '').strip()
        region = request.args.get('region', '').strip()
        quantity = request.args.get('quantity', 'опт').strip()

        if product and region:
            try:
                logger.info(f"Начат быстрый поиск: продукт='{product}', регион='{region}', количество='{quantity}'")

                # Выполняем поиск синхронно
                finder = BusinessSupplierFinder()
                suppliers = finder.search_suppliers(product, region, quantity)
                finder.close_driver()

                search_results = suppliers

                # Сохраняем результаты в JSON
                search_data = {
                    'timestamp': datetime.now().isoformat(),
                    'product': product,
                    'region': region,
                    'quantity': quantity,
                    'suppliers_count': len(suppliers),
                    'suppliers': suppliers
                }

                filename = f"web_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(search_data, f, ensure_ascii=False, indent=2)

                logger.info(f"Быстрый поиск завершен успешно. Найдено {len(suppliers)} поставщиков")

                # Перенаправляем на страницу результатов
                return redirect(url_for('show_results'))

            except Exception as e:
                logger.error(f"Ошибка при быстром поиске: {str(e)}", exc_info=True)
                return render_template('search.html', error=f"Ошибка при поиске: {str(e)}")

    if request.method == 'POST':
        product = request.form.get('product', '').strip()
        region = request.form.get('region', '').strip()
        quantity = request.form.get('quantity', '').strip()

        if not product or not region:
            return render_template('search.html', error="Товар и регион обязательны!")

        try:
            logger.info(f"Начат поиск: продукт='{product}', регион='{region}', количество='{quantity}'")

            # Выполняем поиск синхронно с прогрессом
            finder = BusinessSupplierFinder()
            suppliers = finder.search_suppliers(product, region, quantity)
            finder.close_driver()

            search_results = suppliers

            # Сохраняем результаты в JSON
            search_data = {
                'timestamp': datetime.now().isoformat(),
                'product': product,
                'region': region,
                'quantity': quantity,
                'suppliers_count': len(suppliers),
                'suppliers': suppliers
            }

            filename = f"web_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(search_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Поиск завершен успешно. Найдено {len(suppliers)} поставщиков")

            # Перенаправляем на страницу результатов
            return redirect(url_for('show_results'))

        except Exception as e:
            logger.error(f"Ошибка при поиске: {str(e)}", exc_info=True)
            return render_template('search.html', error=f"Ошибка при поиске: {str(e)}")

    return render_template('search.html')

# Функция для выполнения поиска с прогрессом (упрощенная версия)

# API endpoints для AJAX запросов

@app.route('/quick_search')
def quick_search():
    """Быстрый поиск"""
    return render_template('quick_search.html')


@app.route('/search_progress')
def search_progress():
    """Демо UI прогресса поиска (рендер без Socket.IO на сервере)."""
    return render_template(
        'search_progress.html',
        product=request.args.get('product', 'Демо-товар'),
        region=request.args.get('region', 'Демо-регион'),
        quantity=request.args.get('quantity', 'опт'),
        search_id=request.args.get('search_id', '').strip() or str(uuid.uuid4()),
    )

@app.route('/api/quick_search/<search_type>')
def api_quick_search(search_type):
    """API для быстрого поиска"""
    global search_results
    
    quick_searches = {
        'grohe': {
            'product': 'Grohe',
            'region': 'Ставрополь',
            'quantity': 'опт'
        },
        'metal': {
            'product': 'металлопрокат',
            'region': 'Ставрополь',
            'quantity': 'опт'
        },
        'plumbing': {
            'product': 'сантехника',
            'region': 'Ставрополь',
            'quantity': 'опт'
        }
    }
    
    if search_type not in quick_searches:
        return api_error("unknown_search_type", "Неизвестный тип поиска", 400)
    
    search_data = quick_searches[search_type]
    
    try:
        finder = BusinessSupplierFinder()
        suppliers = finder.search_suppliers(
            search_data['product'],
            search_data['region'],
            search_data['quantity']
        )
        finder.close_driver()
        
        search_results = suppliers
        
        return jsonify({
            'success': True,
            'suppliers': suppliers,
            'product': search_data['product'],
            'region': search_data['region'],
            'quantity': search_data['quantity']
        })
        
    except Exception as e:
        return api_error("quick_search_failed", str(e), 500)

@app.route('/results')
def show_results():
    """Показать результаты поиска"""
    global search_results
    return render_template('results.html',
                        suppliers=search_results,
                        product="Результаты поиска",
                        region="",
                        quantity="")

@app.route('/export')
def export_results():
    """Экспорт результатов"""
    global search_results
    
    if not search_results:
        return redirect(url_for('search'))
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"business_suppliers_export_{timestamp}.txt"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"Экспорт результатов поиска бизнес-поставщиков\n")
            f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")
            
            for i, supplier in enumerate(search_results, 1):
                f.write(f"{i}. {supplier['name']}\n")
                f.write(f"   Телефон: {supplier.get('phone', 'Не указан')}\n")
                f.write(f"   Email: {supplier.get('email', 'Не указан')}\n")
                f.write(f"   Сайт: {supplier.get('website', 'Не указан')}\n")
                f.write(f"   Релевантность: {supplier.get('relevance_score', 0)}\n")
                f.write(f"   Бизнес-поставщик: {'Да' if supplier.get('is_business') else 'Нет'}\n")
                f.write(f"   Источник: {supplier.get('source', 'Неизвестно')}\n")
                if supplier.get('description'):
                    f.write(f"   Описание: {supplier['description']}\n")
                f.write("\n")
        
        return jsonify({'success': True, 'filename': filename})
        
    except Exception as e:
        return api_error("export_failed", str(e), 500)

@app.route('/saved_searches')
def saved_searches():
    """Сохраненные поиски"""
    import glob
    
    json_files = glob.glob("web_search_*.json")
    searches = []
    
    for filename in json_files[:10]:  # Последние 10 поисков
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                searches.append({
                    'filename': filename,
                    'product': data['product'],
                    'region': data['region'],
                    'quantity': data['quantity'],
                    'suppliers_count': data['suppliers_count'],
                    'timestamp': data['timestamp'][:19]
                })
        except Exception as e:
            continue
    
    return render_template('saved_searches.html', searches=searches)

def _safe_saved_search_path(filename: str) -> Optional[Path]:
    """Только файлы web_search_*.json в текущей рабочей директории (без path traversal)."""
    name = Path(filename).name
    if not name.startswith("web_search_") or not name.endswith(".json"):
        return None
    root = Path.cwd().resolve()
    path = (root / name).resolve()
    if path.parent != root or not path.is_file():
        return None
    return path


@app.route('/api/saved_search/<filename>')
def api_saved_search(filename):
    """API для загрузки сохраненного поиска"""
    path = _safe_saved_search_path(filename)
    if path is None:
        return api_error("invalid_filename", "Недопустимое имя файла", 400)
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        
        global search_results
        search_results = data['suppliers']
        
        return jsonify({
            'success': True,
            'suppliers': data['suppliers'],
            'product': data['product'],
            'region': data['region'],
            'quantity': data['quantity']
        })
        
    except Exception as e:
        return api_error("saved_search_read_failed", str(e), 500)

# ================================
# REST API ENDPOINTS
# ================================

@app.route('/api/v1/search', methods=['POST'])
def api_search():
    """REST API для поиска поставщиков (состояние задачи в SQLite, см. api_search_jobs)."""
    try:
        data = request.get_json()

        if not data:
            return api_error("bad_request", "Тело запроса должно быть JSON", 400)

        product = data.get('product', '').strip()
        region = data.get('region', '').strip()
        quantity = data.get('quantity', '')

        if not product:
            return api_error("validation_error", "Поле product обязательно", 400)

        search_id = str(uuid.uuid4())

        logger.info(f"🔍 API поиск [{search_id}]: {product}, регион: {region}, количество: {quantity}")

        repo_start = SearchJobRepository()
        try:
            repo_start.create_job(search_id, product, region, quantity or "")
        except Exception as e:
            logger.error(f"❌ Не удалось записать задачу поиска: {e}", exc_info=True)
            return api_error("internal_error", "Не удалось создать задачу поиска", 500)
        finally:
            repo_start.close()

        if not enqueue_api_search(search_id, product, region, quantity or ""):

            def perform_search():
                repo = SearchJobRepository()
                try:
                    finder = BusinessSupplierFinder()
                    suppliers = finder.search_business_suppliers(product, region, quantity)
                    payload = {
                        'suppliers': suppliers,
                        'product': product,
                        'region': region,
                        'quantity': quantity,
                        'completed_at': datetime.now().isoformat(),
                        'total': len(suppliers),
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

            thread = threading.Thread(target=perform_search)
            thread.daemon = True
            thread.start()

        return jsonify({
            'success': True,
            'search_id': search_id,
            'status': 'accepted',
            'message': 'Поиск запущен в фоне',
            'estimated_time': '30-120 секунд'
        })

    except Exception as e:
        logger.error(f"❌ Ошибка API поиска: {str(e)}", exc_info=True)
        return api_error("internal_error", "Внутренняя ошибка сервера", 500)

@app.route('/api/v1/search/<search_id>', methods=['GET'])
def api_get_search_results(search_id):
    """Статус и результат фонового поиска по search_id (хранение в api_search_jobs)."""
    try:
        repo = SearchJobRepository()
        try:
            job = repo.get(search_id)
        finally:
            repo.close()

        if not job:
            return api_error("not_found", "Задача поиска не найдена", 404)

        st = job.get("status") or ""
        if st == "in_progress":
            return jsonify({
                'status': 'in_progress',
                'search_id': search_id,
                'message': 'Поиск ещё выполняется'
            })
        if st == "failed":
            return jsonify({
                'status': 'failed',
                'search_id': search_id,
                'error': {
                    'code': 'search_failed',
                    'message': 'Ошибка при выполнении поиска',
                }
            })

        if st == "completed":
            data = job.get("_result") or {}
            return jsonify({
                'status': 'completed',
                'search_id': search_id,
                'data': data
            })

        return api_error("invalid_state", "Неизвестное состояние задачи", 500)

    except Exception as e:
        logger.error(f"❌ Ошибка получения результатов поиска: {str(e)}", exc_info=True)
        return api_error("internal_error", "Внутренняя ошибка сервера", 500)

@app.route('/api/v1/suppliers', methods=['GET'])
def api_get_suppliers():
    """
    Поставщики из результата поиска.

    Query ``search_id`` — UUID задачи POST /api/v1/search (рекомендуется для REST).
    Без ``search_id`` — глобальный ``search_results`` (последний поиск через UI/legacy).
    """
    try:
        global search_results

        company_type = request.args.get('type')
        min_score = request.args.get('min_score')
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        job_search_id = (request.args.get('search_id') or '').strip()

        if job_search_id:
            repo = SearchJobRepository()
            try:
                job = repo.get(job_search_id)
            finally:
                repo.close()
            if not job or job.get('status') != 'completed':
                return api_error(
                    "not_found",
                    "Нет завершённой задачи поиска с таким search_id",
                    404,
                )
            result = job.get('_result') or {}
            suppliers = list(result.get('suppliers') or [])
        else:
            suppliers = search_results.copy()

        # Применяем фильтры
        if company_type:
            suppliers = [s for s in suppliers if s.get('company_type') == company_type]

        if min_score:
            try:
                min_score_int = int(min_score)
                suppliers = [s for s in suppliers if s.get('relevance_score', 0) >= min_score_int]
            except ValueError:
                pass

        # Пагинация
        total = len(suppliers)
        suppliers = suppliers[offset:offset + limit]

        return jsonify({
            'success': True,
            'data': {
                'suppliers': suppliers,
                'total': total,
                'limit': limit,
                'offset': offset
            }
        })

    except Exception as e:
        logger.error(f"❌ Ошибка получения поставщиков: {str(e)}", exc_info=True)
        return api_error("internal_error", "Внутренняя ошибка сервера", 500)

@app.route('/api/v1/stats', methods=['GET'])
def api_get_stats():
    """Получить статистику приложения"""
    try:
        global search_results, search_cache

        # Статистика по типам компаний
        company_types = {}
        total_score = 0
        total_contacts = 0

        for supplier in search_results:
            company_type = supplier.get('company_type', 'UNKNOWN')
            company_types[company_type] = company_types.get(company_type, 0) + 1

            total_score += supplier.get('relevance_score', 0)
            total_contacts += supplier.get('contact_completeness', 0)

        avg_score = total_score / len(search_results) if search_results else 0
        avg_contacts = total_contacts / len(search_results) if search_results else 0

        repo = SearchJobRepository()
        try:
            job_counts = repo.counts_by_status()
        finally:
            repo.close()

        return jsonify({
            'success': True,
            'stats': {
                'total_suppliers': len(search_results),
                'http_cache_entries': len(search_cache),
                'api_search_jobs': {
                    'in_progress': job_counts.get('in_progress', 0),
                    'completed': job_counts.get('completed', 0),
                    'failed': job_counts.get('failed', 0),
                },
                'company_types': company_types,
                'average_score': round(avg_score, 1),
                'average_contacts': round(avg_contacts, 1),
                'timestamp': datetime.now().isoformat()
            }
        })

    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики: {str(e)}", exc_info=True)
        return api_error("internal_error", "Внутренняя ошибка сервера", 500)

def _redis_tcp_reachable(redis_url: str, timeout_sec: float = 1.0) -> bool:
    """TCP-доступность Redis по REDIS_URL (без redis-клиента)."""
    try:
        parsed = urlparse(redis_url.strip())
        host = parsed.hostname
        if not host:
            return False
        port = parsed.port if parsed.port is not None else 6379
        with socket.create_connection((host, port), timeout=timeout_sec):
            pass
        return True
    except OSError:
        return False


@app.route('/api/v1/health', methods=['GET'])
def api_health_check():
    """Проверка здоровья приложения"""
    services = {
        'perplexity_ai': OPENAI_AVAILABLE and PERPLEXITY_CONFIG['enabled'],
        'web_scraping': True,
        'caching': True,
    }
    # Если REDIS_URL не задан — ключ redis в services не добавляем (опциональная проверка для ops).
    redis_url = (os.getenv('REDIS_URL') or '').strip()
    if redis_url:
        services['redis'] = _redis_tcp_reachable(redis_url)
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '2.3',
        'services': services,
    })

@app.route('/api/v1/config', methods=['GET'])
def api_get_config():
    """Получить конфигурацию приложения (без чувствительных данных)"""
    return jsonify({
        'version': '2.3',
        'features': {
            'perplexity_ai': OPENAI_AVAILABLE and PERPLEXITY_CONFIG['enabled'],
            'multiple_sources': True,
            'advanced_scoring': True,
            'caching': True,
            'export': True
        },
        'sources': [
            'Google Search',
            'Yandex Search',
            'Yandex Maps',
            '2GIS',
            'Business Catalogs',
            'Perplexity AI'
        ]
    })

# ================================
# ERROR HANDLERS
# ================================

def _wants_unified_api_error() -> bool:
    """JSON-формат ошибок для /api/* или когда Accept явно предпочитает application/json."""
    if request.path.startswith("/api/"):
        return True
    am = request.accept_mimetypes
    return am["application/json"] > am["text/html"]


@app.errorhandler(404)
def not_found(error):
    if _wants_unified_api_error():
        return api_error("not_found", "Endpoint not found", 404)
    if isinstance(error, HTTPException):
        return error.get_response()
    return NotFound().get_response()


@app.errorhandler(500)
def internal_error(error):
    if _wants_unified_api_error():
        return api_error("internal_error", "Internal server error", 500)
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Создаем папку для шаблонов если её нет
    if not os.path.exists('templates'):
        os.makedirs('templates')

    # Получаем настройки из переменных окружения
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    host = os.getenv('FLASK_HOST', '0.0.0.0')  # nosec B104
    port = int(os.getenv('FLASK_PORT', 5000))

    logger.info("🚀 Запуск улучшенного веб-приложения для поиска бизнес-поставщиков")
    logger.info(f"📱 Откройте браузер и перейдите по адресу: http://{host}:{port}")
    logger.info(f"💾 Кэширование результатов: ВКЛЮЧЕНО")
    logger.info(f"🔍 Улучшенные алгоритмы поиска: ВКЛЮЧЕНЫ")
    logger.info(f"📊 Продвинутая фильтрация: ВКЛЮЧЕНА")
    logger.info(f"🐛 Режим отладки: {debug_mode}")

    # Запуск Flask приложения
    app.run(debug=debug_mode, host=host, port=port) 