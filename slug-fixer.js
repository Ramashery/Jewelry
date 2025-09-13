// Файл: netlify/edge-functions/slug-fixer.js

export default async (request) => {
  const url = new URL(request.url);
  const slug = url.searchParams.get('slug');

  // Если slug есть и заканчивается на '/'
  if (slug && slug.endsWith('/')) {
    
    // Убираем слеш
    const correctedSlug = slug.slice(0, -1);
    url.searchParams.set('slug', correctedSlug);

    // Делаем редирект на правильный URL
    return Response.redirect(url.toString(), 301);
  }

  // Если со slug всё в порядке, ничего не делаем
};