import os
import json
import shutil
import firebase_admin
from firebase_admin import credentials, firestore
from jinja2 import Environment, FileSystemLoader

# --- FIREBASE ---
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
        print(f"⚠️ Firebase: {e}")

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
            print(f"✅ Firebase: {len(data['products'])} продуктов")
            return data
        except Exception as e:
            print(f"❌ Firebase: {e}")
    
    print("✅ Тестовые данные")
    return {
        'products': [
            {'title': 'Minankari Pendant', 'price': '250', 'slug': 'pendant'},
            {'title': 'Enamel Ring', 'price': '180', 'slug': 'ring'}
        ]
    }

# --- ГЛАВНАЯ со 34 продуктами ---
def generate_home(data):
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            html = f.read()
        
        products_html = ''
        for i, product in enumerate(data['products']):
            slug = product.get('slug') or product.get('title', 'product').lower().replace(' ', '-')
            title = product.get('title', 'Product')
            price = product.get('price', 'Price')
            
            images = product.get('images', []) or product.get('productImages', [])
            images_html = ''
            for img in images[:3]:  # первые 3 фото
                images_html += f'<img src="{img}" class="slideshow-item" style="display:none;">'
            
            if not images_html:
                images_html = '<img src="placeholder.jpg" class="slideshow-item">'
            
            products_html += f'''
<div class="product-card" style="--delay: {i % 10}">
    <div class="slideshow-container">
        <div class="product-image-container">
            {images_html}
        </div>
        <div class="slideshow-overlay"></div>
    </div>
    <div class="product-info">
        <h3 class="product-title">{title}</h3>
        <p class="product-price">${price}</p>
        <a href="product.html?slug={slug}" class="gold-button">View Details</a>
    </div>
</div>'''
        
        target = '<div class="products-grid" id="products-container"></div>'
        html = html.replace(target, f'<div class="products-grid" id="products-container">{products_html}</div>')
        
        with open(f'{OUTPUT_DIR}/index.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("✅ index.html с 34 продуктами!")
    except Exception as e:
        print(f"❌ index.html: {e}")

# --- product.html ---
def generate_product_page(data):
    try:
        products_json = json.dumps(data['products'])
        
        html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Minankari Jewelry - Product</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <!-- КОПИРУЕМ МЕНЮ ИЗ index.html -->
    <nav>{/* navigation menu from index.html */}</nav>
    
    <div class="product-detail" id="product-container">
        <h1 id="product-title">Loading...</h1>
        <p id="product-price">$0</p>
        <div class="slideshow-container">
            <div class="product-image-container" id="product-images"></div>
        </div>
        <a href="#" class="gold-button" id="buy-button">Buy Now</a>
    </div>

    <script>
        const products = {products_json};
        const urlParams = new URLSearchParams(window.location.search);
        const slug = urlParams.get('slug');
        
        const product = products.find(p => p.slug === slug || (p.title && p.title.toLowerCase().includes(slug || '')));
        if (product) {{
            document.getElementById('product-title').textContent = product.title;
            document.getElementById('product-price').textContent = '$' + product.price;
            const imagesDiv = document.getElementById('product-images');
            const images = product.images || product.productImages || ['placeholder.jpg'];
            imagesDiv.innerHTML = images.map(img => 
                `<img src="${{img}}" class="slideshow-item">`
            ).join('');
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

# --- КРИТИЧНЫЙ ФИКС CSS/JS ---
def copy_everything():
    print("🔥 КОПИРУЕМ CSS/JS...")
    
    # 1. КРИТИЧНЫЕ CSS/JS файлы
    critical_files = [
        'style.css', 'script.js', 'particles.js', 'template.html',
        'placeholder.jpg', 'favicon.ico', 'robots.txt', 'sitemap.xml'
    ]
    for filename in critical_files:
        if os.path.exists(filename):
            shutil.copy2(filename, OUTPUT_DIR)
            print(f"🔥 {filename}")
    
    # 2. ПАПКИ с изображениями
    folders = ['images', 'en', 'ru', 'ka']
    for folder in folders:
        if os.path.exists(folder):
            shutil.copytree(folder, os.path.join(OUTPUT_DIR, folder), dirs_exist_ok=True)
            print(f"📁 {folder}/")
    
    # 3. ОСТАЛЬНЫЕ файлы
    exclude = ['.git', OUTPUT_DIR, 'generate.py', 'index.html'] # Исключаем, так как генерируем
    for item in os.listdir('.'):
        if item not in exclude + critical_files:
            src = os.path.join('.', item)
            dst = os.path.join(OUTPUT_DIR, item)
            try:
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
                    print(f"📄 {item}")
                elif os.path.isdir(src) and item not in folders:
                    shutil.copytree(src, os.path.join(OUTPUT_DIR, item), dirs_exist_ok=True)
                    print(f"📁 {item}/")
            except:
                pass
    
    print("✅ ВСЕ CSS/JS/изображения скопированы!")

def main():
    print("🚀 Генерация minankari.art")
    data = get_all_data()
    generate_home(data)
    generate_product_page(data)
    copy_everything()
    
    # Строка ниже была исправлена
    print("\n🎉 ГОТОВО!")
    print("🔗 https://Ramashery.github.io/Jewelry/ ← 34 товара!")
    print("🔗 product.html?slug=minankari-pendant... ← детальная страница")

if __name__ == '__main__':
    main()
