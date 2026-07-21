from fastapi.testclient import TestClient

from daily_planner.api.app import app


def test_health():
    client = TestClient(app)
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_plans_endpoint(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LLM_PROVIDER", "rule")
    monkeypatch.setenv("TASK_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "daily.db"))
    from daily_planner.config import get_settings

    get_settings.cache_clear()
    client = TestClient(app)
    response = client.post("/api/v1/plans", json={"input": "今天口语练习30分钟"})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["scheduled_tasks"]


def test_cancel_and_review_endpoints(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LLM_PROVIDER", "rule")
    monkeypatch.setenv("TASK_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "daily.db"))
    from daily_planner.config import get_settings

    get_settings.cache_clear()
    client = TestClient(app)
    created = client.post("/api/v1/plans", json={"input": "今天口语练习30分钟"}).json()
    task_id = created["data"]["scheduled_tasks"][0]["id"]
    plan_date = created["data"]["scheduled_tasks"][0]["plan_date"]

    canceled = client.post(f"/api/v1/tasks/{task_id}/cancel")
    reviewed = client.post("/api/v1/review", json={"date": plan_date})

    assert canceled.status_code == 200
    assert canceled.json()["success"] is True
    assert reviewed.status_code == 200
    assert reviewed.json()["success"] is True


def test_sync_queue_endpoint(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TASK_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "daily.db"))
    from daily_planner.config import get_settings

    get_settings.cache_clear()
    client = TestClient(app)
    response = client.get("/api/v1/sync/queue")

    assert response.status_code == 200
    assert response.json()["success"] is True
