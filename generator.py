import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from jinja2 import Environment, FileSystemLoader

# Настройка Firebase (берем ключ из секретов GitHub)
if 'FIREBASE_KEY' in os.environ:
    key_dict = json.loads(os.environ['FIREBASE_KEY'])
    cred = credentials.Certificate(key_dict)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
else:
    print("Ошибка: Секрет FIREBASE_KEY не найден!")
    exit(1)

env = Environment(loader=FileSystemLoader('.'))

def fetch_data():
    print("📥 Загрузка данных...")
    products = [doc.to_dict() for doc in db.collection('products').stream()]
    categories = {doc.id: doc.to_dict() for doc in db.collection('categories').stream()}
    blog_posts = [doc.to_dict() for doc in db.collection('blog_posts').stream()]
    about_me = db.collection('site_content').doc('about_me').get().to_dict()
    return products, categories, blog_posts, about_me

def render(template_name, output_path, data):
    template = env.get_template(template_name)
    html = template.render(**data)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ Создан: {output_path}")

def main():
    products, categories, blog_posts, about_me = fetch_data()
    
    # 1. Главная (Enamel)
    en_prods = [p for p in products if categories.get(p.get('category'), {}).get('parent') == 'enamel']
    render('index (9).html', 'index.html', {'page_products': en_prods})

    # 2. Cast
    ca_prods = [p for p in products if categories.get(p.get('category'), {}).get('parent') == 'cast']
    render('cast.html', 'cast.html', {'page_products': ca_prods})

    # 3. Blog
    render('blog (1).html', 'blog.html', {'blog_posts': blog_posts})

    # 4. About
    render('about.html', 'about.html', {'about': about_me})

    # 5. Посты (раскладываем по папкам языков)
    for lang in ['en', 'ru', 'ka']:
        render('post (1).html', f'{lang}/post.html', {'current_lang': lang, 'blog_posts': blog_posts})

    # 6. Карточка товара (оставляем как общую оболочку)
    render('product.html', 'product.html', {})

if __name__ == "__main__":
    main()
