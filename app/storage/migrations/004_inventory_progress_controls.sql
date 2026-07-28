ALTER TABLE items ADD COLUMN min_level INTEGER NOT NULL DEFAULT 1
CHECK (min_level BETWEEN 1 AND 4);

ALTER TABLE items ADD COLUMN max_level INTEGER NOT NULL DEFAULT 4
CHECK (max_level BETWEEN 1 AND 4);

ALTER TABLE items ADD COLUMN categories TEXT NOT NULL DEFAULT 'task,pose,desire';

ALTER TABLE items ADD COLUMN usage_text TEXT;

ALTER TABLE items ADD COLUMN randomizable INTEGER NOT NULL DEFAULT 1
CHECK (randomizable IN (0, 1));

ALTER TABLE session_items ADD COLUMN frequency INTEGER NOT NULL DEFAULT 2
CHECK (frequency BETWEEN 1 AND 3);

ALTER TABLE turns ADD COLUMN selected_item_code TEXT;

UPDATE items SET
    min_level = 1,
    max_level = 3,
    categories = 'task,desire',
    usage_text = 'Используйте кубик льда для нескольких коротких прикосновений к коже. Не держите его на одном месте.'
WHERE code = 'ice';

UPDATE items SET
    min_level = 1,
    max_level = 4,
    categories = 'task,pose,desire',
    usage_text = 'Добавьте масло или гель для массажа на удобном участке тела.'
WHERE code = 'oil';

UPDATE items SET
    min_level = 2,
    max_level = 4,
    categories = 'task,pose',
    usage_text = 'Используйте веревку только как свободный визуальный реквизит. Не фиксируйте шею и не затягивайте конечности.'
WHERE code = 'rope';

UPDATE items SET
    min_level = 2,
    max_level = 4,
    categories = 'task,pose',
    usage_text = 'Один партнер надевает повязку, которую можно снять одним движением. Второй заранее говорит, что собирается сделать.'
WHERE code = 'blindfold';

UPDATE items SET
    min_level = 3,
    max_level = 4,
    categories = 'task,pose,desire',
    usage_text = 'Добавьте вибратор на заранее согласованной мощности. Принимающий партнер управляет усилением и остановкой.'
WHERE code = 'vibrator';

UPDATE items SET
    min_level = 1,
    max_level = 2,
    categories = 'task,desire',
    usage_text = 'Включите выбранную музыку в наушниках или используйте их как часть сенсорной паузы.'
WHERE code = 'headphones';

UPDATE items SET
    min_level = 1,
    max_level = 4,
    categories = 'task,desire',
    usage_text = 'Зажгите свечу только для освещения и атмосферы. Не используйте пламя или горячий воск на теле.'
WHERE code = 'candle';

UPDATE items SET
    min_level = 3,
    max_level = 4,
    categories = 'task',
    usage_text = 'Используйте только специальные регулируемые зажимы и сразу снимите их при боли, онемении или изменении цвета кожи.'
WHERE code = 'clamps';

UPDATE items SET
    min_level = 1,
    max_level = 3,
    categories = 'task,desire',
    usage_text = 'Выберите небольшой безопасный продукт и заранее проверьте аллергию и комфорт обоих.'
WHERE code = 'food';

INSERT OR IGNORE INTO items (code, name, min_level, max_level, categories, usage_text) VALUES
    ('lubricant', 'Лубрикант', 3, 4, 'task,pose,desire', 'Используйте достаточное количество совместимого лубриканта и добавляйте его по просьбе принимающего партнера.'),
    ('gloves', 'Одноразовые перчатки', 3, 4, 'task,desire', 'Используйте новые одноразовые перчатки подходящего размера и замените их при повреждении.'),
    ('towel', 'Полотенце', 1, 4, 'task,pose,desire', 'Положите рядом чистое полотенце для комфорта и завершения сцены.'),
    ('pillow', 'Подушка', 1, 4, 'task,pose', 'Подложите подушку так, чтобы снизить нагрузку и сделать положение удобнее.'),
    ('chair', 'Устойчивый стул', 1, 4, 'task,pose', 'Используйте устойчивый стул без колес и поставьте его на нескользкую поверхность.'),
    ('sterile_urethral_kit', 'Стерильный уретральный набор', 4, 4, 'task,desire', 'Допустим только стерильный специализированный набор. Не используйте бытовые или самодельные предметы.');

UPDATE items SET randomizable = 0 WHERE code = 'sterile_urethral_kit';
