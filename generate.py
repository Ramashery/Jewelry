import os
import json
import shutil
import firebase_admin
from firebase_admin import credentials, firestore
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

# --- НАСТРОЙКА FIREBASE ---
try:
    service_account_info = json.loads(os.environ.get('FIREBASE_SERVICE_ACCOUNT'))
    cred = credentials.Certificate(service_account_info)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase подключен")
except Exception as e:
    print(f"❌ Firebase ошибка: {e}")
    exit(1)

# Jinja из корня
env = Environment(loader=FileSystemLoader('.'))
template = env.get_template('template.html')

# Папка для результата
OUTPUT_DIR = 'public'
if os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- ЗАГРУЗКА ДАННЫХ ИЗ FIREBASE ---
def get_all_data():
    data = {}
    try:
        # Продукты (основная коллекция)
        products = db.collection('products').stream()
        data['products'] = [doc.to_dict() for doc in products]
        
        # Категории
        categories = db.collection('categories').stream()
        data['categories'] = [doc.to_dict() for doc in categories]
        
        # Home контент (если есть)
        home_doc = db.collection('home').document('content').get()
        data['home'] = home_doc.to_dict() if home_doc.exists else {}
        
        print(f"✅ Загружено: {len(data['products'])} продуктов, {len(data['categories'])} категорий")
        return data
    except Exception as e:
        print(f"❌ Ошибка загрузки данных: {e}")
        return None

# --- ГЛАВНАЯ СТРАНИЦА со ВСЕМИ продуктами (статическая!) ---
def generate_home_with_products(data):
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            html = f.read()
        
        # Генерируем HTML КАРТОЧЕК продуктов для #products-container
        products_html = ''
        for i, product in enumerate(data['products']):
            # Генерируем slug для ссылки
            slug = product.get('slug') or product.get('title', 'product').lower().replace(' ', '-').replace(',', '').replace('/', '').replace("'", "")
            
            images = []
            for img in product.get('images', []) or product.get('productImages', []):
                images.append(f'<img src="{img}" class="slideshow-item" style="display:none">')
            images_html = '
'.join(images)
            
            products_html += f'''
            <div class="product-card" style="--delay: {i}">
                <div class="slideshow-container">
                    <div class="product-image-container">
                        {images_html}
                    </div>
                    <div class="slideshow-overlay"></div>
                </div>
                <div class="product-info">
                    <h3 class="product-title">{product.get("title", "Product")}</h3>
                    <p class="product-price">${product.get("price", "Price")}</p>
                    <a href="product.html?slug={slug}" class="gold-button">View Details</a>
                </div>
            </div>'''
        
        # Вставляем продукты в index.html
        html = html.replace(
            '<div class="products-grid" id="products-container"></div>',
            f'<div class="products-grid" id="products-container">{products_html}</div>'
        )
        
        # Убираем Firebase-скрипты для статической версии
        firebase_scripts = [
            '<script src="https://www.gstatic.com/firebasejs/8.10.1/firebase-firestore.js"></script>',
            '<script src="https://www.gstatic.com/firebasejs/8.10.1/firebase-auth.js"></script>',
            '<script src="https://www.gstatic.com/firebasejs/8.10.1/firebase-app.js"></script>'
        ]
        for script in firebase_scripts:
            html = html.replace(script, '')
        
        with open(os.path.join(OUTPUT_DIR, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(html)
        print("✅ Главная страница со статическими продуктами")
    except Exception as e:
        print(f"❌ Ошибка главной страницы: {e}")

# --- ОДИН product.html для ВСЕХ товаров (?slug=...) ---
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
        print(f"✅ product.html?slug={slug} (шаблон для всех товаров)")
    except Exception as e:
        print(f"❌ Ошибка product.html: {e}")

# --- КОПИРОВАНИЕ АССЕТОВ (CSS/JS/images) ---
def copy_assets():
    exclude = ['.git', OUTPUT_DIR, 'generate.py', 'template.html', 'index.html']
    for item in os.listdir('.'):
        if item not in exclude:
            src = os.path.join('.', item)
            dst = os.path.join(OUTPUT_DIR, item)
            try:
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
                    print(f"📄 {item}")
                elif os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                    print(f"📁 {item}/")
            except Exception as e:
                print(f"⚠️  {item}: {e}")
    print("✅ Все ассеты скопированы")

# --- ОСНОВНОЙ ЗАПУСК ---
def main():
    print("🚀 Генерация minankari.art (статическая версия)")
    
    data = get_all_data()
    if not data:
        print("❌ Нет данных. Проверь Firebase коллекции: products, categories")
        return
    
    generate_home_with_products(data)
    generate_product_page(data)
    copy_assets()
    
    print("
🎉 ГОТОВО!")
    print(f"📂 Загружай ВСЮ папку 'public/' на Netlify")
    print("🔗 Структура:")
    print("   /index.html ← главная со всеми продуктами")
    print("   /product.html?slug=... ← детальная страница товара")

if __name__ == '__main__':
    main()
