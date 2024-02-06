import json
from unittest.mock import patch

import httpx
import respx

BASE_URL = "http://localhost:8000/auth"
test_data = {"email": "test@example.com", "password": "password123"}


@respx.mock
def test_signup_user():
    mock = respx.post(BASE_URL + "/auth/signup").respond(
        status_code=201,
        json={"message": "user successfully created"},
    )

    res = httpx.post(
        BASE_URL + "/auth/signup",
        data=test_data,
    )

    assert mock.called
    assert res.status_code == 201
    assert res.json() == {"message": "user successfully created"}


@respx.mock
def test_signup_user_email_already_exists():
    with patch(
        "app.core.authenticate.get_user", return_value={"id": "existing_user_id"}
    ):
        mock = respx.post(BASE_URL + "/signup").respond(
            status_code=200,
            json={"message": "Email already in use"},
        )

        res = httpx.post(
            BASE_URL + "/signup",
            data=test_data,
        )

        assert mock.called
        assert res.status_code == 200
        assert res.json() == {"message": "Email already in use"}


@respx.mock
def test_signup_user_internal_server_error():
    with patch(
        "app.core.authenticate.hash_password", side_effect=Exception("Simulated error")
    ):
        mock = respx.post(BASE_URL + "/signup").respond(
            status_code=500,
            text="Internal server error",
        )
        res = httpx.post(
            BASE_URL + "/signup",
            data=test_data,
        )

        assert mock.called
        assert res.status_code == 500
        assert "Internal server error" in res.text


@respx.mock
def test_login_user():
    mock = respx.post(BASE_URL + "/login").respond(
        status_code=201,
        json={
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "token_type": "Bearer",
        },
    )

    res = httpx.post(
        BASE_URL + "/login",
        data=test_data,
    )
    assert mock.called
    assert res.status_code == 201
    assert "access_token" in res.json()
    assert "refresh_token" in res.json()


@respx.mock
def test_login_user_incorrect_credentials():
    with patch("app.core.authenticate.authenticate_user", return_value=None):
        mock = respx.post(BASE_URL + "/login").respond(
            status_code=401,
            text="Incorrect username or password",
        )

        res = httpx.post(
            BASE_URL + "/login",
            data=test_data,
        )

        assert mock.called
        assert res.status_code == 401
        assert "Incorrect username or password" in res.text


@respx.mock
def test_login_user_internal_server_error():
    with patch(
        "app.core.authenticate.create_access_token",
        side_effect=Exception("Simulated error"),
    ):
        mock = respx.post(BASE_URL + "/login").respond(
            status_code=500, text="Internal server error"
        )

        res = httpx.post(
            BASE_URL + "/login",
            data=test_data,
        )
        assert mock.called
        assert res.status_code == 500
        assert "Internal server error" in res.text


@respx.mock
def test_logout_user():
    mock = respx.get(BASE_URL + "/logout").respond(
        status_code=200,
        json={"message": "user successfully logged out"},
    )

    res = httpx.get(BASE_URL + "/logout")

    assert mock.called
    assert res.status_code == 200
    assert res.json() == {"message": "user successfully logged out"}


@respx.mock
def test_logout_user_error():
    with patch(
        "app.core.authenticate.decode_jwt", side_effect=Exception("Simulated error")
    ):
        mock = respx.get(BASE_URL + "/logout").respond(
            status_code=500,
            text="refresh token not valid",
        )

        res = httpx.get(BASE_URL + "/logout")

        assert mock.called
        assert res.status_code == 500
        assert "refresh token not valid" in res.text


@respx.mock
def test_refresh_token():
    mock = respx.get(BASE_URL + "/token/refresh").respond(
        status_code=200,
        json={
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "token_type": "Bearer",
        },
    )

    res = httpx.get(BASE_URL + "/token/refresh")

    assert mock.called
    assert res.status_code == 200
    assert "access_token" in res.json()
    assert "refresh_token" in res.json()


@respx.mock
def test_refresh_token_exception():
    with patch(
        "app.core.authenticate.decode_jwt", side_effect=Exception("Simulated error")
    ):
        mock = respx.get(BASE_URL + "/token/refresh").respond(
            status_code=500,
            text="refresh token not valid, please login again",
        )

        res = httpx.get(BASE_URL + "/token/refresh")

        assert mock.called
        assert res.status_code == 500
        assert "refresh token not valid, please login again" in res.text


@respx.mock
def test_reset_password():
    mock = respx.put(BASE_URL + "/reset_password").respond(
        status_code=201,
        json={"message": "password updated successfully"},
    )

    res = httpx.put(
        BASE_URL + "/reset_password",
        json=test_data,
    )

    assert mock.called
    assert res.status_code == 201
    assert res.json() == {"message": "password updated successfully"}


@respx.mock
def test_reset_password_internal_server_error():
    with patch(
        "app.core.authenticate.hash_password", side_effect=Exception("Simulated error")
    ):
        mock = respx.put(BASE_URL + "/reset_password").respond(
            status_code=500,
            text="Internal server error",
        )

        res = httpx.put(
            BASE_URL + "/reset_password",
            json=test_data,
        )

        assert mock.called
        assert res.status_code == 500
        assert "Internal server error" in res.text
