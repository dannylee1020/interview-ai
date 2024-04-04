CREATE TABLE IF NOT EXISTS context (
    id uuid PRIMARY KEY,
    user_id text,
    created_at timestamptz,
    role text,
    content text
);