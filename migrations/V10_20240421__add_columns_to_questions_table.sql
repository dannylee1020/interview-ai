ALTER TABLE questions
ADD COLUMN qid INT,
ADD COLUMN company text,
DROP COLUMN topic;

ALTER TABLE questions
ADD CONSTRAINT unique_qid UNIQUE (qid);
