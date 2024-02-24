import httpx

BASE_URL = "http://127.0.0.1:8000/user"

TEST_FORM_DATA = {
    "username": "test-email@test.com",
    "password": "newtestpassword123",
}

client = httpx.Client()


def test_successful_retrieve_profile():
    res = client.post("http://127.0.0.1:8000/auth/login", data=TEST_FORM_DATA)
    res_data = res.json()

    headers = {"Authorization": f"Bearer {res_data['access_token']}"}
    res = client.get(BASE_URL + "/profile", headers=headers)
    res_data = res.json()

    assert res.status_code == 200
    assert res_data["name"] == "John Doe"


def test_profile_exception():
    headers = {"Authorization": f"Bearer random-token-123"}
    res = client.get(BASE_URL + "/profile", headers=headers)

    assert res.status_code == 401
    assert "Could not validate credentials" in res.text


def test_successful_deactivate_user():
    res = client.post("http://127.0.0.1:8000/auth/login", data=TEST_FORM_DATA)
    res_data = res.json()

    headers = {"Authorization": f"Bearer {res_data['access_token']}"}
    res = client.get(BASE_URL + "/deactivate", headers=headers)
    res_data = res.json()

    assert res.status_code == 200
    assert "Account successfully deactivated" in res.text


def test_deactivate_exception():
    headers = {"Authorization": f"Bearer random-token-123"}
    res = client.get(BASE_URL + "/deactivate", headers=headers)

    assert res.status_code == 401
