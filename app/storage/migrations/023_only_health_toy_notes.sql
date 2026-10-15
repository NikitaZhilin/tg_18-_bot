-- Under a card («🧸 Понадобится») keep only notes about health, one short phrase each.
-- Everything else the couple knows; oil, pillow and headphones keep a «how to use» hint
-- because they can come up as a random bonus prop.
UPDATE items SET usage_text = ''
WHERE code NOT IN ('estim', 'gag', 'rope', 'sterile_urethral_kit', 'oil', 'pillow', 'headphones');

UPDATE items SET usage_text = 'Только ниже пояса; не при проблемах с сердцем.' WHERE code = 'estim';
UPDATE items SET usage_text = 'Нос дышит свободно.' WHERE code = 'gag';
UPDATE items SET usage_text = 'Не на шею.' WHERE code = 'rope';
UPDATE items SET usage_text = 'Только стерильные.' WHERE code = 'sterile_urethral_kit';
