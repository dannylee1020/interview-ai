ALTER TABLE context
ADD COLUMN user_id_temp uuid;

ALTER TABLE context
DROP COLUMN user_id;

ALTER TABLE context
RENAME COLUMN user_id_temp TO user_id;
