CREATE TABLE users (
    id uuid NOT NULL PRIMARY KEY,
    email text,
    encrypted_password text,
    created_at timestamptz,
    updated_at timestamptz,
    deleted_at timestamptz
);

ALTER TABLE users
ADD COLUMN provider text;

ALTER TABLE users
ADD COLUMN username text,
ADD COLUMN name text;

ALTER TABLE users
ADD COLUMN status text;

CREATE TABLE IF NOT EXISTS questions (
    id uuid PRIMARY KEY,
    topic text,
    title text,
    difficulty text,
    tags text [],
    problem text
);

CREATE TABLE IF NOT EXISTS context (
    id uuid PRIMARY KEY,
    user_id text,
    created_at timestamptz,
    role text,
    content text
);