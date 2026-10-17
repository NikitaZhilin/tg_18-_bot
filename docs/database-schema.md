# Схема данных

Источник истины — последовательность миграций `app/storage/migrations/*.sql`. Они применяются
при старте по порядку; каждая — в одной транзакции вместе с записью в `schema_migrations`.

## Таблицы

| Область | Таблицы |
|---|---|
| Пользователи и чаты | `users` (роль `player_1/2/3`), `chat_contexts` |
| Игра | `sessions` (`player_1_id`, `player_2_id`, `player_3_id`, `play_mode` couple/threesome, `current_player_slot`, `allow_restricted_content` — Экстрим вкл/выкл), `turns` (`play_mode` для «Правды или действия»), `used_cards`, `session_enabled_levels` |
| Группы | `unlocked_groups` (группы, открытые паролем), `group_players` (кто нажал «Я играю», порядок) |
| Настройки бота | `bot_settings`: `group_password` (PBKDF2-хеш), `threesome_enabled` |
| Контент | `cards`, `content_collections` (`base_tasks`, `kamasutra_inspired_poses`, `restricted_content`, `threesome`), `card_collection_items` |
| Реквизит | `items` (`default_owned`, `usage_text`), `card_required_items`, `session_items` |
| Границы и безопасность | `session_blocked_tags` (границы и режим «🍑 Анал»), `safety_events`, `session_consents`, `daily_slot_consents` |
| Таймеры | `timers` |
| Желания | `saved_desires` |
| Админка | `admin_actions`, `card_versions`, `seed_conflicts`, `card_feedback`, `card_review_progress` |
| Временное состояние | `fsm_states`, `session_setting_drafts` |
| Эксплуатация | `content_imports`, `app_heartbeats`, `schema_migrations` |

## Миграции

| № | Что |
|---|---|
| 001–018 | Исходная схема, один аккаунт на двоих, Экстрим, реквизит, каталог, черновики настроек, конфликты обновлений, таймеры, жалобы, проверка карточек, семантический аудит (июль 2026) |
| 019 | Игрушки пары, `default_owned`, новые предметы |
| 020 | `turns.play_mode` для «Правды или действия» |
| 021–023 | Описания игрушек сокращены |
| 024 | Игра на троих: `player_3`, `play_mode`, `bot_settings`, коллекция `threesome`; слоты пересозданы с `player_3` |
| 025 | Описания игрушек убраны; `unlocked_groups`, `group_players`; Экстрим включён в открытых играх |

Миграция 024 удаляет колонки (`ALTER TABLE … DROP COLUMN`) — нужна SQLite 3.35+, на сервере 3.45.

Поля `safety_level`, `requires_both_opt_in`, `requires_safeword_check` удалены миграцией 008 —
не добавляйте их в импорт.
