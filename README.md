# tg_18_bot

Приватный Telegram-бот для пошаговой игры двух взрослых партнеров.

## Быстрый старт

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python scripts\smoke_start.py
python scripts\import_cards.py --check content\cards.csv
python -m pytest -q
```

Для реального запуска заполнить `.env`:

```text
BOT_TOKEN=
ALLOWED_TELEGRAM_USER_IDS=
ADMIN_TELEGRAM_USER_IDS=
PLAYER_1_NAME=
PLAYER_2_NAME=
SINGLE_ACCOUNT_TWO_PLAYERS=false
ADMIN_CONTENT_PASSWORD_SHA256=
```

Токены, пароли и приватные ID не коммитятся.

Если два человека играют с одного Telegram-аккаунта, укажите один `ALLOWED_TELEGRAM_USER_IDS`
и включите:

```text
SINGLE_ACCOUNT_TWO_PLAYERS=true
```

Закрытая коллекция карточек не выпадает в игре по умолчанию. Для доступа админ открывает
`Админка -> Закрытые темы: выключены`, вводит пароль, и текущая сессия получает доступ к карточкам
из коллекции `restricted_content`. В `.env` хранится только SHA-256 пароля:

```powershell
python -c "import hashlib, getpass; print(hashlib.sha256(getpass.getpass().encode()).hexdigest())"
```

Настройки реквизита действуют в пределах текущей сессии. Для каждого предмета выбирается
частота `выключен / редко / иногда / часто`; бот добавляет только предметы, совместимые с
уровнем и типом выпавшей карточки.

Кнопка `В меню` не завершает активную карточку. Прогресс хранится в SQLite, а вернуться к
карточке можно кнопкой `Продолжить текущую карточку`.

## Команды

- `/start` - старт и игровое меню;
- `/help` - справка;
- `/status` - технический статус для владельцев;
- `/admin` - Telegram-админка контента;
- `/reset` - завершить сессию после подтверждения;
- `/stopword` - мгновенно остановить сессию.

## Документы

Актуальное ТЗ и аналитика лежат в `docs/`.
