# --- ФАЙЛ: generate_site.py (ФИНАЛЬНАЯ ВЕРСИЯ - СОВМЕЩАЕТ ВСЕ ТРЕБОВАНИЯ) ---

import os
import json
import shutil
import re
from jinja2 import Environment, FileSystemLoader
import firebase_admin
from firebase_admin import credentials, firestore

# --- НАСТРОЙКА ---
try:
    service_account_json_str = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
    if not service_account_json_str:
        print("Переменная окружения FIREBASE_SERVICE_ACCOUNT не найдена. Попытка использовать локальный файл 'firebase-key.json'...")
        with open('firebase-key.json', 'r') as f:
            service_account_json_str = f.read()

    service_account_info = json.loads(service_account_json_str)
    
    if not firebase_admin._apps:
        cred = credentials.Certificate(service_account_info)
        firebase_admin.initialize_app(cred)
        
    db = firestore.client()
    print("Успешное подключение к Firebase.")
except Exception as e:
    print(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось подключиться к Firebase. {e}")
    print("Убедитесь, что у вас есть файл 'firebase-key.json' или настроена переменная окружения FIREBASE_SERVICE_ACCOUNT.")
    exit(1)

# --- НАСТРОЙКА JINJA2 ---
env = Environment(loader=FileSystemLoader('.'))

def format_description(text):
    if not text: return ""
    return "".join(f'<p>{p.strip()}</p>' for p in text.strip().split('\n') if p.strip())

env.filters['format_description'] = format_description
# ВАЖНО: Используем template.html, так как он содержит всю логику для генерации
template = env.get_template('template.html') 


# --- ФУНКЦИИ ГЕНЕРАЦИИ ДАННЫХ ---

def generate_schemas(item, all_categories, image_urls):
    base_url = "https://minankari.art"
    # !!! ВОЗВРАЩАЕМ СТАРЫЙ ФОРМАТ URL !!!
    product_url = f"{base_url}/product.html?slug={item.get('slug')}"
    
    text_with_spaces = re.sub('<[^<]+?>', ' ', item.get('description', '')).replace('\n', ' ')
    clean_description = ' '.join(text_with_spaces.split())

    item_category_id = item.get('category')
    category_info = all_categories.get(item_category_id) if item_category_id else None
    category_string = "Jewelry"
    if category_info:
        parent_name = "Cast" if category_info.get('parent') == 'cast' else "Enamel"
        category_name = category_info.get('name', '')
        category_string = f"Jewelry > {parent_name} > {category_name}"

    product_schema = {
        "@type": "Product",
        "name": item.get('title', '').strip(),
        "description": clean_description,
        "sku": item.get('sku', '').strip(),
        "mpn": item.get('sku', '').strip(),
        "image": image_urls,
        "brand": {"@type": "Brand", "name": "Nino Kartsivadze"},
        "manufacturer": {"@type": "Person", "name": "Nino Kartsivadze"},
        "url": product_url,
        "category": category_string
    }
    
    if item.get('material'):
        product_schema['material'] = item.get('material').strip()
    if item.get('additionalProperties'):
        product_schema['additionalProperty'] = item.get('additionalProperties')
        
    price_str = str(item.get('price', '')).replace('$', '').replace(',', '').strip()
    if price_str:
        try:
            price_val = float(price_str)
            product_schema['offers'] = {
                "@type": "Offer",
                "url": product_url,
                "priceCurrency": "USD",
                "price": f"{price_val:.2f}",
                "itemCondition": "https://schema.org/NewCondition",
                "availability": f"https://schema.org/{item.get('availability', 'InStock')}",
                "seller": {"@type": "Person", "name": "Nino Kartsivadze"}
            }
        except (ValueError, TypeError):
            pass

    item_list = [{"@type": "ListItem", "position": 1, "name": "Home", "item": f"{base_url}/"}]
    parent_type = category_info.get('parent') if category_info else 'enamel'

    if parent_type == 'cast':
        item_list.append({"@type": "ListItem", "position": 2, "name": "Cast Collection", "item": f"{base_url}/cast.html"})
        item_list.append({"@type": "ListItem", "position": 3, "name": item.get('title', '').strip(), "item": product_url})
    else:
        item_list.append({"@type": "ListItem", "position": 2, "name": "Enamel Collection", "item": f"{base_url}/index.html"})
        item_list.append({"@type": "ListItem", "position": 3, "name": item.get('title', '').strip(), "item": product_url})
    
    breadcrumb_schema = {
        "@type": "BreadcrumbList",
        "itemListElement": item_list
    }

    combined_schema = {
        "@context": "https://schema.org",
        "@graph": [
            product_schema,
            breadcrumb_schema
        ]
    }
    
    return json.dumps(combined_schema, indent=2, ensure_ascii=False)


def generate_site():
    print("Начало сборки сайта...")
    output_dir = 'public'
    
    if os.path.exists(output_dir): shutil.rmtree(output_dir)
    os.makedirs(output_dir)

    print("Копирование статичных файлов...")
    # Копируем все, КРОМЕ template.html
    files_to_copy = ['index.html', 'cast.html', 'blog.html', 'about.html', 'product.html']
    
    for file_name in files_to_copy:
        if os.path.exists(file_name):
            shutil.copy(file_name, os.path.join(output_dir, file_name))
            print(f"  -> Скопирован: {file_name}")
        else:
            print(f"  -> ВНИМАНИЕ: Файл для копирования не найден: {file_name}")
    
    print("Создание языковой структуры для блога...")
    languages = ['en', 'ru', 'ka']
    post_template_path = 'post.html' 

    if os.path.exists(post_template_path):
        for lang in languages:
            lang_dir = os.path.join(output_dir, lang)
            os.makedirs(lang_dir, exist_ok=True)
            shutil.copy(post_template_path, os.path.join(lang_dir, 'post.html'))
            print(f"  -> Создана папка и скопирован шаблон для языка: {lang}")
    else:
        print(f"  -> ВНИМАНИЕ: Шаблон поста '{post_template_path}' не найден!")

    # --- ВОЗВРАЩАЕМ СТАТИЧЕСКУЮ ГЕНЕРАЦИЮ ТОВАРОВ ---
    products_dir = os.path.join(output_dir, 'product')
    os.makedirs(products_dir, exist_ok=True)

    print("Загрузка данных из Firebase...")
    categories_ref = db.collection('categories').stream()
    all_categories = {doc.id: doc.to_dict() for doc in categories_ref}
    print(f"Загружено {len(all_categories)} категорий.")
    products_ref = db.collection('products').stream()
    all_products = [doc.to_dict() for doc in products_ref]
    print(f"Загружено {len(all_products)} товаров.")

    print("Генерация статических страниц товаров...")
    for item in all_products:
        slug = item.get('slug')
        if not slug:
            print(f"  -> Пропущен товар без слага: {item.get('title')}")
            continue

        image_urls = [img for img in item.get('images', []) if 'youtube.com' not in img and 'youtu.be' not in img]
        
        combined_schema_json = generate_schemas(item, all_categories, image_urls)
        
        context = {
            'item': item,
            'image_urls': image_urls,
            'all_categories': all_categories,
            'combined_schema_json': combined_schema_json
        }
        
        rendered_html = template.render(context)
        
        product_folder = os.path.join(products_dir, slug)
        os.makedirs(product_folder, exist_ok=True)
        output_path = os.path.join(product_folder, 'index.html')
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(rendered_html)
    # --- КОНЕЦ БЛОКА ГЕНЕРАЦИИ ТОВАРОВ ---
            
    print("Сборка сайта успешно завершена.")

if __name__ == '__main__':
    generate_site()
