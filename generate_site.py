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
        # Проверяем наличие файла, чтобы избежать падения, если его нет
        if os.path.exists('firebase-key.json'):
            with open('firebase-key.json', 'r') as f:
                service_account_json_str = f.read()
        else:
            print("ВНИМАНИЕ: Файл 'firebase-key.json' не найден. Скрипт может упасть, если ключи не настроены.")

    if service_account_json_str:
        service_account_info = json.loads(service_account_json_str)
        if not firebase_admin._apps:
            cred = credentials.Certificate(service_account_info)
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Успешное подключение к Firebase.")
    else:
        raise Exception("Ключи доступа не найдены.")

except Exception as e:
    print(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось подключиться к Firebase. {e}")
    exit(1)

# --- НАСТРОЙКА JINJA2 ---
env = Environment(loader=FileSystemLoader('.'))
template = env.get_template('template.html') 

# Фильтр для форматирования описания (используется в product.html/template.html)
def format_description(text):
    if not text: return ""
    return "".join(f'<p>{p.strip()}</p>' for p in text.strip().split('\n') if p.strip())

env.filters['format_description'] = format_description

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def generate_schemas(item, all_categories, image_urls):
    """Генерация JSON-LD схемы для товаров"""
    base_url = "https://minankari.art"
    product_url = f"{base_url}/product/{item.get('slug')}" # Чистый URL
    
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
        "description": clean_description[:300], # Ограничиваем длину
        "image": image_urls,
        "brand": {"@type": "Brand", "name": "Nino Kartsivadze"},
        "url": product_url,
        "category": category_string
    }
    
    price_str = str(item.get('price', '')).replace('$', '').replace(',', '').strip()
    if price_str:
        try:
            # Извлекаем только цифры и точку
            price_clean = re.sub(r'[^\d.]', '', price_str)
            price_val = float(price_clean)
            product_schema['offers'] = {
                "@type": "Offer",
                "url": product_url,
                "priceCurrency": "USD",
                "price": f"{price_val:.2f}",
                "availability": f"https://schema.org/{item.get('availability', 'InStock')}"
            }
        except (ValueError, TypeError):
            pass

    return json.dumps(product_schema, indent=2, ensure_ascii=False)


def generate_site():
    print("Начало сборки сайта...")
    output_dir = 'public'
    
    # Очистка папки public
    if os.path.exists(output_dir): 
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)

    # 1. Копирование корневых файлов
    print("Копирование статичных файлов...")
    files_to_copy = ['index.html', 'cast.html', 'blog.html', 'about.html', 'product.html']
    
    for file_name in files_to_copy:
        if os.path.exists(file_name):
            shutil.copy(file_name, os.path.join(output_dir, file_name))
            print(f"  -> Скопирован: {file_name}")
        else:
            print(f"  -> ВНИМАНИЕ: Файл {file_name} не найден!")

    # 2. Загрузка данных из Firebase
    print("Загрузка данных из Firebase...")
    
    # Категории
    categories_ref = db.collection('categories').stream()
    all_categories = {doc.id: doc.to_dict() for doc in categories_ref}
    
    # Товары
    products_ref = db.collection('products').stream()
    all_products = [doc.to_dict() for doc in products_ref]
    
    # Блог (НОВОЕ)
    posts_ref = db.collection('blog_posts').stream()
    all_posts = [{'id': doc.id, **doc.to_dict()} for doc in posts_ref]

    print(f"Загружено: Категорий: {len(all_categories)}, Товаров: {len(all_products)}, Постов: {len(all_posts)}")

    # 3. Генерация страниц БЛОГА (ИСПРАВЛЕНИЕ ВАШЕЙ ПРОБЛЕМЫ)
    print("Генерация структуры блога...")
    post_template_path = 'post.html'
    
    if os.path.exists(post_template_path):
        # Читаем шаблон один раз
        with open(post_template_path, 'r', encoding='utf-8') as f:
            post_html_content = f.read()

        for post in all_posts:
            i18n = post.get('i18n', {})
            # Проходим по всем доступным языкам в посте (en, ru, ka)
            for lang in ['en', 'ru', 'ka']:
                lang_data = i18n.get(lang)
                if lang_data and lang_data.get('slug'):
                    slug = lang_data.get('slug')
                    
                    # Создаем путь: public/en/post/slug-name/
                    post_dir = os.path.join(output_dir, lang, 'post', slug)
                    os.makedirs(post_dir, exist_ok=True)
                    
                    # Записываем туда index.html (это копия post.html)
                    # Браузер откроет этот файл при запросе .../en/post/slug
                    output_path = os.path.join(post_dir, 'index.html')
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(post_html_content)
        print("  -> Страницы постов сгенерированы.")
    else:
        print(f"  -> ОШИБКА: Файл шаблона '{post_template_path}' не найден. Блог не сгенерирован.")

    # 4. Генерация страниц ТОВАРОВ
    print("Генерация страниц товаров...")
    products_dir = os.path.join(output_dir, 'product')
    os.makedirs(products_dir, exist_ok=True)

    for item in all_products:
        slug = item.get('slug')
        if not slug:
            continue

        image_urls = [img for img in item.get('images', []) if 'youtube.com' not in img and 'youtu.be' not in img]
        
        combined_schema_json = generate_schemas(item, all_categories, image_urls)
        
        context = {
            'item': item,
            'image_urls': image_urls,
            'all_categories': all_categories,
            'combined_schema_json': combined_schema_json
        }
        
        # Рендерим через Jinja2 (используя template.html)
        rendered_html = template.render(context)
        
        # Создаем структуру: public/product/slug-name/index.html
        product_folder = os.path.join(products_dir, slug)
        os.makedirs(product_folder, exist_ok=True)
        output_path = os.path.join(product_folder, 'index.html')
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(rendered_html)
            
    print("Сборка сайта успешно завершена.")

if __name__ == '__main__':
    generate_site()
