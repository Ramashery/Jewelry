import os
import json
import shutil
from jinja2 import Environment, FileSystemLoader
import firebase_admin
from firebase_admin import credentials, firestore

# --- НАСТРОЙКА ---
try:
    service_account_json_str = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
    if not service_account_json_str:
        raise ValueError("Переменная окружения FIREBASE_SERVICE_ACCOUNT не найдена.")
    service_account_info = json.loads(service_account_json_str)
    cred = credentials.Certificate(service_account_info)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Успешное подключение к Firebase через переменные окружения.")
except Exception as e:
    print(f"Ошибка подключения к Firebase: {e}")
    exit(1)

# --- НАСТРОЙКА JINJA2 ---
env = Environment(loader=FileSystemLoader('.'))

def format_description(text):
    if not text: return ""
    return "".join(f'<p>{p.strip()}</p>' for p in text.strip().split('\n') if p.strip())

env.filters['format_description'] = format_description
template = env.get_template('template.html')


# --- ФУНКЦИИ ГЕНЕРАЦИИ ДАННЫХ ---

def generate_schemas(item, all_categories, image_urls):
    """
    !!! НОВАЯ ФУНКЦИЯ: Генерирует ОБА типа разметки (Product и Breadcrumb)
    и объединяет их в @graph.
    """
    base_url = "https://minankari.art"
    product_url = f"{base_url}/product.html?slug={item.get('slug')}"
    
    # --- 1. Создаем разметку Product ---
    product_schema = {
        "@type": "Product",
        "name": item.get('title'),
        "description": item.get('description', '').replace('\n', ' '),
        "sku": item.get('sku', ''),
        "mpn": item.get('sku', ''),
        "image": image_urls,
        "brand": {"@type": "Brand", "name": "Nino Kartsivadze"},
        "manufacturer": {"@type": "Person", "name": "Nino Kartsivadze"},
        "url": product_url
    }
    
    # Добавляем необязательные поля, если они есть
    if item.get('material'):
        product_schema['material'] = item.get('material')
    if item.get('additionalProperties'):
        product_schema['additionalProperty'] = item.get('additionalProperties')
        
    # Блок с ценой (Offer)
    price_str = item.get('price', '').replace('$', '').replace(',', '').strip()
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
                # Сюда можно вернуть shippingDetails и hasMerchantReturnPolicy, если нужно
            }
        except (ValueError, TypeError):
            pass # Если цена некорректна, просто не добавляем offer

    # --- 2. Создаем разметку BreadcrumbList ---
    item_list = [{"@type": "ListItem", "position": 1, "name": "Home", "item": f"{base_url}/"}]
    item_category_id = item.get('category')
    item_category = all_categories.get(item_category_id) if item_category_id else None
    parent_type = item_category.get('parent') if item_category else 'enamel'

    if parent_type == 'cast':
        item_list.append({"@type": "ListItem", "position": 2, "name": "Cast Collection", "item": f"{base_url}/cast.html"})
        item_list.append({"@type": "ListItem", "position": 3, "name": item.get('title'), "item": product_url})
    else:
        item_list.append({"@type": "ListItem", "position": 2, "name": item.get('title'), "item": product_url})
    
    breadcrumb_schema = {
        "@type": "BreadcrumbList",
        "itemListElement": item_list
    }

    # --- 3. Объединяем всё в @graph ---
    combined_schema = {
        "@context": "https://schema.org",
        "@graph": [
            product_schema,
            breadcrumb_schema
        ]
    }
    
    return json.dumps(combined_schema, indent=2)


def generate_site():
    print("Начало сборки сайта...")
    output_dir = 'public'
    
    if os.path.exists(output_dir): shutil.rmtree(output_dir)
    os.makedirs(output_dir)

    files_to_copy = ['index.html', 'cast.html']
    
    print("Копирование статичных файлов...")
    for file_name in files_to_copy:
        if os.path.exists(file_name):
            shutil.copy(file_name, os.path.join(output_dir, file_name))
            print(f"  -> Скопирован: {file_name}")
        else:
            print(f"  -> ВНИМАНИЕ: Файл для копирования не найден: {file_name}")

    products_dir = os.path.join(output_dir, 'product')
    os.makedirs(products_dir, exist_ok=True)

    print("Загрузка данных из Firebase...")
    categories_ref = db.collection('categories').stream()
    all_categories = {doc.id: doc.to_dict() for doc in categories_ref}
    print(f"Загружено {len(all_categories)} категорий.")
    products_ref = db.collection('products').stream()
    all_products = [doc.to_dict() for doc in products_ref]
    print(f"Загружено {len(all_products)} товаров.")

    print("Генерация страниц товаров...")
    for item in all_products:
        slug = item.get('slug')
        if not slug:
            print(f"  -> Пропущен товар без слага: {item.get('title')}")
            continue

        image_urls = [img for img in item.get('images', []) if 'youtube.com' not in img and 'youtu.be' not in img]
        
        # !!! ИЗМЕНЕНИЕ: Вызываем одну функцию для всей разметки
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
            
    print("Все страницы товаров успешно сгенерированы.")
    print("Сборка сайта успешно завершена.")

if __name__ == '__main__':
    generate_site()
