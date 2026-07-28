# Схема данных

Актуальная схема не поддерживается отдельным монолитным SQL-файлом. Единственный источник
истины — последовательность миграций:

```text
app/storage/migrations/001_initial.sql
...
app/storage/migrations/016_cleanup_legacy_session_state.sql
```

Такой подход гарантирует одинаковое обновление новой и уже работающей базы.

## Области

- Пользователи и контекст: `users`, `chat_contexts`.
- Игра: `sessions`, `turns`, `used_cards`, `session_enabled_levels`.
- Контент: `cards`, `content_collections`, `card_collection_items`.
- Реквизит: `items`, `card_required_items`, `session_items`.
- Согласие и границы: `session_consents`, `daily_slot_consents`,
  `session_blocked_tags`, `safety_events`.
- Таймеры: `timers`.
- Желания: `saved_desires`.
- Админка: `admin_actions`, `card_versions`, `seed_conflicts`, `card_feedback`.
- Временные persisted-состояния: `fsm_states`, `session_setting_drafts`.
- Эксплуатация: `content_imports`, `app_heartbeats`, `schema_migrations`.

Удаленные прикладные поля карточки не следует добавлять в импорт:

```text
safety_level
requires_both_opt_in
requires_safeword_check
```

Они могут встречаться в исторической миграции `001`, но удаляются миграцией `008`.
Устаревшие переключатели уровня 4 и жесткого режима удаляются из `sessions` миграцией `016`.
