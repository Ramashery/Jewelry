import os
import json
import shutil
import re
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
import firebase_admin
from firebase_admin import credentials, firestore

# --- НАСТРОЙКА FIREBASE ---
try:
    service_account_json_str = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
    if not service_account_json_str:
        if os.path.exists('firebase-key.json'):
            with open('firebase-key.json', 'r') as f:
                service_account_json_str = f.read()
    
    if service_account_json_str:
        service_account_info = json.loads(service_account_json_str)
        if not firebase_admin._apps:
            cred = credentials.Certificate(service_account_info)
            firebase_admin.initialize_app(cred)
        db = firestore.client()
    else:
        db = None
        print("ERROR: Ключи доступа Firebase не найдены.")
except Exception as e:
    print(f"CRITICAL ERROR: {e}")
    exit(1)

# --- НАСТРОЙКА JINJA2 ---
env = Environment(loader=FileSystemLoader('.'))

def format_description(text):
    if not text: return ""
    return "".join(f'<p>{p.strip()}</p>' for p in text.strip().split('\n') if p.strip())

def parse_blog_content(content):
    if not content: return ""
    # Замена [image: url]
    content = re.sub(r'\[image:\s*(.*?)\]', r'<img src="\1" class="embedded-image" alt="Blog image" loading="lazy">', content)
    # Замена [youtube: url]
    def youtube_repl(match):
        url = match.group(1)
        video_id = url.split('v=')[-1] if 'v=' in url else url.split('/')[-1]
        return f'<div class="slideshow-item-video"><iframe src="https://www.youtube.com/embed/{video_id}" allowfullscreen></iframe></div>'
    content = re.sub(r'\[youtube:\s*(.*?)\]', youtube_repl, content)
    return content.replace('\n', '<br>')

env.filters['format_description'] = format_description
env.filters['parse_blog_content'] = parse_blog_content

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace('\n', ' ').strip()

def generate_product_schema(item, all_categories, image_urls, canonical_url):
    # Очистка описания для Schema
    description = clean_html(item.get('description', '') or item.get('metaDescription', ''))[:300]
    
    # 1. Product Schema
    product_schema = {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": item.get('title', '').strip(),
        "image": image_urls if image_urls else ["https://minankari.art/placeholder.jpg"],
        "description": description,
        "sku": item.get('sku', item.get('slug')),
        "brand": {
            "@type": "Brand",
            "name": "Nino Kartsivadze"
        },
        "url": canonical_url
    }

    # Обработка цены и наличия
    price_str = str(item.get('price', '')).replace('$', '').replace(',', '').strip()
    price_val = None
    if price_str:
        try:
            price_clean = re.sub(r'[^\d.]', '', price_str)
            if price_clean:
                price_val = "{:.2f}".format(float(price_clean))
        except: pass

    if price_val:
        availability_map = {
            'InStock': 'https://schema.org/InStock',
            'OutOfStock': 'https://schema.org/OutOfStock',
            'PreOrder': 'https://schema.org/PreOrder',
            'SoldOut': 'https://schema.org/SoldOut'
        }
        status = item.get('availability', 'InStock')
        
        product_schema['offers'] = {
            "@type": "Offer",
            "url": canonical_url,
            "priceCurrency": "USD",
            "price": price_val,
            "priceValidUntil": "2026-12-31", 
            "availability": availability_map.get(status, 'https://schema.org/InStock'),
            "itemCondition": "https://schema.org/NewCondition"
        }

    # 2. BreadcrumbList Schema (Product)
    # ЛОГИКА:
    # 1. Enamel: Home > Product (так как enamel главная)
    # 2. Cast: Home > Cast > Product
    
    cat_id = item.get('category')
    is_cast = False
    
    if cat_id and cat_id in all_categories:
        # Проверяем, является ли родительская категория 'cast'
        if all_categories[cat_id].get('parent') == 'cast':
            is_cast = True

    breadcrumb_list = [
        { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://minankari.art/" }
    ]
    
    pos = 2
    if is_cast:
        breadcrumb_list.append({
            "@type": "ListItem", "position": 2, "name": "Cast Collection", "item": "https://minankari.art/cast"
        })
        pos += 1
    
    # Ссылка на сам товар
    breadcrumb_list.append({
        "@type": "ListItem", "position": pos, "name": item.get('title'), "item": canonical_url
    })

    breadcrumb_schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": breadcrumb_list
    }

    return json.dumps([product_schema, breadcrumb_schema], indent=2, ensure_ascii=False)

