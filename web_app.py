#!/usr/bin/env python3
"""
Улучшенное веб-приложение для поиска бизнес-поставщиков
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, Response
from business_supplier_finder import BusinessSupplierFinder
import json
import logging
import threading
from datetime import datetime
import os
from dotenv import load_dotenv
from functools import wraps
import time

# Загружаем переменные окружения
load_dotenv()

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

# Глобальные переменные для хранения результатов поиска
search_results = []
active_searches = {}  # Словарь для отслеживания активных поисков
search_cache = {}     # Кэш результатов поиска

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
        return jsonify({'error': 'Неизвестный тип поиска'})
    
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
        return jsonify({'error': str(e)})

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
        return jsonify({'error': str(e)})

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

@app.route('/api/saved_search/<filename>')
def api_saved_search(filename):
    """API для загрузки сохраненного поиска"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
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
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    # Создаем папку для шаблонов если её нет
    if not os.path.exists('templates'):
        os.makedirs('templates')

    # Получаем настройки из переменных окружения
    debug_mode = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))

    logger.info("🚀 Запуск улучшенного веб-приложения для поиска бизнес-поставщиков")
    logger.info(f"📱 Откройте браузер и перейдите по адресу: http://{host}:{port}")
    logger.info(f"💾 Кэширование результатов: ВКЛЮЧЕНО")
    logger.info(f"🔍 Улучшенные алгоритмы поиска: ВКЛЮЧЕНЫ")
    logger.info(f"📊 Продвинутая фильтрация: ВКЛЮЧЕНА")
    logger.info(f"🐛 Режим отладки: {debug_mode}")

    # Запуск Flask приложения
    app.run(debug=debug_mode, host=host, port=port) 