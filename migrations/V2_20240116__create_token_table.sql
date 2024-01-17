CREATE TABLE public.token (
    id uuid NOT NULL PRIMARY KEY,
    user_id uuid,
    token text,
    created_at timestamptz
)