# Cloudflare Pages — тестовая миграция AI Tools Ecosystem

**Только сайт трёх продуктов**, без переноса переводчика, локальных моделей, секретов и внутренних репозиториев.

## Уже подготовлено

- Сборка из **33 SHA-256 проверенных файлов** исходного статического сайта плюс Cloudflare `_headers` — 34 файла.
- HSTS, строгая CSP на уровне **HTTP-ответа**, запрет индексирования и дополнительные браузерные ограничения.
- Тесты и read-only аудит по действительному адресу `*.pages.dev`.
- Никаких токенов, сборки Node/Docker, платных API, внешних программ или приватных исходников.
- Старый https://quiet-flint-6kde.here.now/ остаётся без изменений и доступен как резервный.

## Настройка Cloudflare одним разом

1. Открыть https://dash.cloudflare.com/ → **Workers & Pages** → **Create application** → **Pages** → **Connect to Git**.
2. Разрешить доступ GitHub **только** к `my-project-01012026/ai-tools-ecosystem`, не ко всем репозиториям.
3. Создать отдельный Pages-проект (например, `ai-tools-ecosystem-staging`, если имя доступно). Не считайте адрес гарантированным до создания.
4. Выбрать `main` как production branch. Фреймворк `None`. Root `/`. Build command: `python3 scripts/build_cloudflare_pages.py`. Build output directory: `dist-cloudflare`. Если требуется, environment variable `PYTHON_VERSION=3.11`.
5. **Save and Deploy**. Первоначально это тестовая площадка, даже если интерфейс Cloudflare обозначает ветку production. **Git-интеграция по умолчанию публикует новые коммиты автоматически**: после первого деплоя отключите automatic production branch builds до решения о полноценном запуске. Preview-ветки тоже ограничьте.
6. Сохранить реальный URL `https://<имя-проекта>.pages.dev/` и проверить его скриптом `python scripts/audit_cloudflare_pages.py --host <имя-проекта>.pages.dev`; он не требует Cloudflare API-токенов. Выполнить визуальную проверку мобильной версии, локализаций, SEO, фактических статусов проектов и отдельной ссылки Local Media AI.
7. `noindex` и `robots.txt: Disallow: /` намеренно сохраняются до финальной приёмки. Не запускать рассылку инвесторам до завершения аудита.

## Важные ограничения

- Cloudflare Pages автоматически преобразует `/section/index.html` в чистый адрес `/section/`; аудит проверяет посетительские URL.
- Скрипты и исходники не публикуются, потому что Cloudflare получает только каталог `dist-cloudflare`.
- Сайт here.now не удаляется, домен/DNS не переключается и редиректы не создаются.
- Если нужен собственный домен, его регистрация и DNS-настройка выполняются отдельно с подтверждением владельца.
- Local Media AI всё ещё в режиме release HOLD; сайт не заменяет независимую Windows/NVIDIA E2E-приёмку.

Официальные источники: https://developers.cloudflare.com/pages/configuration/headers/ , https://developers.cloudflare.com/pages/get-started/git-integration/ , https://developers.cloudflare.com/pages/configuration/branch-build-controls/ , https://developers.cloudflare.com/pages/configuration/serving-pages/ .
