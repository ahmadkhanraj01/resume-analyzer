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
