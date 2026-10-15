-- Short practical notes shown under a card in «🧸 Понадобится».
-- The cards themselves no longer repeat them.
UPDATE items
SET usage_text = 'Снимается одним движением.'
WHERE code = 'blindfold';

UPDATE items
SET usage_text = 'Только стерильный набор и стерильный лубрикант. Буж входит под собственным весом — не толкать и не крутить; при боли или жжении сразу прекратить. После — помочиться.'
WHERE code = 'sterile_urethral_kit';

UPDATE items SET name = 'Верёвка' WHERE code = 'rope';
