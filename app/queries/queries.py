signup_user = """
    INSERT INTO users (id, email, encrypted_password, created_at, provider, username, name)
    VALUES (%s, %s, %s, %s, %s, %s, %s);
"""

reset_password = """
    UPDATE users
    SET encrypted_password = %s, updated_at = %s
    WHERE email= %s;
"""
