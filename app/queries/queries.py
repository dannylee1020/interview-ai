signup_user = """
    INSERT INTO users (id, email, encrypted_password, created_at, provider, username, name, status)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
"""

reset_password = """
    UPDATE users
    SET encrypted_password = %s, updated_at = %s
    WHERE email= %s;
"""

deactivate_user = """
    UPDATE users
    SET status = %s, updated_at = %s
    WHERE email = %s;
"""

get_user_by_email = """
    SELECT
    FROM users
        *
    WHERE email = %s;
"""

get_similar_vectors = """
    with a as (
        SELECT
            role,
            content,
            created_at
        FROM context
        ORDER BY content_embedding created_at <-> %s::vector LIMIT %s;
    )

    SELECT role, content FROM a ORDER BY created_at;
"""

upsert_preference = """
    INSERT INTO preference (id, user_id, created_at, updated_at, theme, language, model)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (user_id)
    DO UPDATE SET
        updated_at = EXCLUDED.updated_at,
        theme = EXCLUDED.theme,
        language = EXCLUDED.language,
        model = EXCLUDED.model
"""
