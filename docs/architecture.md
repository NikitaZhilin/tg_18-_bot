# Устройство

Python 3, aiogram 3, SQLite. Точка входа — `python -m app` (`app/main.py`): загрузка настроек,
миграции, импорт карточек из `content/*.csv`, проверка `getMe`, публикация меню команд,
heartbeat и long polling.

## Модули

```text
app/
  main.py               сборка Dispatcher, порядок routers (fallback — последним)
  config.py             .env → Config
  domain.py             PickFilter, PickedCard, FORBIDDEN_RISK_TAGS, ANAL_MODES
  labels.py             русские названия уровней, категорий, тегов, коллекций
  bot_commands.py       меню «/» по ролям
  handlers/
    start.py            /start, /help; в группе передаёт в group_play
    group_play.py       пароль группы, «🙋 Я играю», пароль в админке
    game.py             меню, выдача карточек, «Сделали», отказ → штраф, таймер,
                        «Правда или действие», переключатель Экстрима
    game_settings.py    игрушки, границы, «🍑 Анал»
    desires.py          сохранённые купоны
    safety.py           /stopword, «Закончить игру»
    membership.py       бота добавили в группу
    admin*.py           админка: карточки, реквизит, импорт/экспорт, игра на троих
    common.py           проверки доступа (личка / группа), лимит людей в группе
    screens.py          экран меню, правка сообщения на месте
    errors.py, fallback.py
  services/
    game_service.py     сессии, очередь игроков, выдача и замена, отказ, статус
    session_settings.py уровни, игрушки, границы, режим анала (mixin)
    card_picker.py      выбор карточки по фильтрам, тегам, реквизиту, без повторов
    group_access.py     пароль групп (PBKDF2), открытые группы, состав игроков
    threesome.py        флаг игры на троих
    safety_service.py   остановка и завершение игры
    timer_service.py    таймеры с повторной доставкой
    desire_service.py, feedback_service.py, admin_service.py
    content_importer.py, content_readers.py, export_service.py
    error_report.py     отчёты владельцам
  storage/
    database.py         SQLite, транзакции, миграции
    fsm.py              FSM aiogram в SQLite (TTL 2 часа)
    repositories/       sessions, users, cards
    migrations/*.sql
```

## Игра

- **Сессия** — одна открытая игра на чат (`chat_key = chat_id:thread_id`).
- **Игроки:** `player_1_id`, `player_2_id`, `player_3_id` (только на троих). В личке все слоты —
  хозяин чата, бот чередует имена `PLAYER_1_NAME` / `PLAYER_2_NAME`. В группе — участники из
  `group_players` в порядке «🙋 Я играю», имена берутся оттуда.
- **Очередь:** `current_player_slot` → следующий по кругу (`GameService._next_slot`).
- **Ход-карточка:** `turns` (`status`, `source`, `play_mode`: `tod:<уровень>:<интенсивность>` для
  «Правды или действия»). `used_cards` не даёт повторов; штрафы могут повторяться, когда кончились.
- **Выбор карточки:** `CardPicker.pick(PickFilter)` — уровень/уровни, категория, интенсивность,
  коллекция, Экстрим (`allow_restricted_content` сессии), колода на троих, `allow_repeats`.
  Штрафы — только при отказе. Затем отсекаются теги из `session_blocked_tags` (границы и анал)
  и карточки без включённого реквизита.
- **Отказ:** `GameService.refuse_card` закрывает карточку со статусом `skipped` и выдаёт штраф
  того же уровня тому же игроку.

## Доступ

- Личка: `ALLOWED_TELEGRAM_USER_IDS`.
- Группа: `group_access.registry` — группа открыта паролем (`unlocked_groups`) и пользователь
  в `group_players`. Лимит людей в группе: игроки + бот (`common.max_group_members`).
- Админ: `ADMIN_TELEGRAM_USER_IDS`.

## Контент

См. [content.md](content.md). Импорт при старте: новые карточки добавляются, изменённые без правок
в админке обновляются, изменённые в админке становятся конфликтами (`seed_conflicts`).
