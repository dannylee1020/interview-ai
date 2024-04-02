CREATE TABLE IF NOT EXISTS questions (
    id uuid PRIMARY KEY,
    topic text,
    title text,
    difficulty text,
    tags text [],
    problem text
);