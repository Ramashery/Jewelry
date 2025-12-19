import os
import json
import shutil
import firebase_admin
from firebase_admin import credentials, firestore
from jinja2 import Environment, FileSystemLoader

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

def get_all_data():
    if USE_FIREBASE:
        try:
            products = db.collection('products').stream()
            data = {'products': [doc.to_dict() for doc in products]}
            print(f"✅ Firebase: {len(data['products'])} продуктов")
            return data
        except Exception as e:
            print(f"❌ Firebase: {e}")
    
    return {'products': [
        {'title': 'Test Pendant', 'price': '250', 'slug': 'test-pendant', 'images': []}
    ]}

def generate_home(data):
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            html = f.read()
        
        products_html = ''
        for i, product in enumerate(data['products']):
            slug = product.get('slug') or 'product'
            title = product.get('title', 'Product')
            price = product.get('price', 'Price')
            
            # ПРОСТАЯ КАРТОЧКА (без сложного HTML)
            products_html += f'''
<div class="product-card">
    <img src="placeholder.jpg" alt="{title}">
    <h3>{title}</h3>
    <p>${price}</p>
    <a href="product.html?slug={slug}">Подробнее</a>
</div>'''
        
        # ЗАМЕНА
        target = '<div class="products-grid" id="products-container"></div>'
        html = html.replace(target, f'<div class="products-grid">{products_html}</div>')
        
        # ✅ НЕ УДАЛЯЕМ Firebase скрипты!
        with open(f'{OUTPUT_DIR}/index.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("✅ index.html готов!")
    except Exception as e:
        print(f"❌ index.html: {e}")

def generate_product():
    try:
        html = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Product</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <h1>Детальная страница товара</h1>
    <p>Смотри ?slug= в URL</p>
    <script src="script.js"></script>
</body>
</html>'''
        with open(f'{OUTPUT_DIR}/product.html', 'w') as f:
            f.write(html)
        print("✅ product.html готов!")
    except Exception as e:
        print(f"❌ product.html: {e}")

def copy_everything():
    # Исключаем index.html, так как мы его генерируем
    exclude = ['.git', OUTPUT_DIR, 'generate.py', 'index.html'] 
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
            except:
                pass

def main():
    print("🚀 Генерация...")
    data = get_all_data()
    generate_home(data)
    generate_product()
    copy_everything()
    # Строка ниже была исправлена
    print("\n🎉 ГОТОВО!")
    print("🔗 https://Ramashery.github.io/Jewelry/")

if __name__ == '__main__':
    main()
