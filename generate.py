import os
import json
import shutil
import firebase_admin
from firebase_admin import credentials, firestore
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

try:
    service_account_info = json.loads(os.environ.get('FIREBASE_SERVICE_ACCOUNT'))
    cred = credentials.Certificate(service_account_info)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase подключен")
except Exception as e:
    print(f"❌ Firebase ошибка: {e}")
    exit(1)

env = Environment(loader=FileSystemLoader('.'))
template = env.get_template('template.html')

OUTPUT_DIR = 'public'
if os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_all_data():
    data = {}
    try:
        products = db.collection('products').stream()
        data['products'] = [doc.to_dict() for doc in products]
        
        categories = db.collection('categories').stream()
        data['categories'] = [doc.to_dict() for doc in categories]
        
        home_doc = db.collection('home').document('content').get()
        data['home'] = home_doc.to_dict() if home_doc.exists else {}
        
        print(f"✅ Загружено: {len(data['products'])} продуктов, {len(data['categories'])} категорий")
        return data
    except Exception as e:
        print(f"❌ Ошибка загрузки данных: {e}")
        return None

def generate_home_with_products(data):
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            html = f.read()
        
        products_html = ''
        for i, product in enumerate(data['products']):
            slug = product.get('slug') or product.get('title', 'product').lower().replace(' ', '-').replace(',', '').replace('/', '').replace("'", "")
            
            images = product.get('images', []) or product.get('productImages', [])
            images_html = ''
            for img in images:
                images_html += f'<img src="{img}" class="slideshow-item" style="display:none;">\n'
            
            card_html = f'<div class="product-card" style="--delay: {i}"><div class="slideshow-container"><div class="product-image-container">{images_html}</div><div class="slideshow-overlay"></div></div><div class="product-info"><h3 class="product-title">{product.get("title", "Product")}</h3><p class="product-price">${product.get("price", "Price")}</p><a href="product.html?slug={slug}" class="gold-button">View Details</a></div></div>'
            products_html += card_html
        
        html = html.replace(
            '<div class="products-grid" id="products-container"></div>',
            f'<div class="products-grid" id="products-container">{products_html}</div>'
        )
        
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

def main():
    print("🚀 Генерация minankari.art")
    
    data = get_all_data()
    if not data:
        print("❌ Нет данных. Проверь Firebase: products, categories")
        return
    
    generate_home_with_products(data)
    generate_product_page(data)
    copy_assets()
    
    print("🎉 ГОТОВО! Загружай public/ на Netlify")

if __name__ == '__main__':
    main()
