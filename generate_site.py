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

# Загрузка шаблона товаров
try:
    template = env.get_template('template.html')
except Exception as e:
    print(f"WARNING: Не удалось загрузить template.html: {e}")
    template = None

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def generate_schemas(item, all_categories, image_urls):
    base_url = "https://minankari.art"
    # Canonical URL должен быть со слэшем в конце
    product_url = f"{base_url}/product/{item.get('slug')}/"
    
    text_with_spaces = re.sub('<[^<]+?>', ' ', item.get('description', '')).replace('\n', ' ')
    clean_description = ' '.join(text_with_spaces.split())

    item_category_id = item.get('category')
    category_info = all_categories.get(item_category_id) if item_category_id else None
    
    # 1. Product Schema
    product_schema = {
        "@type": "Product",
        "name": item.get('title', '').strip(),
        "description": clean_description[:300],
        "image": image_urls,
        "brand": {"@type": "Brand", "name": "Nino Kartsivadze"},
        "url": product_url
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

    # 2. BreadcrumbList Schema
    breadcrumb_list = []
    
    # Home
    breadcrumb_list.append({
        "@type": "ListItem",
        "position": 1,
        "name": "Home",
        "item": base_url + "/"
    })
    
    current_pos = 2
    
    # Logic for Categories
    if category_info and category_info.get('parent') == 'cast':
        # Для CAST: Home -> Cast -> Product
        breadcrumb_list.append({
            "@type": "ListItem",
            "position": current_pos,
            "name": "Cast Collection",
            "item": base_url + "/cast"
        })
        current_pos += 1
    # Для ENAMEL: Home -> Product (пропускаем промежуточную категорию согласно требованию)
    
    # Product Leaf
    breadcrumb_list.append({
        "@type": "ListItem",
        "position": current_pos,
        "name": item.get('title', '').strip(),
        "item": product_url
    })

    breadcrumb_schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": breadcrumb_list
    }

    # Возвращаем список схем (Product + Breadcrumb)
    return json.dumps([product_schema, breadcrumb_schema], indent=2, ensure_ascii=False)


def generate_site():
    print("--- НАЧАЛО СБОРКИ САЙТА ---")
    output_dir = 'public'
    
    if os.path.exists(output_dir): 
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)

    # 1. Копирование корневых файлов
    print("Step 1: Копирование статичных файлов...")
    files_to_copy = ['index.html', 'cast.html', 'blog.html', 'about.html', 'product.html']
    
    for file_name in files_to_copy:
        if os.path.exists(file_name):
            shutil.copy(file_name, os.path.join(output_dir, file_name))
            print(f"  -> OK: {file_name}")
        else:
            print(f"  -> INFO: Файл {file_name} не найден.")

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
    if not os.path.exists(post_template_path):
        if os.path.exists('en/post.html'):
            post_template_path = 'en/post.html'
        else:
            post_template_path = None

    if post_template_path:
        with open(post_template_path, 'r', encoding='utf-8') as f:
            post_html_content = f.read()

        count_generated = 0
        
        for post in all_posts:
            i18n = post.get('i18n')
            if not i18n: continue

            for lang in ['en', 'ru', 'ka']:
                lang_data = i18n.get(lang)
                if not lang_data: continue
                
                slug = lang_data.get('slug')
                if not slug: continue
                    
                # Создаем путь: public/lang/post/slug/
                post_dir = os.path.join(output_dir, lang, 'post', slug)
                try:
                    os.makedirs(post_dir, exist_ok=True)
                    
                    output_path = os.path.join(post_dir, 'index.html')
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(post_html_content)
                    
                    count_generated += 1
                except Exception as e:
                    print(f"  -> ERROR: Не удалось создать файл для {slug}: {e}")

        print(f"  -> Итого сгенерировано страниц блога: {count_generated}")
    else:
        print(f"  -> CRITICAL ERROR: Шаблон поста не найден! Блог не сгенерирован.")

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
            
            # Генерация схем
            combined_schema_json = generate_schemas(item, all_categories, image_urls)
            
            # Canonical URL со слэшем
            canonical_url = f"https://minankari.art/product/{slug}/"

            context = {
                'item': item,
                'image_urls': image_urls,
                'all_categories': all_categories,
                'combined_schema_json': combined_schema_json,
                'canonical_url': canonical_url
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