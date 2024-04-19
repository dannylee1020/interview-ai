import httpx

BASE_URL = "http://127.0.0.1:8000/user"

TEST_FORM_DATA = {
    "username": "test-email@test.com",
    "password": "newtestpassword123",
}

PREF_DATA = {"theme": "dark", "language": "python", "model": "claude-sonnet"}

UPDATE_PREF_DATA = {"theme": "light", "language": "python", "model": "claude-sonnet"}

client = httpx.Client()
AUTH_URL = "http://127.0.0.1:8000/auth"

res = client.post(AUTH_URL + "/login", data=TEST_FORM_DATA)
res_data = res.json()
AUTH_HEADERS = {"Authorization": f"Bearer {res_data['access_token']}"}


def test_successful_retrieve_profile():
    res = client.get(BASE_URL + "/profile", headers=AUTH_HEADERS)
    res_data = res.json()

    assert res.status_code == 200
    assert res_data["name"] == "John Doe"


def test_profile_exception():
    headers = {"Authorization": f"Bearer random-token-123"}
    res = client.get(BASE_URL + "/profile", headers=headers)

    assert res.status_code == 401
    assert "Could not validate credentials" in res.text


def test_successful_deactivate_user():
    res = client.get(BASE_URL + "/deactivate", headers=AUTH_HEADERS)
    res_data = res.json()

    assert res.status_code == 200
    assert "Account successfully deactivated" in res.text


def test_deactivate_exception():
    headers = {"Authorization": f"Bearer random-token-123"}
    res = client.get(BASE_URL + "/deactivate", headers=headers)

    assert res.status_code == 401


def test_save_preference():
    res = client.post(
        BASE_URL + "/preference/save",
        headers=AUTH_HEADERS,
        json=PREF_DATA,
    )

    assert res.status_code == 200


def test_get_preference():
    res = client.get(
        BASE_URL + "/preference/get",
        headers=AUTH_HEADERS,
    )
    res_data = res.json()

    assert res.status_code == 200
    assert res_data["model"] == "claude-sonnet"


def test_upsert_preference():
    res = client.post(
        BASE_URL + "/preference/save",
        headers=AUTH_HEADERS,
        json=UPDATE_PREF_DATA,
    )
    res_data = res.json()

    updated = client.get(BASE_URL + "/preference/get", headers=AUTH_HEADERS)
    updated_data = updated.json()

    assert res.status_code == 200
    assert updated_data["theme"] == "light"
