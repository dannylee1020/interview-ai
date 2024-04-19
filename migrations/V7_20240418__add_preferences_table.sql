CREATE TABLE IF NOT EXISTS preference (
    id uuid PRIMARY KEY,
    user_id uuid,
    created_at timestamptz,
    updated_at timestamptz,
    theme text,
    language text,
    model text
);

ALTER TABLE preference
ADD CONSTRAINT unique_user_id UNIQUE (user_id);
