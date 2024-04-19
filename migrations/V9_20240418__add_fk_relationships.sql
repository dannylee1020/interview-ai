ALTER TABLE context
ADD CONSTRAINT fk_user
FOREIGN KEY (user_id)
REFERENCES users(id);


ALTER TABLE preference
ADD CONSTRAINT fk_user
FOREIGN KEY (user_id)
REFERENCES users(id);