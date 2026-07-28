# Сверка реализации с ТЗ

Дата проверки: 2026-07-28.

## Реализовано

| Блок ТЗ | Статус | Где |
|---|---|---|
| Whitelist и admin whitelist | Готово | `app/config.py`, handlers |
| `.env`, `DRY_RUN`, `DATA_DIR`, proxy | Готово | `.env.example`, `app/config.py`, `app/main.py` |
| SQLite schema/migrations | Готово | `app/storage/migrations/001_initial.sql` |
| Сессии, turns, used_cards | Готово | `app/services/game_service.py` |
| Два игрока на одном Telegram-аккаунте | Готово | `SINGLE_ACCOUNT_TWO_PLAYERS`, `current_player_slot` |
| Реквизит с включением/отключением и частотой | Готово | `session_items.frequency`, inventory UI |
| Контекстная подстановка подходящего реквизита | Готово | `items.min_level/max_level/categories`, `CardPicker` |
| Базовое согласие обоих игроков | Готово | `game:base_consent`, `session_consents` |
| Выбор уровня/категории/интенсивности | Готово | `app/handlers/game.py` |
| Русская рулетка с safety-фильтрами | Готово | `CardPicker` |
| Рулетка выбранного уровня | Готово | `game:roulette_level:*` |
| Без повторов карточек в сессии | Готово | `used_cards`, тесты |
| Пустая выборка | Готово | game handlers |
| `/stopword` без подтверждения | Готово | `SafetyService` |
| Замена карточки без передачи хода | Готово | `game:replace`, `replace_active_card` |
| Level 4 opt-in обоими игроками | Готово | `game:level4`, `session_consents` |
| Hard intensity opt-in обоими игроками | Готово | `game:hard`, `session_consents` |
| Границы на сессию | Готово | `session_blocked_tags`, boundary UI |
| Persisted timers | Готово | `timers`, `TimerService` |
| Telegram-уведомление "Время вышло" | Готово | `TimerService.process_due_timers` |
| Desire-купоны | Готово | `saved_desires` |
| Telegram-админка `/admin` | Готово | `app/handlers/admin.py` |
| Draft/review/approve/disabled | Готово | `cards.review_status`, admin UI |
| Preview перед сохранением | Готово | admin wizard |
| Каталог раздел -> тип -> страницы по 10 | Готово | `admin_cards.py` |
| Просмотр, редактирование, архив и удаление карточек | Готово | `admin_cards.py`, `AdminService` |
| Редактирование и версии карточек | Готово | `card_versions`, `update_card_text` |
| Дублирование карточек | Готово | `duplicate_card` |
| CSV/XLSX/DOCX импорт | Готово | `ContentImporter` |
| Dry-run импорта | Готово | `/admin`, `scripts/import_cards.py --check` |
| Русский XLSX с листами уровней и списками | Готово | `ExportService` |
| Обратный импорт экспортированного XLSX | Готово | `ContentImporter` |
| Каталог реквизита и CRUD-действия | Готово | `admin_items.py`, `ItemRepository` |
| Возврат в админку/главное меню из админских экранов | Готово | `admin_navigation` |
| Возврат в меню без потери активной карточки | Готово | `game:home`, `game:current`, `sessions.active_turn_id` |
| Понятный заголовок уровня/типа/номера | Готово | `format_card`, `display_number` |
| Динамические кнопки level 4 и hard | Готово | state-aware `main_menu`, toggle handlers |
| Коллекции | Готово | `content_collections`, admin list |
| Отдельный «Экстрим» по админскому паролю | Готово | `restricted_content`, `ADMIN_CONTENT_PASSWORD_SHA256` |
| Уровни общей рулетки по умолчанию | Готово | `session_enabled_levels` |
| Стартовый seed не отменяет правки админки | Готово | `ContentImporter.skip_existing` |
| Проверка ясности всех встроенных карточек | Готово | `test_content_clarity.py` |
| Risk-tags и disabled для запрещенного | Готово | `ContentImporter`, `FORBIDDEN_RISK_TAGS` |
| Позы в стиле камасутры | Готово | `content/cards.csv`, `docs/kamasutra-pose-pack.md` |
| Целевая task-матрица 24/24/48/48 | Готово | `content/cards.csv`, тесты |
| Status/heartbeat | Готово | `/status`, `app_heartbeats` |
| Runtime scripts | Готово | `scripts/start-bot.ps1`, `stop-bot.ps1`, `status-bot.ps1` |
| Server deploy script | Готово | `scripts/deploy_server.sh` |
| Tests/smoke/import-check | Готово | `tests/`, scripts |

## Проверки

```text
python scripts\import_cards.py --check content\cards.csv
python scripts\import_cards.py --check content\restricted_cards.csv
python scripts\smoke_start.py
python -m compileall app scripts tests
python -c "import os, sys, pytest; root=os.getcwd(); os.environ['TEMP']=os.path.join(root,'.tmp','temp'); os.environ['TMP']=os.environ['TEMP']; sys.exit(pytest.main(['-q','--basetemp',os.path.join(root,'.tmp','pytest')]))"
```

Результат последней проверки: 41 тест прошел.

## Сознательные ограничения

- Токены и пароли не коммитятся.
- Проверенные встроенные hard/level 4 seed-файлы публикуются как `approved`; внешние импорты сохраняют заданный review-статус.
- Карточки «Экстрима» требуют одновременно пароля, level 4, hard opt-in и подходящего реквизита.
- Запрещенные risk-tags по-прежнему автоматически отключаются и не могут быть открыты паролем.
- Публичная web-админка не входит в MVP; Telegram-админка входит.
