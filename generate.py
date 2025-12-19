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
        print(f"⚠️ Firebase ошибка: {e}")
else:
    print("⚠️ FIREBASE_KEY пустой")

# Папка для результата
OUTPUT_DIR = 'public'
if os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- ДАННЫЕ ---
def get_all_data():
    if USE_FIREBASE:
        try:
            products = db.collection('products').stream()
            data = {'products': [doc.to_dict() for doc in products]}
            categories = db.collection('categories').stream()
            data['categories'] = [doc.to_dict() for doc in categories]
            print(f"✅ Firebase: {len(data['products'])} продуктов")
            return data
        except Exception as e:
            print(f"❌ Firebase: {e}")
    
    print("✅ Тестовые данные")
    return {
        'products': [
            {'title': 'Minankari Pendant', 'price': '250', 'slug': 'pendant', 'images': ['placeholder.jpg']},
            {'title': 'Enamel Ring', 'price': '180', 'slug': 'ring', 'images': ['placeholder.jpg']}
        ],
        'categories': [{'name': 'Pendants'}]
    }

# --- ГЛАВНАЯ со ВСЕМИ продуктами ---
def generate_home(data):
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            html = f.read()
        
        products_html = ''
        for i, product in enumerate(data['products']):
            slug = product.get('slug', product['title'].lower().replace(' ', '-'))
            title = product.get('title', 'Product')
            price = product.get('price', 'Price')
            
            images_html = '<img src="placeholder.jpg" class="slideshow-item">'
            if product.get('images'):
                images_html = ''.join([f'<img src="{img}" class="slideshow-item">' for img in product['images']])
            
            products_html += f'''
<div class="product-card" style="--delay: {i}">
    <div class="slideshow-container">
        <div class="product-image-container">{images_html}</div>
        <div class="slideshow-overlay"></div>
    </div>
    <div class="product-info">
        <h3 class="product-title">{title}</h3>
        <p class="product-price">${price}</p>
        <a href="product.html?slug={slug}" class="gold-button">Подробнее</a>
    </div>
</div>'''
        
        target = '<div class="products-grid" id="products-container"></div>'
        html = html.replace(target, f'<div class="products-grid" id="products-container">{products_html}</div>')
        
        with open(f'{OUTPUT_DIR}/index.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("✅ Главная с продуктами!")
    except Exception as e:
        print(f"❌ Главная: {e}")

# --- product.html с JavaScript для ?slug= ---
def generate_product_template(data):
    try:
        # Преобразуем список продуктов в JSON строку для вставки в JavaScript
        products_json = json.dumps(data['products'])
        
        html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Minankari Jewelry</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <!-- ТВОЙ НАВИГАЦИОННЫЙ МЕНЮ ЗДЕСЬ (скопировать из index.html) -->
    
    <div class="product-detail">
        <div id="product-info">
            <h1 id="product-title">Загрузка...</h1>
            <p id="product-price">$0</p>
            <div class="slideshow-container">
                <div class="product-image-container" id="product-images"></div>
            </div>
            <button class="gold-button">Купить</button>
        </div>
    </div>

    <script>
        const products = {products_json};
        const urlParams = new URLSearchParams(window.location.search);
        const slug = urlParams.get('slug');
        
        const product = products.find(p => p.slug === slug || (p.title && p.title.toLowerCase().includes(slug)));
        if (product) {{
            document.getElementById('product-title').textContent = product.title;
            document.getElementById('product-price').textContent = '$' + product.price;
            
            const imagesDiv = document.getElementById('product-images');
            if (product.images && product.images.length > 0) {{
                imagesDiv.innerHTML = product.images.map(img => 
                    `<img src="${{img}}" class="slideshow-item">`
                ).join('');
            }} else {{
                imagesDiv.innerHTML = '<img src="placeholder.jpg" class="slideshow-item">';
            }}
        }}
    </script>
    <script src="script.js"></script>
</body>
</html>'''
        
        with open(f'{OUTPUT_DIR}/product.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("✅ product.html готов!")
    except Exception as e:
        print(f"❌ product.html: {e}")

# --- КОПИРОВАНИЕ ВСЕГО ---
def copy_assets():
    exclude = ['.git', OUTPUT_DIR, 'generate.py', 'index.html'] # index.html теперь генерируется
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
            except Exception:
                pass
    print("✅ Ассеты скопированы")

# --- ЗАПУСК ---
def main():
    print("🚀 Генерация minankari.art")
    data = get_all_data()
    generate_home(data)
    generate_product_template(data)
    copy_assets()
    # Строка ниже была исправлена
    print("\n🎉 ГОТОВО!")
    print("🔗 https://Ramashery.github.io/Jewelry/ ← 34 продукта!")
    print("🔗 product.html?slug=pendant ← детальная страница")

if __name__ == '__main__':
    main()
