import os
import uuid

import httpx

BASE_URL = "http://127.0.0.1:8000/auth"
TEST_DATA = {"email": "test-email@test.com", "password": "testpassword123"}
TEST_FORM_DATA = {"username": "test-email@test.com", "password": "testpassword123"}
TEST_OAUTH_DATA = {
    "email": "test-oauth@test.com",
    "token": "test-token-123",
    "provider": "github",
}
TEST_RESET_PW = {"email": "test-email@test.com", "new_password": "newtestpassword123"}

client = httpx.Client()


def test_successful_signup_user():
    res = client.post(BASE_URL + "/signup", data=TEST_DATA)

    assert res.status_code == 201
    assert res.json() == {"message": "user successfully created"}


def test_duplicate_signup_email():
    res = client.post(BASE_URL + "/signup", data=TEST_DATA)

    assert res.status_code == 200
    assert res.json() == {"message": "Email already in use"}


def test_db_insert_signup(db_conn):
    res = db_conn.execute(
        "select * from users where email = 'test-email@test.com'"
    ).fetchone()

    assert res is not None
    assert res["email"] == "test-email@test.com"


def test_successful_login(db_conn, redis_conn):
    res = client.post(BASE_URL + "/login", data=TEST_FORM_DATA)
    res_data = res.json()

    db_data = db_conn.execute(
        "select * from users where email = 'test-email@test.com'"
    ).fetchone()
    r_token = redis_conn.get(f"rt:whitelist:{db_data['id']}")

    assert res.status_code == 201
    assert "access_token" in res.json()
    assert "refresh_token" in res.json()
    assert r_token.decode("utf-8") == res_data["refresh_token"]


def test_incorrect_credential_login():
    res = client.post(
        BASE_URL + "/login",
        data={"username": "test-email@test.com", "password": "wrongpassword123"},
    )

    assert res.status_code == 401
    assert "Incorrect username or password" in res.text


def test_successful_oauth(db_conn, redis_conn):
    res = client.post(BASE_URL + "/login/oauth", json=TEST_OAUTH_DATA)
    res_data = res.json()

    db_data = db_conn.execute(
        "select * from users where email = 'test-oauth@test.com' and provider != 'native'"
    ).fetchone()
    r_token = redis_conn.get(f"rt:whitelist:{db_data['id']}")

    assert res.status_code == 201
    assert "access_token" in res.json()
    assert "refresh_token" in res.json()
    assert r_token.decode("utf-8") == res_data["refresh_token"]


def test_oauth_db_insert(db_conn):
    user = db_conn.execute(
        "select * from users where email = 'test-oauth@test.com' and provider = 'github'"
    ).fetchone()

    assert user is not None
    assert user["email"] == "test-oauth@test.com"


def test_successful_token_refresh():
    res = client.post(BASE_URL + "/login", data=TEST_FORM_DATA)
    res_data = res.json()
    ref_token = res_data["refresh_token"]

    headers = {"Authorization": f"Bearer {ref_token}"}
    res = client.get(BASE_URL + "/token/refresh", headers=headers)

    assert res.status_code == 200
    assert "access_token" in res.json()
    assert "refresh_token" in res.json()


def test_invalid_refresh_token():
    ref_token = uuid.uuid4()

    headers = {"Authorization": f"Bearer {ref_token}"}
    res = client.get(BASE_URL + "/token/refresh", headers=headers)

    assert res.status_code == 401
    assert "refresh token not valid" in res.text


def test_refresh_token_is_blacklisted(redis_conn):
    res = client.post(BASE_URL + "/login", data=TEST_FORM_DATA)
    res_data = res.json()
    old_token = res_data["refresh_token"]

    headers = {"Authorization": f"Bearer {old_token}"}
    client.get(BASE_URL + "/logout", headers=headers)

    ref_res = client.get(BASE_URL + "/token/refresh", headers=headers)

    assert ref_res.status_code == 401
    assert "please login again" in ref_res.text


def test_successful_logout(redis_conn, db_conn):
    res = client.post(BASE_URL + "/login", data=TEST_FORM_DATA)
    data = res.json()
    ref_token = data["refresh_token"]

    db_res = db_conn.execute(
        "select * from users where email = 'test-email@test.com'"
    ).fetchone()

    headers = {"Authorization": f"Bearer {ref_token}"}
    res = client.get(BASE_URL + "/logout", headers=headers)

    c = redis_conn.get(f"rt:whitelist:{db_res['id']}")

    assert res.status_code == 200
    assert res.json() == {"message": "user successfully logged out"}
    assert c is None


def test_successful_reset_password():
    res = client.put(BASE_URL + "/reset-password", json=TEST_RESET_PW)

    assert res.status_code == 201
    assert res.json() == {"message": "password updated successfully"}


def test_db_update_reset_password(db_conn):
    user = db_conn.execute(
        "select * from users where email = %s", (TEST_RESET_PW["email"],)
    ).fetchone()

    db_conn.close()

    assert user is not None
    assert user["updated_at"] is not None


def test_invalid_reset_password():
    res = client.put(
        BASE_URL + "/reset-password",
        json={"email": "test-oauth@test.com", "new_password": "testpassword"},
    )

    assert res.status_code == 401
    assert "This user uses provider for login. Can't reset password" in res.text
