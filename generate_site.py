import os
import json
import shutil
import firebase_admin
from firebase_admin import credentials, firestore
from jinja2 import Environment, FileSystemLoader

# --- НАСТРОЙКА ---
# Скрипт будет использовать переменную окружения 'FIREBASE_KEY'
try:
    # Загружаем JSON-ключ из переменной окружения
    service_account_info_str = os.environ.get('FIREBASE_KEY')
    if not service_account_info_str:
        raise ValueError("Переменная окружения FIREBASE_KEY не найдена или пуста.")
    
    service_account_info = json.loads(service_account_info_str)
    cred = credentials.Certificate(service_account_info)
    
    # Укажите ваш Project ID из Firebase
    firebase_admin.initialize_app(cred, {'projectId': 'nini-shop-7c89d'})
    db = firestore.client()
    print("Подключение к Firebase успешно.")
except Exception as e:
    print(f"ОШИБКА ПОДКЛЮЧЕНИЯ к Firebase: {e}")
    print("Убедитесь, что секрет FIREBASE_KEY добавлен в настройки репозитория GitHub и содержит корректный JSON.")
    exit(1)

# Настройка шаблонизатора Jinja2
env = Environment(loader=FileSystemLoader('.'))
template = env.get_template('template.html')

# Папка для сгенерированного сайта
OUTPUT_DIR = 'public'
if os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- ФУНКЦИИ ---

def get_all_data():
    """Загружает все необходимые данные из Firestore."""
    site_data = {'products': [], 'categories': {}}
    try:
        products_stream = db.collection('products').stream()
        for doc in products_stream:
            site_data['products'].append(doc.to_dict())

        categories_stream = db.collection('categories').stream()
        for doc in categories_stream:
            cat_data = doc.to_dict()
            site_data['categories'][cat_data.get('id')] = cat_data

        print(f"Загружено {len(site_data['products'])} товаров и {len(site_data['categories'])} категорий.")
        return site_data
    except Exception as e:
        print(f"Критическая ОШИБКА при загрузке данных: {e}")
        return None

def format_description(content_string):
    """Превращает строки с переносами в параграфы HTML."""
    if not content_string or not isinstance(content_string, str):
        return ""
    paragraphs = content_string.strip().split('\n')
    return ''.join(f'<p>{p.strip()}</p>' for p in paragraphs if p.strip())

def generate_product_pages(all_data):
    """Генерирует статические HTML страницы для каждого товара."""
    print("\nНачинаю генерацию страниц товаров...")
    products = all_data.get('products', [])
    categories = all_data.get('categories', {})

    if not products:
        print("Товары не найдены. Генерация страниц товаров пропущена.")
        return

    for item in products:
        slug = item.get('slug')
        if not slug:
            print(f"[ПРЕДУПРЕЖДЕНИЕ] Пропущен товар без слага (slug): {item.get('title', 'Без названия')}")
            continue

        path = os.path.join(OUTPUT_DIR, 'product', slug, 'index.html')
        os.makedirs(os.path.dirname(path), exist_ok=True)

        try:
            html_content = template.render(
                item=item,
                all_categories=categories,
                format_description=format_description
            )
            with open(path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"✓ Создана страница: /product/{slug}/")
        except Exception as e:
            print(f"[ОШИБКА] Не удалось создать страницу для '{slug}': {e}")

def copy_static_assets():
    """Копирует все остальные файлы (html, css, js, изображения) в папку public."""
    print("\nНачинаю копирование статических ассетов...")
    excluded_files = [
        '.git', '.github', OUTPUT_DIR,
        'generate_site.py', 'template.html', 'firebase.json', 'README.md',
        'product.html'  # Важно: мы не копируем оригинальный product.html!
    ]
    for item_name in os.listdir('.'):
        if item_name not in excluded_files:
            source_path = os.path.join('.', item_name)
            dest_path = os.path.join(OUTPUT_DIR, item_name)
            try:
                if os.path.isfile(source_path):
                    shutil.copy2(source_path, dest_path)
                elif os.path.isdir(source_path):
                    shutil.copytree(source_path, dest_path)
            except Exception as e:
                print(f"[ПРЕДУПРЕЖДЕНИЕ] Не удалось скопировать '{item_name}': {e}")
    print("Копирование ассетов завершено.")

def main():
    """Главная функция для запуска процесса генерации."""
    all_data = get_all_data()
    if not all_data:
        print("Не удалось получить данные. Генерация сайта отменена.")
        return

    generate_product_pages(all_data)
    copy_static_assets()

    print("\nГенерация сайта полностью завершена!")
    print(f"Готовый сайт находится в папке '{OUTPUT_DIR}'.")
    print("\nВАЖНО: Не забудьте настроить rewrite-правила на вашем хостинге!")

if __name__ == '__main__':
    main()
