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

CREATE TABLE IF NOT EXISTS preference (
    id uuid PRIMARY KEY,
    user_id uuid,
    created_at timestamptz,
    updated_at timestamptz,
    theme text,
    language text,
    model text
);

-- for upsert
ALTER TABLE preference
ADD CONSTRAINT unique_user_id UNIQUE (user_id);

-- for converting user_id to uuid
ALTER TABLE context
ADD COLUMN user_id_temp uuid;

ALTER TABLE context
DROP COLUMN user_id;

ALTER TABLE context
RENAME COLUMN user_id_temp TO user_id;

-- add fk relationship
ALTER TABLE context
ADD CONSTRAINT fk_user
FOREIGN KEY (user_id)
REFERENCES users(id);


ALTER TABLE preference
ADD CONSTRAINT fk_user
FOREIGN KEY (user_id)
REFERENCES users(id);

ALTER TABLE questions
ADD COLUMN qid INT,
ADD COLUMN company text,
DROP COLUMN topic;

ALTER TABLE questions
ADD CONSTRAINT unique_qid UNIQUE (qid);

CREATE TABLE IF NOT EXISTS solution (
    id uuid PRIMARY KEY,
    title text,
    qid int UNIQUE,
    hints text,
    FOREIGN KEY (qid) REFERENCES questions(qid)
);

CREATE TABLE IF NOT EXISTS solution_code (
    id uuid PRIMARY KEY,
    language text,
    code text,
    qid int,
    FOREIGN KEY (qid)  REFERENCES questions(qid),
    CONSTRAINT unique_solution_key UNIQUE (qid, language)
);
