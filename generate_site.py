import os
import json
from jinja2 import Environment, FileSystemLoader
import firebase_admin
from firebase_admin import credentials, firestore

# --- ОБНОВЛЕННАЯ НАСТРОЙКА ---
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
    print("Убедитесь, что переменная окружения FIREBASE_SERVICE_ACCOUNT правильно настроена в Netlify.")
    exit(1)

# Настройка Jinja2
env = Environment(loader=FileSystemLoader('.'))
template = env.get_template('template.html')

# --- ФУНКЦИИ ---

def format_description(text):
    """Преобразует текст с переносами строк в параграфы HTML."""
    if not text:
        return ""
    paragraphs = text.strip().split('\n')
    return ''.join(f'<p>{p.strip()}</p>' for p in paragraphs if p.strip())

# !!! ВАЖНОЕ ИСПРАВЛЕНИЕ: Регистрируем нашу функцию как фильтр в Jinja
env.filters['format_description'] = format_description

def generate_category_string(item, all_categories):
    item_category_id = item.get('category')
    if not item_category_id:
        return "Jewelry"
    category_info = all_categories.get(item_category_id)
    if not category_info:
        return "Jewelry"
    parent_name = "Cast" if category_info.get('parent') == 'cast' else "Enamel"
    category_name = category_info.get('name', '')
    return f"{parent_name} > {category_name}"

def generate_breadcrumbs(item, all_categories):
    base_url = "https://minankari.art"
    item_list = []
    home = {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{base_url}/"}
    item_list.append(home)
    item_category_id = item.get('category')
    item_category = all_categories.get(item_category_id) if item_category_id else None
    parent_type = item_category.get('parent') if item_category else 'enamel'

    if parent_type == 'cast':
        cast_collection = {"@type": "ListItem", "position": 2, "name": "Cast Collection", "item": f"{base_url}/cast.html"}
        item_list.append(cast_collection)
        product = {"@type": "ListItem", "position": 3, "name": item.get('title'), "item": f"{base_url}/product.html?slug={item.get('slug')}"}
        item_list.append(product)
    else:
        product = {"@type": "ListItem", "position": 2, "name": item.get('title'), "item": f"{base_url}/product.html?slug={item.get('slug')}"}
        item_list.append(product)
    return {"@context": "https://schema.org/", "@type": "BreadcrumbList", "itemListElement": item_list}

def generate_site():
    print("Начало сборки сайта...")
    output_dir = 'public'
    # Копируем статичные файлы в папку public
    static_files = ['index.html', 'cast.html', 'template.html', 'netlify.txt', 'requirements.txt'] # Добавьте сюда другие файлы, если нужно
    for file_name in static_files:
        if os.path.exists(file_name):
            with open(file_name, 'r', encoding='utf-8') as f_in:
                content = f_in.read()
            with open(os.path.join(output_dir, file_name), 'w', encoding='utf-8') as f_out:
                f_out.write(content)
            print(f"Скопирован статичный файл: {file_name}")

    products_dir = os.path.join(output_dir, 'product')
    os.makedirs(products_dir, exist_ok=True)

    categories_ref = db.collection('categories').stream()
    all_categories = {doc.id: doc.to_dict() for doc in categories_ref}
    print(f"Загружено {len(all_categories)} категорий.")

    products_ref = db.collection('products').stream()
    all_products = [doc.to_dict() for doc in products_ref]
    print(f"Загружено {len(all_products)} товаров.")

    for item in all_products:
        slug = item.get('slug')
        if not slug:
            print(f"Пропущен товар без слага: {item.get('title')}")
            continue

        image_urls = [img for img in item.get('images', []) if 'youtube.com' not in img and 'youtu.be' not in img]
        schema_breadcrumbs = generate_breadcrumbs(item, all_categories)
        category_string = generate_category_string(item, all_categories)
        
        context = {
            'item': item,
            'image_urls': image_urls,
            'description_for_json': item.get('description', '').replace('\n', ' '),
            'all_categories': all_categories,
            'schema_breadcrumbs_json': json.dumps(schema_breadcrumbs, indent=2),
            'category_string_for_json': category_string
        }
        
        rendered_html = template.render(context)
        
        product_folder = os.path.join(products_dir, slug)
        os.makedirs(product_folder, exist_ok=True)
        output_path = os.path.join(product_folder, 'index.html')
        
        with open(output_path, 'w', encoding='utf-8') as f_out:
            f_out.write(rendered_html)
        
        print(f"  -> Страница создана: {output_path}")

    print("Сборка сайта успешно завершена.")

if __name__ == '__main__':
    generate_site()
