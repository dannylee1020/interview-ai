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

CREATE DATABASE vectors;

