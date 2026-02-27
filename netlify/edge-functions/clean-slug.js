export default async (request, context) => {
  const url = new URL(request.url);

  // Если в ссылке есть параметр "slug"
  if (url.searchParams.has("slug")) {
    // Удаляем его
    url.searchParams.delete("slug");
    
    // Возвращаем 301 редирект на чистую ссылку
    return Response.redirect(url.toString(), 301);
  }

  // Если параметра нет, отдаем страницу как обычно
  return context.next();
};
