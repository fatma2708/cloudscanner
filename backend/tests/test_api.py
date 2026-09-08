"""API integration tests against the FastAPI app."""

from fastapi.testclient import TestClient


def test_health(client: TestClient):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_demo_analyze(client: TestClient):
    resp = client.get("/api/v1/demo/analyze")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scores"]["overall"] > 0
    assert data["finops"]["current_monthly"] > 0
    assert data["comparison"]["providers"]
    assert data["graph"]["nodes"]
    assert data["recommendations"]


def test_demo_modes(client: TestClient):
    for mode in ("lowest-cost", "max-availability", "balanced"):
        resp = client.get(f"/api/v1/demo/analyze/{mode}")
        assert resp.status_code == 200
        assert resp.json()["optimization"]["mode"] == mode


def test_auth_register_login(client: TestClient):
    email = "test@example.com"
    password = "password123"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Test"},
    )
    assert reg.status_code == 201
    token = reg.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == email

    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200

    bad = client.post("/api/v1/auth/login", json={"email": email, "password": "wrongpass1"})
    assert bad.status_code == 401


def test_projects_crud(client: TestClient):
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/v1/projects",
        json={"name": "My Infra", "source_type": "zip"},
        headers=headers,
    )
    assert created.status_code == 201
    project_id = created.json()["id"]

    listed = client.get("/api/v1/projects", headers=headers)
    assert len(listed.json()) == 1

    deleted = client.delete(f"/api/v1/projects/{project_id}", headers=headers)
    assert deleted.status_code == 204


def test_analyze_zip_flow(client: TestClient):
    import io
    import zipfile

    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project = client.post(
        "/api/v1/projects",
        json={"name": "Zip project", "source_type": "zip", "default_region": "us-east-1"},
        headers=headers,
    ).json()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "main.tf", 'resource "aws_instance" "web" {\n  instance_type = "t3.medium"\n}\n'
        )
    buf.seek(0)

    resp = client.post(
        f"/api/v1/analyses/{project['id']}/analyze-zip",
        headers=headers,
        files={"file": ("infra.zip", buf.getvalue(), "application/zip")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["analysis_id"]
    assert data["summary"]["resource_count"] == 1

    listed = client.get("/api/v1/analyses", headers=headers)
    assert any(a["id"] == data["analysis_id"] for a in listed.json())

    detail = client.get(f"/api/v1/analyses/{data['analysis_id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["resources"]


def _login(client: TestClient) -> str:
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "flow@example.com", "password": "password123"},
    )
    if resp.status_code == 409:
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "flow@example.com", "password": "password123"},
        )
    return resp.json()["access_token"]
