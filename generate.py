import os
import json
import shutil
import firebase_admin
from firebase_admin import credentials, firestore
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

# --- БЕЗОПАСНАЯ НАСТРОЙКА FIREBASE ---
firebase_key = os.environ.get('FIREBASE_KEY')
USE_FIREBASE = False

if firebase_key and firebase_key.strip():
    try:
        service_account_info = json.loads(firebase_key)
        cred = credentials.Certificate(service_account_info)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase подключен")
        USE_FIREBASE = True
    except Exception as e:
        print(f"⚠️ Firebase ошибка, использую тестовые данные: {e}")
else:
    print("⚠️ FIREBASE_KEY пустой, использую тестовые данные")

# Jinja из корня
env = Environment(loader=FileSystemLoader('.'))
template = env.get_template('template.html')

# Папка для результата
OUTPUT_DIR = 'public'
if os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- ДАННЫЕ (Firebase ИЛИ тестовые) ---
def get_all_data():
    if USE_FIREBASE:
        data = {}
        try:
            products = db.collection('products').stream()
            data['products'] = [doc.to_dict() for doc in products]
            
            categories = db.collection('categories').stream()
            data['categories'] = [doc.to_dict() for doc in categories]
            
            home_doc = db.collection('home').document('content').get()
            data['home'] = home_doc.to_dict() if home_doc.exists else {}
            
            print(f"✅ Firebase: {len(data['products'])} продуктов, {len(data['categories'])} категорий")
            return data
        except Exception as e:
            print(f"❌ Firebase failed: {e}")
    
    # ТЕСТОВЫЕ ДАННЫЕ
    print("✅ Использую тестовые данные")
    return {
        'products': [
            {
                'title': 'Minankari Pendant Pomegranate',
                'price': '250',
                'slug': 'minankari-pendant-pomegranate-handmade-sterling-silver-artisan-from-tbilisi',
                'images': ['https://via.placeholder.com/400x300/D4AF37/FFFFFF?text=Pendant+1']
            },
            {
                'title': 'Enamel Ring Gold',
                'price': '180',
                'slug': 'enamel-ring-gold-minankari-tbilisi',
                'images': ['https://via.placeholder.com/400x300/Gold/FFFFFF?text=Ring']
            }
        ],
        'categories': [{'name': 'Pendants'}, {'name': 'Rings'}],
        'home': {}
    }

# --- ГЛАВНАЯ СТРАНИЦА со ВСЕМИ продуктами (ОТЛАДКА) ---
def generate_home_with_products(data):
    try:
        print("📂 Читаю index.html...")
        with open('index.html', 'r', encoding='utf-8') as f:
            html = f.read()
        
        # ОТЛАДКА: ищем контейнер продуктов
        target_string = '<div class="products-grid" id="products-container"></div>'
        print(f"🔍 Ищу строку: '{target_string}'")
        print(f"📏 Длина index.html: {len(html)} символов")
        
        if target_string in html:
            print("✅ Контейнер найден!")
        else:
            print("❌ Контейнер НЕ найден!")
            print("🔍 Ищу похожие строки:")
            # Строка ниже была исправлена
            for line in html.split('\n'):
                if 'products-grid' in line or 'products-container' in line:
                    print(f"  → '{line.strip()}'")
        
        # Создаём продукты
        print(f"📦 Создаю {len(data['products'])} продуктов...")
        products_html = ''
        for i, product in enumerate(data['products']):
            slug = product.get('slug') or product.get('title', 'product').lower().replace(' ', '-').replace(',', '').replace('/', '').replace("'", "")
            print(f"  📦 Продукт {i}: {product.get('title', 'Unknown')} → slug={slug}")
            
            images = product.get('images', [])
            images_html = ''
            for img in images:
                # Строка ниже была исправлена
                images_html += f'<img src="{img}" class="slideshow-item" style="display:none;">\n'
            
            card_html = f'<div class="product-card" style="--delay: {i}"><div class="slideshow-container"><div class="product-image-container">{images_html}</div><div class="slideshow-overlay"></div></div><div class="product-info"><h3 class="product-title">{product.get("title", "Product")}</h3><p class="product-price">${product.get("price", "Price")}</p><a href="product.html?slug={slug}" class="gold-button">View Details</a></div></div>'
            products_html += card_html
        
        print(f"📦 Готово HTML продуктов: {len(products_html)} символов")
        
        # Заменяем контейнер
        new_content = f'<div class="products-grid" id="products-container">{products_html}</div>'
        old_count = html.count(target_string)
        html = html.replace(target_string, new_content)
        new_count = html.count(target_string)
        print(f"🔄 Заменил: {old_count - new_count} контейнеров")
        
        # Удаляем Firebase
        firebase_scripts = [
            '<script src="https://www.gstatic.com/firebasejs/8.10.1/firebase-firestore.js"></script>',
            '<script src="https://www.gstatic.com/firebasejs/8.10.1/firebase-auth.js"></script>',
            '<script src="https://www.gstatic.com/firebasejs/8.10.1/firebase-app.js"></script>'
        ]
        for script in firebase_scripts:
            html = html.replace(script, '')
        
        with open(os.path.join(OUTPUT_DIR, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(html)
        print("✅ Главная создана!")
        
        # Проверяем результат
        with open(os.path.join(OUTPUT_DIR, 'index.html'), 'r') as f:
            result = f.read()
        if 'product-card' in result:
            print("🎉 Продукты ВСТАВЛЕНЫ в index.html!")
        else:
            print("❌ Продукты НЕ вставлены!")
            
    except Exception as e:
        print(f"❌ Ошибка главной страницы: {e}")

# --- ОДИН product.html ---
def generate_product_page(data):
    try:
        first_product = data['products'][0] if data['products'] else {}
        slug = first_product.get('slug') or first_product.get('title', 'product').lower().replace(' ', '-')
        
        html = template.render(
            item=first_product,
            page_type='product-detail',
            categories=data['categories'],
            slug=slug
        )
        
        product_path = os.path.join(OUTPUT_DIR, 'product.html')
        with open(product_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"✅ product.html?slug={slug}")
    except Exception as e:
        print(f"❌ Ошибка product.html: {e}")

# --- КОПИРОВАНИЕ АССЕТОВ ---
def copy_assets():
    exclude = ['.git', OUTPUT_DIR, 'generate.py', 'template.html', 'index.html']
    copied = 0
    for item in os.listdir('.'):
        if item not in exclude:
            src = os.path.join('.', item)
            dst = os.path.join(OUTPUT_DIR, item)
            try:
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
                    print(f"📄 {item}")
                    copied += 1
                elif os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                    print(f"📁 {item}/")
                    copied += 1
            except Exception as e:
                print(f"⚠️  {item}: {e}")
    print(f"✅ {copied} ассетов скопировано")

# --- ОСНОВНОЙ ЗАПУСК ---
def main():
    print("🚀 Генерация minankari.art")
    
    data = get_all_data()
    if not data or not data.get('products'):
        print("❌ Нет данных продуктов")
        return
    
    generate_home_with_products(data)
    generate_product_page(data)
    copy_assets()
    
    # Строка ниже была исправлена
    print("\n🎉 ГОТОВО! Загружай public/ на Netlify")
    print("🔗 Проверь: https://Ramashery.github.io/Jewelry/")

if __name__ == '__main__':
    main()
