# AI Tools Ecosystem v0.12 — Security Review публикации here.now

**Дата:** 2026-11-10  
**Статус:** `LOCAL_STATIC_PASS` + `MOCK_NETWORK_PASS` / `LIVE_NOT_TESTED` / `GITHUB_NOT_UPDATED` / `NOT_DEPLOYED`.

## 1. Проверенный объект

- **Файл:** `scripts/publish_herenow.py`
- **Локальный исходник:** `/mnt/data/ai_tools_deploy_workflow/scripts/publish_herenow.py`
- **Предлагаемый публичный путь после утверждения:** `my-project-01012026/ai-tools-ecosystem/scripts/publish_herenow.py`.
- **Назначение:** проверить 32 файла статического сайта v0.12 по фиксированному SHA-256 manifest; по явной команде опубликовать их как персональный постоянный сайт here.now. Не публикует токен, не подключает кошелёк, не выполняет сборку установщика.

## 2. Все места обращения к ключу

| Место | Действие | Контроль |
|---|---|---|
| `main()` | Читает `os.environ.get('HERENOW_API_KEY', '')` только после `--publish` | Dry run не требует ключа; не выводится |
| `publish()` | Проверяет префикс `hnk_` и минимальную длину | Отсекает отсутствие очевидно неверного ключа, не проверяет криптографически |
| `request_json()` | Передаёт ключ в `Authorization: Bearer ...` только к заранее разрешённому here.now API | HTTPS + ограничение hostname, path и method; 3xx не обрабатываются; пользовательские proxy/TLS правила сохранены |
| `.github/workflows/deploy-herenow.yml` | Ссылается на `${{ secrets.HERENOW_API_KEY }}` в `env` **единственного шага публикации** | Значение хранится в GitHub Environment secret, не в коммите; `main` only + `here-now-production` |

**Фактические значения ключей не присутствуют** в проверенных текстовых файлах (сигнатуры `hnk_...`, GitHub PAT, AWS access keys, PEM PRIVATE KEY). Отсутствие найденных совпадений не является криптографическим доказательством, что в произвольном тексте невозможно скрыть секрет.

## 3. Исчерпывающий список сетевых операций

Только после `--publish`:

1. `POST https://here.now/api/v1/publish` — создание сайта. Заголовок `Authorization: Bearer <HERENOW_API_KEY>`; JSON с metadata 32 файлов.
2. При `--slug` сначала `GET https://here.now/api/v1/publish/<slug>` — чтение `currentVersionId` с тем же Bearer.
3. При `--slug` далее `PUT https://here.now/api/v1/publish/<slug>` — обновление с Bearer и `baseVersionId` для предотвращения перезаписи после конкурентных изменений.
4. `PUT https://<account>.r2.cloudflarestorage.com/<signed-path>?<signed-query>` — файл через выданный here.now **presigned URL**, только `Content-Type`; `HERENOW_API_KEY` сюда **не передаётся**. Подписанная строка в URL является самостоятельным временным секретом и также **не выводится в логи**.
5. `POST https://here.now/api/v1/publish/<slug>/finalize` — завершение с Bearer и JSON `versionId`. Адрес должен совпасть с исходным host и slug.

Клиентом по умолчанию используется `https://here.now`; низкоуровневая функция допускает `https://api.here.now` как известный альтернативный API host. Ни сторонние аналитические API, ни платежи, ни Solana RPC, ни GitHub API скрипт **не вызывает**. Скрипт не имеет `curl`, `wget`, `subprocess`, `os.system`, `eval`, `exec` и не открывает WebSocket.

## 4. Найденные и устранённые слабые места

