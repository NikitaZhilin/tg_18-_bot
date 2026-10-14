-- Toys the couple owns, so cards can name them and appear only when enabled
-- in «Настройки → Реквизит».
INSERT OR IGNORE INTO items (code, name, min_level, max_level, categories, usage_text, randomizable) VALUES
    ('dildo_large', 'Большой фаллос', 3, 4, 'task,pose',
     'Много лубриканта, вводить медленно, глубину задаёт принимающий.', 1),
    ('dildo_heated', 'Фаллос с нагревом и вибрацией', 3, 4, 'task,pose',
     'Включите нагрев заранее, начните с минимальной вибрации и фрикций.', 1),
    ('tentacle', 'Щупальце', 3, 4, 'task,pose',
     'Много лубриканта, вводить медленно, без резких движений.', 1),
    ('clit_suction', 'Вакуумный стимулятор клитора', 2, 4, 'task,pose,desire',
     'Начните с минимального режима; партнёрша сама говорит, когда прибавить.', 1),
    ('whip', 'Плётка', 4, 4, 'task',
     'Только ягодицы, бёдра и верх спины; мимо поясницы, позвоночника и лица.', 0),
    ('gag', 'Кляп', 4, 4, 'task',
     'Нос должен дышать свободно. Вместо стоп-слова — бросить предмет из руки. Не дольше десяти минут.', 0),
    ('anal_plug_s', 'Анальная пробка — маленькая', 2, 4, 'task,pose',
     'Широкое основание, много лубриканта, вводить медленно на выдохе.', 1),
    ('anal_plug_m', 'Анальная пробка — средняя', 3, 4, 'task,pose',
     'Сначала разогрев пальцами или маленькой пробкой, много лубриканта.', 1),
    ('anal_plug_l', 'Анальная пробка — большая', 3, 4, 'task',
     'Только после средней и хорошего разогрева, очень медленно, без усилия.', 0),
    ('inflatable_plug', 'Надувная пробка', 3, 4, 'task',
     'Много лубриканта; накачивать по одному нажатию и спрашивать после каждого.', 0),
    ('suction_cups', 'Вакуумные насадки', 3, 4, 'task',
     'Слабый вакуум, не дольше нескольких минут, снимать, сначала стравив воздух.', 0),
    ('cock_ring', 'Эрекционное кольцо', 3, 4, 'task,pose',
     'Не дольше 20 минут; снять сразу при онемении или холоде.', 1),
    ('penis_sleeve', 'Насадка на член', 3, 4, 'task,pose',
     'Наденьте с лубрикантом и проверьте, что насадка не пережимает.', 1),
    ('masturbator', 'Мастурбатор', 2, 4, 'task',
     'Много лубриканта; темп задаёт тот, на ком мастурбатор.', 1),
    ('anal_hook', 'Анальный крюк', 4, 4, 'task',
     'Много лубриканта; верёвку от крюка крепить к запястьям с запасом, не натягивать и не дёргать.', 0),
    ('massage_candle', 'Свеча для массажа', 2, 4, 'task',
     'Только специальная массажная свеча. Задуйте её и проверьте масло на своём запястье.', 0),
    ('strapon', 'Страпон', 3, 4, 'task,pose',
     'Много лубриканта; для анального проникновения — после разогрева пальцами или мини-фаллосом.', 1),
    ('dildo_mini', 'Мини-фаллос', 2, 4, 'task,pose',
     'Удобен для первого анального опыта и разогрева. Много лубриканта.', 1),
    ('estim', 'Электростимулятор', 3, 4, 'task',
     'Только ниже пояса, никогда через грудь, шею и голову. Не при кардиостимуляторе, болезнях сердца, эпилепсии и беременности, не в воде. Начинать с минимума.', 0);

-- Rope is now used for real tying on level 4.
UPDATE items
SET usage_text = 'Не обвязывайте шею; между верёвкой и кожей — два пальца; ножницы рядом; проверяйте пальцы на онемение.'
WHERE code = 'rope';

-- Vibrator over underwear is fine for «Разогрев».
UPDATE items SET min_level = 2 WHERE code = 'vibrator' AND min_level > 2;

-- Speculum for level 4; urethral play uses the existing sterile kit.
INSERT OR IGNORE INTO items (code, name, min_level, max_level, categories, usage_text, randomizable) VALUES
    ('speculum', 'Расширитель', 4, 4, 'task',
     'Много лубриканта, раскрывать медленно и только по команде принимающего; при боли сразу закрыть.', 0);
UPDATE items SET name = 'Уретральные бужи (стерильные)' WHERE code = 'sterile_urethral_kit';


-- Toys the couple already owns: every new game starts with them enabled.
ALTER TABLE items ADD COLUMN default_owned INTEGER NOT NULL DEFAULT 0 CHECK (default_owned IN (0, 1));
UPDATE items SET default_owned = 1 WHERE code IN (
    'dildo_large', 'dildo_heated', 'dildo_mini', 'tentacle', 'vibrator', 'clit_suction',
    'whip', 'rope', 'gag', 'anal_plug_s', 'anal_plug_m', 'anal_plug_l', 'inflatable_plug',
    'suction_cups', 'sterile_urethral_kit', 'cock_ring', 'penis_sleeve', 'masturbator',
    'speculum', 'anal_hook', 'estim', 'massage_candle', 'strapon', 'lubricant', 'blindfold', 'clamps'
);

-- The game that is already open gets them too, unless props were set by hand.
INSERT OR IGNORE INTO session_items (session_id, item_code, frequency)
SELECT s.id, i.code, 2
FROM sessions s
JOIN items i ON i.default_owned = 1
WHERE s.status IN ('draft', 'active')
  AND NOT EXISTS (SELECT 1 FROM session_items si WHERE si.session_id = s.id);

UPDATE items SET name = 'Зажимы на соски' WHERE code = 'clamps';
