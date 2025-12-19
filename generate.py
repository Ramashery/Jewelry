import os
import json
import shutil
import firebase_admin
from firebase_admin import credentials, firestore
from jinja2 import Environment, FileSystemLoader

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
            print(f"✅ Firebase: {len(data['products'])} продуктов")
            return data
        except Exception as e:
            print(f"❌ Firebase failed: {e}")
    
    print("✅ Тестовые данные")
    return {
        'products': [
            {'title': 'Minankari Pendant', 'price': '250', 'slug': 'pendant', 'images': []},
            {'title': 'Enamel Ring', 'price': '180', 'slug': 'ring', 'images': []}
        ],
        'categories': [{'name': 'Pendants'}]
    }

# --- ТОЛЬКО index.html со статическими продуктами ---
def generate_static_home(data):
    try:
        # ЧИТАЕМ ОРИГИНАЛЬНЫЙ index.html
        with open('index.html', 'r', encoding='utf-8') as f:
            html = f.read()
        
        # ГЕНЕРИРУЕМ КАРТОЧКИ
        products_html = ''
        for i, product in enumerate(data['products']):
            slug = product.get('slug', 'product')
            title = product.get('title', 'Product')
            price = product.get('price', 'Price')
            
            products_html += f'''
            <div class="product-card" style="--delay: {i}">
                <div class="slideshow-container">
                    <div class="product-image-container">
                        <img src="placeholder.jpg" class="slideshow-item">
                    </div>
                    <div class="slideshow-overlay"></div>
                </div>
                <div class="product-info">
                    <h3 class="product-title">{title}</h3>
                    <p class="product-price">${price}</p>
                    <a href="product.html?slug={slug}" class="gold-button">View Details</a>
                </div>
            </div>'''
        
        # ЗАМЕНАЕМ КОНТЕЙНЕР
        target = '<div class="products-grid" id="products-container"></div>'
        new_content = f'<div class="products-grid" id="products-container">{products_html}</div>'
        html = html.replace(target, new_content)
        
        # СОХРАНЯЕМ КАК index-static.html (НЕ трогаем оригинал!)
        with open(os.path.join(OUTPUT_DIR, 'index-static.html'), 'w', encoding='utf-8') as f:
            f.write(html)
        print("✅ index-static.html с продуктами")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

# --- КОПИРУЕМ ВСЁ ОСТАЛЬНОЕ БЕЗОПАСНО ---
def copy_all_assets():
    exclude = ['.git', OUTPUT_DIR, 'generate.py']
    
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
                print(f"⚠️ {item}: {e}")
    print("✅ ВСЕ ассеты скопированы")

# --- ОСНОВНОЙ ЗАПУСК ---
def main():
    print("🚀 Безопасная генерация minankari.art")
    
    data = get_all_data()
    generate_static_home(data)
    copy_all_assets()
    
    # Строка ниже была исправлена
    print("\n🎉 ГОТОВО!")
    print("🔗 public/index-static.html ← главная со статическими продуктами")
    print("🔗 public/index.html ← оригинал с Firebase (меню работает!)")

if __name__ == '__main__':
    main()