- **HIGH:** стандартные HTTP redirects могли перенаправить запрос с Authorization. **Исправлено:** `_NoRedirect` на всех запросах.
- **HIGH:** список файлов в server response не сверялся с полным ожидаемым набором. **Исправлено:** strict equality `uploads + skipped`, защита от дублей, неизвестных путей и заголовков.
- **HIGH:** `finalizeUrl` проверял только host. **Исправлено:** строгое соответствие API origin, `slug` и `/api/v1/publish/<slug>/finalize`.
- **HIGH:** программный параметр API origin мог направить Bearer в произвольный host. **Исправлено:** только `here.now`/`api.here.now`.
- **MEDIUM:** обновление без проверки версии могло затереть изменения в live-site. **Исправлено:** `GET currentVersionId` + `baseVersionId`; сервер должен ответить конфликтом при race.
- **MEDIUM:** в промежуточной версии принудительно отключалась поддержка системного proxy. **Удалено**, чтобы не обходить сетевые политики. TLS verification по умолчанию включён.
- **MEDIUM:** у workflow токен был доступен всему job. **Исправлено:** Environment secret только в шаге публикации, `main` only, запуск только `workflow_dispatch`, `contents:read`, checkout без persisted credentials.
- **MEDIUM:** неприкреплённые версии GitHub Actions. **Исправлено:** `checkout@11bd71901bbe5b1630ceea73d27597364c9af683` (v4.2.2) и `setup-python@a26af69be951a213d495a4c3e4e4022e16d87065` (v5.6.0), SHA сверены с тегами official GitHub actions.
- Никаких комментариев или команд с рекомендациями отключить проверки/SSL/логирование безопасности не осталось.

## 5. Результаты доступных проверок

- `unittest discover`: **23/23 PASS**, исключительно на моках без обращения к here.now и без реального ключа.
- `python scripts/publish_herenow.py` без аргументов: **PASS, dry run**, проверено 32 файла, сеть не использована.
- `py_compile`: **PASS**, скрипт и тесты компилируются.
- Поиск ключей в 37 source/site файлах: **0 совпадений** для реальных токеноподобных строк, AWS keys и PEM PRIVATE KEY.
- Проверка workflow: **PASS** по статическим assertions; секрет упоминается только в одном `secrets.HERENOW_API_KEY`.
- Проверка исходного сайта: **32 файла** по фиксированному локальному SHA-256 manifest, пути symlink/traversal запрещены.

### SHA-256 изменённых файлов

- `scripts/publish_herenow.py`: `42d4c0e08bd52bce40b50f211af7ce6b2260815cac9b863fa8dbb97658400529` *(см. контрольную сумму в актуальном пакете после изменения; при дальнейшем редактировании будет другой хэш)*
- Окончательные SHA-256 всех артефактов перечислены в `AUDITED_FILES_SHA256.txt`.

## 6. Оставшиеся условия допуска

- GitHub `Environment: here-now-production` должен быть **создан владельцем**, иметь Required reviewers и ограничение deploy branches; само упоминание `environment:` в YAML не устанавливает эти политики.
- Никогда не помещать ключ в `Repository secrets`, README, issue, чаты или логи; использовать только Environment secret GitHub Actions или локальную переменную окружения.
- Нет реального `HERENOW_API_KEY`, поэтому **не было** создания сайта, обновления, upload или finalize на реальном сервере; подтверждён только синтетический контракт и документация API.
- Нет живого E2E-свидетельства, что here.now действительно отправляет требуемые HTTP Security Headers. До live-аудита сайт `HOSTING_HOLD`.
- Даже TLS и разрешённые хосты не устраняют полностью риск компрометации GitHub runner, доверенной системы TLS, прокси организации, backend here.now и служебного аккаунта. Внешние signed URLs принадлежат механизму Here.now/Cloudflare R2.

## 7. Рекомендация

**APPROVED_FOR_REVIEW / NOT_COMMITTED**: можно предложить перенос прозрачных UTF-8 файлов в **публичный GitHub** только после ознакомления владельца; значения токенов не копировать. Публикацию сайта выполнять отдельно, строго после настройки охраняемого Environment и отдельного разрешения владельца.

Официальный источник спецификации API: https://here.now/docs
