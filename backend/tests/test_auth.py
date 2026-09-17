def test_register_returns_token_and_logs_in_directly(client):
    resp = client.post(
        "/api/auth/register", json={"email": "new@example.com", "password": "testpass123"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["access_token"]
    assert body["user"]["email"] == "new@example.com"


def test_duplicate_register_returns_validation_error(client):
    client.post("/api/auth/register", json={"email": "dup@example.com", "password": "testpass123"})
    resp = client.post(
        "/api/auth/register", json={"email": "dup@example.com", "password": "anotherpass"}
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_short_password_rejected(client):
    resp = client.post("/api/auth/register", json={"email": "x@example.com", "password": "short"})
    assert resp.status_code == 422


def test_login_success(client):
    client.post(
        "/api/auth/register", json={"email": "login@example.com", "password": "testpass123"}
    )
    resp = client.post(
        "/api/auth/login", json={"email": "login@example.com", "password": "testpass123"}
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_login_wrong_password_returns_invalid_credentials(client):
    client.post(
        "/api/auth/register", json={"email": "login2@example.com", "password": "testpass123"}
    )
    resp = client.post(
        "/api/auth/login", json={"email": "login2@example.com", "password": "wrongpassword"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_unknown_email_returns_invalid_credentials(client):
    resp = client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "whatever123"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_me_requires_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "TOKEN_INVALID"


def test_me_rejects_garbage_token(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "TOKEN_INVALID"


def test_me_returns_current_user(client, auth_headers):
    headers = auth_headers("me@example.com")
    resp = client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"


def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_password_over_72_bytes_rejected_cleanly(client):
    # bcrypt 5.x raises on >72 bytes; this must be a 422, never a 500.
    resp = client.post(
        "/api/auth/register", json={"email": "long@example.com", "password": "x" * 73}
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "password" in body["error"]["fields"]


def test_multibyte_password_counted_in_bytes(client):
    # 30 characters but 90 UTF-8 bytes.
    resp = client.post(
        "/api/auth/register",
        json={"email": "utf8@example.com", "password": "éé" * 15 * 1 + "é" * 0},
    )
    # 30 x 2-byte chars = 60 bytes, allowed
    assert resp.status_code == 201, resp.text
    resp = client.post(
        "/api/auth/register", json={"email": "utf8b@example.com", "password": "€" * 25}
    )
    # 25 x 3-byte chars = 75 bytes, rejected
    assert resp.status_code == 422


def test_72_byte_password_accepted(client):
    resp = client.post(
        "/api/auth/register", json={"email": "edge@example.com", "password": "x" * 72}
    )
    assert resp.status_code == 201, resp.text


def test_auth_endpoints_are_rate_limited(client):
    from app.core import limiter as limiter_module

    limiter_module._auth_limiter = limiter_module.RateLimiter(3, 72)
    try:
        for _ in range(3):
            client.post(
                "/api/auth/login", json={"email": "rl@example.com", "password": "wrongpass1"}
            )
        resp = client.post(
            "/api/auth/login", json={"email": "rl@example.com", "password": "wrongpass1"}
        )
        assert resp.status_code == 429
        assert resp.json()["error"]["code"] == "RATE_LIMITED"
    finally:
        limiter_module._auth_limiter = None