def generate_post_schema(post_data, lang, slug, canonical_url):
    # Дата публикации
    date_published = datetime.now().isoformat()
    if post_data.get('timestamp'):
        try:
            date_published = post_data['timestamp'].isoformat()
        except: pass

    # 1. BlogPosting Schema
    schema_blog = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post_data['i18n'][lang].get('title'),
        "description": post_data['i18n'][lang].get('metaDescription') or post_data['i18n'][lang].get('subtitle', ''),
        "image": post_data.get('mediaUrls', ["https://minankari.art/og-image.jpg"]),
        "author": {
            "@type": "Person",
            "name": "Nino Kartsivadze",
            "url": "https://minankari.art/about"
        },
        "publisher": {
            "@type": "Organization",
            "name": "Cloisonne Enamel",
            "logo": {
                "@type": "ImageObject",
                "url": "https://minankari.art/logo.png"
            }
        },
        "datePublished": date_published,
        "dateModified": date_published,
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": canonical_url
        }
    }

    # 2. BreadcrumbList Schema (Blog)
    # ЛОГИКА: Home > Blog > Post
    breadcrumb_schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://minankari.art/" },
            { "@type": "ListItem", "position": 2, "name": "Blog", "item": "https://minankari.art/blog" },
            { "@type": "ListItem", "position": 3, "name": post_data['i18n'][lang].get('title'), "item": canonical_url }
        ]
    }

    return json.dumps([schema_blog, breadcrumb_schema], indent=2, ensure_ascii=False)


def generate_site():
    print("--- НАЧАЛО СБОРКИ САЙТА ---")
    output_dir = 'public'
    if os.path.exists(output_dir): shutil.rmtree(output_dir)
    os.makedirs(output_dir)

    # Копирование статики
    static_files = ['index.html', 'cast.html', 'blog.html', 'about.html']
    for f in static_files:
        if os.path.exists(f): shutil.copy(f, os.path.join(output_dir, f))

    # Загрузка шаблонов
    try:
        product_template = env.get_template('template.html')
        post_template = env.get_template('post_template.html') 
    except Exception as e:
        print(f"ERROR: Не найден шаблон: {e}")
        return

    if not db: 
        print("База данных недоступна. Выход.")
        return

    print("Загрузка данных из Firebase...")
    cats = {d.id: d.to_dict() for d in db.collection('categories').stream()}
    prods = [d.to_dict() for d in db.collection('products').stream()]
    
    posts = []
    for d in db.collection('blog_posts').order_by('timestamp', direction=firestore.Query.DESCENDING).stream():
        p = d.to_dict()
        p['id'] = d.id
        posts.append(p)

    # --- 1. ГЕНЕРАЦИЯ ТОВАРОВ ---
    print(f"Генерация {len(prods)} товаров...")
    products_dir = os.path.join(output_dir, 'product')
    os.makedirs(products_dir, exist_ok=True)

    for item in prods:
        slug = item.get('slug')
        if not slug: continue
        
        # Фильтрация YouTube из картинок для Schema
        images_clean = [img for img in item.get('images', []) if 'youtube' not in img and 'youtu.be' not in img]
        
        canonical_url = f"https://minankari.art/product/{slug}/"
        schema_json = generate_product_schema(item, cats, images_clean, canonical_url)

        html = product_template.render(
            item=item,
            all_categories=cats,
            image_urls=images_clean,
            combined_schema_json=schema_json,
            canonical_url=canonical_url
        )
        
        p_path = os.path.join(products_dir, slug)
        os.makedirs(p_path, exist_ok=True)
        with open(os.path.join(p_path, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(html)

    # --- 2. ГЕНЕРАЦИЯ БЛОГА ---
    print(f"Генерация {len(posts)} постов...")
    
    for post in posts:
        i18n = post.get('i18n', {})
        
        # Сбор Hreflang ссылок
        hreflangs = []
        for l_code in ['en', 'ru', 'ka']:
            if l_code in i18n and i18n[l_code].get('slug'):
                l_slug = i18n[l_code]['slug']
                hreflangs.append({
                    'lang': l_code,
                    'url': f"https://minankari.art/{l_code}/post/{l_slug}/"
                })
        
        # Добавляем x-default (ссылается на EN)
        en_link = next((x for x in hreflangs if x['lang'] == 'en'), None)
        if en_link:
            hreflangs.append({'lang': 'x-default', 'url': en_link['url']})

        # Генерация страниц для каждого языка
        for lang_code in ['en', 'ru', 'ka']:
            lang_data = i18n.get(lang_code)
            if not lang_data or not lang_data.get('slug'):
                continue
            
            slug = lang_data.get('slug')
            canonical_url = f"https://minankari.art/{lang_code}/post/{slug}/"
            
            schema_json = generate_post_schema(post, lang_code, slug, canonical_url)
            
            # Related posts logic
            related_posts = []
            for rp in posts:
                if rp['id'] == post['id']: continue
                if len(related_posts) >= 3: break
                if rp.get('i18n', {}).get(lang_code, {}).get('slug'):
                    related_posts.append({
                        'title': rp['i18n'][lang_code]['title'],
                        'slug': rp['i18n'][lang_code]['slug'],
                        'image': rp.get('mediaUrls', [''])[0]
                    })

            html = post_template.render(
                lang=lang_code,
                post=post,
                content=lang_data,
                canonical_url=canonical_url,
                hreflangs=hreflangs,
                schema_json=schema_json,
                related_posts=related_posts
            )

            post_path = os.path.join(output_dir, lang_code, 'post', slug)
            os.makedirs(post_path, exist_ok=True)
            with open(os.path.join(post_path, 'index.html'), 'w', encoding='utf-8') as f:
                f.write(html)

    print("--- СБОРКА ЗАВЕРШЕНА ---")

if __name__ == '__main__':
    generate_site()