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
        print("INFO: Переменная окружения FIREBASE_SERVICE_ACCOUNT не найдена. Ищем локальный файл.")
        if os.path.exists('firebase-key.json'):
            with open('firebase-key.json', 'r') as f:
                service_account_json_str = f.read()
        else:
            print("WARNING: Файл 'firebase-key.json' не найден.")

    if service_account_json_str:
        service_account_info = json.loads(service_account_json_str)
        if not firebase_admin._apps:
            cred = credentials.Certificate(service_account_info)
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("SUCCESS: Успешное подключение к Firebase.")
    else:
        db = None
        print("ERROR: Ключи доступа не найдены. Работа с БД невозможна.")

except Exception as e:
    print(f"CRITICAL ERROR: {e}")
    exit(1)

# --- НАСТРОЙКА JINJA2 ---
env = Environment(loader=FileSystemLoader('.'))

def format_description(text):
    if not text: return ""
    return "".join(f'<p>{p.strip()}</p>' for p in text.strip().split('\n') if p.strip())

env.filters['format_description'] = format_description

# Загрузка шаблона товаров (если есть)
try:
    template = env.get_template('template.html')
except Exception as e:
    print(f"WARNING: Не удалось загрузить template.html: {e}")
    template = None

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def generate_schemas(item, all_categories, image_urls):
    base_url = "https://minankari.art"
    product_url = f"{base_url}/product/{item.get('slug')}"
    
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
        "description": clean_description[:300],
        "image": image_urls,
        "brand": {"@type": "Brand", "name": "Nino Kartsivadze"},
        "url": product_url,
        "category": category_string
    }
    
    price_str = str(item.get('price', '')).replace('$', '').replace(',', '').strip()
    if price_str:
        try:
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
    print("--- НАЧАЛО СБОРКИ САЙТА ---")
    output_dir = 'public'
    
    if os.path.exists(output_dir): 
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)

    # 1. Копирование корневых файлов
    print("Step 1: Копирование статичных файлов...")
    # Добавил post.html в список, чтобы он тоже попал в корень (на всякий случай)
    files_to_copy = ['index.html', 'cast.html', 'blog.html', 'about.html', 'product.html', 'post.html']
    
    for file_name in files_to_copy:
        if os.path.exists(file_name):
            shutil.copy(file_name, os.path.join(output_dir, file_name))
            print(f"  -> OK: {file_name}")
        else:
            # Для post.html это не критично в корне, но важно для генерации
            print(f"  -> INFO: Файл {file_name} не найден в корне (это нормально, если он шаблон).")

    if not db:
        print("ERROR: Нет подключения к БД. Останавливаем сборку.")
        return

    # 2. Загрузка данных
    print("Step 2: Загрузка данных из Firebase...")
    
    try:
        categories_ref = db.collection('categories').stream()
        all_categories = {doc.id: doc.to_dict() for doc in categories_ref}
        
        products_ref = db.collection('products').stream()
        all_products = [doc.to_dict() for doc in products_ref]
        
        posts_ref = db.collection('blog_posts').stream()
        all_posts = [{'id': doc.id, **doc.to_dict()} for doc in posts_ref]

        print(f"  -> Статистика БД: Категорий: {len(all_categories)}, Товаров: {len(all_products)}, Постов: {len(all_posts)}")
    except Exception as e:
        print(f"ERROR: Ошибка при чтении из базы данных: {e}")
        return

    # 3. Генерация БЛОГА
    print("Step 3: Генерация структуры блога...")
    post_template_path = 'post.html'
    
    if os.path.exists(post_template_path):
        with open(post_template_path, 'r', encoding='utf-8') as f:
            post_html_content = f.read()

        count_generated = 0
        
        # --- ДИАГНОСТИКА ПОСТОВ ---
        if len(all_posts) == 0:
            print("  -> WARNING: Список постов пуст! Проверьте коллекцию 'blog_posts' в Firebase.")

        for post in all_posts:
            post_id = post.get('id', 'UnknownID')
            # Проверяем структуру данных
            i18n = post.get('i18n')
            
            if not i18n:
                print(f"  -> SKIP: Пост ID {post_id} не имеет поля 'i18n'.")
                continue

            for lang in ['en', 'ru', 'ka']:
                lang_data = i18n.get(lang)
                if not lang_data:
                    # Это нормально, если пост не переведен на все языки
                    continue
                
                slug = lang_data.get('slug')
                if not slug:
                    print(f"  -> SKIP: Пост ID {post_id} (lang: {lang}) не имеет поля 'slug'.")
                    continue
                    
                # Если мы здесь, значит все данные есть
                # Создаем путь: public/en/post/slug-name/
                post_dir = os.path.join(output_dir, lang, 'post', slug)
                try:
                    os.makedirs(post_dir, exist_ok=True)
                    
                    # Кладем туда index.html
                    output_path = os.path.join(post_dir, 'index.html')
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(post_html_content)
                    
                    count_generated += 1
                    # Раскомментируйте, если нужно видеть каждый созданный файл:
                    # print(f"  -> CREATED: {lang}/post/{slug}/index.html")
                except Exception as e:
                    print(f"  -> ERROR: Не удалось создать файл для {slug}: {e}")

        print(f"  -> Итого сгенерировано страниц блога: {count_generated}")
    else:
        print(f"  -> CRITICAL ERROR: Файл шаблона '{post_template_path}' не найден в папке сборки! Блог не будет сгенерирован.")
        # Выводим список файлов в текущей директории для отладки
        print(f"  -> Файлы в текущей директории: {os.listdir('.')}")

    # 4. Генерация ТОВАРОВ
    print("Step 4: Генерация страниц товаров...")
    if template:
        products_dir = os.path.join(output_dir, 'product')
        os.makedirs(products_dir, exist_ok=True)

        count_products = 0
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
            
            rendered_html = template.render(context)
            product_folder = os.path.join(products_dir, slug)
            os.makedirs(product_folder, exist_ok=True)
            output_path = os.path.join(product_folder, 'index.html')
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(rendered_html)
            count_products += 1
        
        print(f"  -> Сгенерировано товаров: {count_products}")
    else:
        print("  -> SKIP: Пропуск генерации товаров (шаблон не загружен).")
            
    print("--- СБОРКА ЗАВЕРШЕНА ---")

if __name__ == '__main__':
    generate_site()
