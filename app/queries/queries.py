signup_user = """
    INSERT INTO public.user
    VALUES (%s, %s, %s, %s);
"""

get_user = """
    SELECT
        *
    FROM public.user
    WHERE email = %s
"""

save_token = """
    INSERT INTO public.token
    VALUES (%s, %s, %s, %s);
"""
