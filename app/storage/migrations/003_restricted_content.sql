ALTER TABLE sessions ADD COLUMN allow_restricted_content INTEGER NOT NULL DEFAULT 0
CHECK (allow_restricted_content IN (0, 1));

INSERT OR IGNORE INTO content_collections (code, name, description) VALUES
    ('restricted_content', 'Закрытые темы', 'Карточки, доступные только после админского пароля');
