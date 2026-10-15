-- «Правда или действие»: remember which turns were played in that mode,
-- so after «Сделали» the next player gets the same choice again.
ALTER TABLE turns ADD COLUMN play_mode TEXT;
