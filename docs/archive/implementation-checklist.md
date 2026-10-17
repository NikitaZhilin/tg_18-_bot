# Сверка реализации с ТЗ v4

Дата проверки: 2026-07-28.

| Требование | Статус | Реализация |
|---|---|---|
| Whitelist и admin whitelist | Готово | `app/config.py`, общие guards |
| Два аккаунта и один аккаунт с двумя слотами | Готово | `current_player_slot` |
| Последовательное согласие двух слотов раз в сутки | Готово | `daily_slot_consents` |
| Завершение игры без повторного согласия в тот же день | Готово | `safe:end_game` |
| Обычные разделы 1-4 без дублирующих переключателей | Готово | `app/keyboards/game.py` |
| Отдельный `Экстрим` по паролю админки | Готово | `restricted_content` |
| Удаление неисполняемых safety-полей | Готово | миграция `008` |
| Рулетка без повторов | Готово | `used_cards` |
| Атомарная замена карточки | Готово | `GameService.replace_active_card` |
| Persisted timer с ограниченными retry | Готово | миграция `013`, `TimerService` |
| Реквизит с частотой и совместимостью | Готово | `session_items`, `CardPicker` |
| Persisted черновики реквизита и границ | Готово | `session_setting_drafts` |
| Persisted FSM админки | Готово | `SQLiteFSMStorage` |
| Желания по виртуальному владельцу | Готово | миграция `010`, `DesireService` |
| Просмотр и использование желаний | Готово | `handlers/desires.py` |
| Каталог карточек по 10 | Готово | `handlers/admin_cards.py` |
| CRUD карточек и реквизита | Готово | `AdminService`, admin handlers |
| История и восстановление версии | Готово | `card_versions` |
| Конфликты seed-обновлений | Готово | `seed_conflicts` |
| Кнопка `На доработку` с отключением и заменой | Готово | `GameService.request_card_revision` |
| Очередь карточек на доработке | Готово | `review_status = needs_review` |
| Последовательная проверка с сохранением прогресса | Готово | `card_review_progress` |
| Русский XLSX и обратный импорт | Готово | export/import services |
| Контент-аудит всех CSV | Готово | `scripts/audit_card_content.py` |
| Опасный генератор seed удален | Готово | файл отсутствует |
| Модули разделены по ответственности | Готово | handlers/services readers/settings |
| CI перед deploy | Готово | `.github/workflows/ci-deploy.yml` |
| Backup, health-check и rollback | Готово | `scripts/deploy_server.sh` |
| Транзакционное применение миграций | Готово | `Database.apply_migrations` |

## Обязательные проверки

```text
python scripts/audit_card_content.py
python scripts/import_cards.py --check content/cards.csv
python scripts/import_cards.py --check content/restricted_cards.csv
python scripts/smoke_start.py
python -m compileall -q app scripts tests
python -m pytest
bash -n scripts/deploy_server.sh
```

Фактический результат полного прогона фиксируется в commit и CI, а не поддерживается вручную
как постоянное число в этом документе.

## Сознательное ограничение

Отдельный системный пользователь, SSH-only вход и ротация ранее переданных секретов не входят
в этот этап по прямому решению владельца. Секреты при этом не добавляются в Git.
