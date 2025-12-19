import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from jinja2 import Environment, FileSystemLoader

# Настройка Firebase
if 'FIREBASE_KEY' in os.environ:
    try:
        key_dict = json.loads(os.environ['FIREBASE_KEY'])
        cred = credentials.Certificate(key_dict)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
    except Exception as e:
        print(f"Ошибка инициализации Firebase: {e}")
        exit(1)
else:
    print("Ошибка: Секрет FIREBASE_KEY не найден!")
    exit(1)

# Настройка шаблонизатора
env = Environment(loader=FileSystemLoader('.'))

def fetch_data():
    print("📥 Загрузка данных из Firebase...")
    products = [doc.to_dict() for doc in db.collection('products').stream()]
    categories = {doc.id: doc.to_dict() for doc in db.collection('categories').stream()}
    blog_posts = [doc.to_dict() for doc in db.collection('blog_posts').stream()]
    
    about_doc = db.collection('site_content').document('about_me').get()
    about_me = about_doc.to_dict() if about_doc.exists else {"text": "", "images": []}
    
    return products, categories, blog_posts, about_me

def render_page(template_name, output_path, data):
    try:
        template = env.get_template(template_name)
        html = template.render(**data)
        # Создаем папку если нужно
        folder = os.path.dirname(output_path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
            
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"✅ Готово: {output_path}")
    except Exception as e:
        print(f"❌ Ошибка в {template_name}: {e}")

def main():
    products, categories, blog_posts, about_me = fetch_data()
    
    # Контекст
    ctx = {'blog_posts': blog_posts, 'categories': categories, 'about': about_me}

    # 1. Главная (Enamel)
    en_prods = [p for p in products if categories.get(p.get('category'), {}).get('parent') == 'enamel']
    render_page('index.html', 'index.html', {**ctx, 'page_products': en_prods})

    # 2. Cast
    ca_prods = [p for p in products if categories.get(p.get('category'), {}).get('parent') == 'cast']
    render_page('cast.html', 'cast.html', {**ctx, 'page_products': ca_prods})

    # 3. Blog
    render_page('blog.html', 'blog.html', ctx)

    # 4. About
    render_page('about.html', 'about.html', ctx)

    # 5. Посты по языкам
    for lang in ['en', 'ru', 'ka']:
        render_page('post.html', f'{lang}/post.html', {**ctx, 'current_lang': lang})

    # 6. Product
    render_page('product.html', 'product.html', ctx)

if __name__ == "__main__":
    main()
