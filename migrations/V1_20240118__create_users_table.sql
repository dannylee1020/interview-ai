CREATE TABLE public.users (
    id uuid NOT NULL PRIMARY KEY,
    email text,
    encrypted_password text,
    created_at timestamptz,
    updated_at timestamptz,
    deleted_at timestamptz
)

