CREATE TABLE public.users (
    id uuid NOT NULL PRIMARY KEY,
    email text,
    encrypted_password text,
    created_at timestamptz,
    updated_at timestamptz,
    deleted_at timestamptz
);

ALTER TABLE public.users
ADD COLUMN provider text;

ALTER TABLE public.users
ADD COLUMN username text,
ADD COLUMN name text;

ALTER TABLE public.users
ADD COLUMN status text;