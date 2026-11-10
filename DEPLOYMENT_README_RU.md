# here.now — безопасная ручная публикация AI Tools Ecosystem

**Статус: NOT_DEPLOYED / PRELAUNCH.** Скрипт и workflow проверены локально, но **не публиковались** и ещё не отправлены в GitHub из этой проверки. Токен Solana не выпущен, продаж нет.

## Публикуемые файлы

Скрипт передаёт **только 32 файла**, перечисленные в `scripts/SITE_SHA256SUMS.txt`. Проверяется хэш SHA-256 каждого файла, имена файлов, отсутствие symlink и изменение файла непосредственно перед PUT. Главная — `index.html`.

## Ключ и логирование

- `HERENOW_API_KEY` берётся **только из переменной окружения** на этапе `--publish`. В Git и файлы он не записывается. Не вставляйте значение в README, настройки workflow, issue или сообщения чата.
- Для GitHub Actions используйте **Environment secret** `HERENOW_API_KEY` в окружении `here-now-production` (Settings → Environments → here-now-production → Environment secrets). **Не хранить токен как repository secret**, чтобы не выдавать его другим workflow.
- В `here-now-production` настройте **Required reviewers** и (если доступно) **Deployment branches: only protected branches / main**. Пока эти ограничения не настроены, не запускайте workflow и считайте публикацию на HOLD.
- У шага публикации единственный доступ к `HERENOW_API_KEY`. В остальных шагах этой переменной нет. В логи выводится только число проверенных файлов, сообщение BLOCKED с названием исключения и (при успехе) публичный URL без токенов.
- Исключения не сериализуются в логи, потому что могут содержать подписанные URL. Никаких `set -x`, дампов окружения, вывода заголовков Authorization и URL подписанных загрузок.

## Сетевые запросы (только при явном `--publish`)

1. `POST https://here.now/api/v1/publish` — создать персональный сайт, Bearer API-key и JSON с 32 метаданными файлов.
2. При обновлении: `GET https://here.now/api/v1/publish/<slug>` — прочитать текущий `currentVersionId`; затем `PUT https://here.now/api/v1/publish/<slug>` с `baseVersionId`. Если сайт изменился параллельно, here.now отклонит публикацию по конфликту версии, вместо затирания чужого обновления.
3. `PUT https://<account>.r2.cloudflarestorage.com/...` — отправить байты файлов по одноразовым подписанным HTTPS URL из ответа here.now; **без Bearer/API key**. Проверяются суффикс хоста, Content-Type и точный набор файлов.
4. `POST https://here.now/api/v1/publish/<slug>/finalize` — финализация того же slug; Bearer API-key и JSON с `versionId`.

Запросы выполняются через HTTPS **без автоматических перенаправлений**, но с учётом системных HTTPS-прокси и доверенных TLS-сертификатов. Скрипт не отключает сетевые политики организации. `api.here.now` допустим только как альтернативная доверенная точка API при явном конфигурировании вызова (CLI по умолчанию публикует через `here.now`). Произвольные API-хосты и пути отклоняются.

## Запуск и критерии

1. На своей машине проверить без сети: `python -m unittest discover -s tests -p 'test_publish_herenow.py' -v` и `python scripts/publish_herenow.py`.
2. Настроить защищённое окружение GitHub Actions, добавить **Environment secret**, назначить контролирующего Reviewer.
3. В GitHub → Actions выбрать `Deploy static website to here.now (manual)` → `Run workflow` строго из `main`; slug оставить пустым для **первого сайта** либо ввести существующий для обновления.
4. Перед публикацией workflow ещё раз запускает тесты и проверку хэшей. Публикация требует отдельного подтверждения защищённого окружения.
5. После публикации проверяются реальный TLS/HTTPS, HTTP CSP (включая frame-ancestors), X-Content-Type-Options, HSTS, 404 и редиректы; до этого **LIVE_SECURITY_HOLD**.

**Ограничения:** это статические и мок-тесты без реальных токенов и HTTPS-запросов; они не гарантируют безопасность аккаунта, сетевых посредников, here.now и неизменность runner. Проверка неподконтрольных окружений и независимый аудит остаются обязательными. Реальные токены никогда не вводятся в тестах.
