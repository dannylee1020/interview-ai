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
