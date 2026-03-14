"""Integration tests for the API using FastAPI TestClient.

Note: tests/conftest.py sets AUTOCOIN_DATABASE_URL and AUTOCOIN_JWT_SECRET
to a temp directory BEFORE any autocoin modules are imported.
"""
import pytest
from fastapi.testclient import TestClient

from autocoin.app import create_app
from tests.test_parsers import _make_alipay_csv


@pytest.fixture(scope="module")
def app():
    """Create a test app (DB is configured via conftest.py env vars)."""
    application = create_app()
    yield application


@pytest.fixture(scope="module")
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers(client):
    """Register a test user and return auth headers."""
    resp = client.post("/api/v1/auth/register", json={
        "username": "testuser",
        "password": "testpass123",
    })
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestAuth:
    def test_register(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "username": "newuser",
            "password": "password123",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["username"] == "newuser"

    def test_register_duplicate(self, client):
        # First register
        client.post("/api/v1/auth/register", json={
            "username": "dupuser",
            "password": "password123",
        })
        # Duplicate
        resp = client.post("/api/v1/auth/register", json={
            "username": "dupuser",
            "password": "password456",
        })
        assert resp.status_code == 409

    def test_login_success(self, client):
        # Register first
        client.post("/api/v1/auth/register", json={
            "username": "loginuser",
            "password": "password123",
        })
        resp = client.post("/api/v1/auth/login", json={
            "username": "loginuser",
            "password": "password123",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_wrong_password(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "username": "loginuser",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401
        assert "用户名或密码错误" in resp.json()["detail"]

    def test_me(self, client, auth_headers):
        resp = client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["username"] == "testuser"


class TestTransactions:
    def test_create(self, client, auth_headers):
        resp = client.post("/api/v1/transactions", headers=auth_headers, json={
            "transaction_time": "2025-01-15 12:30:00",
            "direction": "expense",
            "amount": 25.80,
            "category": "餐饮美食",
            "counterparty": "美团",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["amount"] == 25.80
        assert data["category"] == "餐饮美食"

    def test_list(self, client, auth_headers):
        resp = client.get("/api/v1/transactions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_update_category(self, client, auth_headers):
        # Create a transaction
        create_resp = client.post("/api/v1/transactions", headers=auth_headers, json={
            "transaction_time": "2025-01-16 09:00:00",
            "direction": "income",
            "amount": 100,
        })
        tx_id = create_resp.json()["id"]
        # Update category
        resp = client.put(f"/api/v1/transactions/{tx_id}", headers=auth_headers, json={
            "category": "工资收入",
        })
        assert resp.status_code == 200
        assert resp.json()["category"] == "工资收入"

    def test_delete(self, client, auth_headers):
        create_resp = client.post("/api/v1/transactions", headers=auth_headers, json={
            "transaction_time": "2025-01-17 10:00:00",
            "direction": "expense",
            "amount": 5,
        })
        tx_id = create_resp.json()["id"]
        resp = client.delete(f"/api/v1/transactions/{tx_id}", headers=auth_headers)
        assert resp.status_code == 200
        # Verify it's gone from list
        get_resp = client.get(f"/api/v1/transactions/{tx_id}", headers=auth_headers)
        assert get_resp.status_code == 404

    def test_categories(self, client, auth_headers):
        resp = client.get("/api/v1/transactions/categories", headers=auth_headers)
        assert resp.status_code == 200
        assert "categories" in resp.json()

    def test_batch_delete(self, client, auth_headers):
        # Create 3 transactions
        ids = []
        for i in range(3):
            r = client.post("/api/v1/transactions", headers=auth_headers, json={
                "transaction_time": f"2025-02-0{i+1} 12:00:00",
                "direction": "expense",
                "amount": 10 + i,
            })
            ids.append(r.json()["id"])
        # Batch delete first 2
        resp = client.post("/api/v1/transactions/batch/delete", headers=auth_headers, json={
            "ids": ids[:2],
        })
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 2

    def test_export_csv(self, client, auth_headers):
        resp = client.get("/api/v1/transactions/export/csv", headers=auth_headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    def test_export_excel(self, client, auth_headers):
        resp = client.get("/api/v1/transactions/export/excel", headers=auth_headers)
        assert resp.status_code == 200
        assert "spreadsheet" in resp.headers["content-type"]

    def test_unauthorized(self, client):
        resp = client.get("/api/v1/transactions")
        assert resp.status_code in (401, 403)  # No token → depends on FastAPI version


class TestClassificationRules:
    def test_rule_crud(self, client, auth_headers):
        create_resp = client.post("/api/v1/rules", headers=auth_headers, json={
            "name": "美团自动归类",
            "priority": 10,
            "is_active": True,
            "match_counterparty": "美团",
            "match_product": "外卖",
            "match_payment_method": "",
            "match_transaction_type": "",
            "category": "餐饮美食",
            "remark": "规则自动归类",
        })
        assert create_resp.status_code == 201
        rule = create_resp.json()
        assert rule["name"] == "美团自动归类"
        assert rule["category"] == "餐饮美食"

        list_resp = client.get("/api/v1/rules", headers=auth_headers)
        assert list_resp.status_code == 200
        assert any(item["id"] == rule["id"] for item in list_resp.json())

        update_resp = client.put(f"/api/v1/rules/{rule['id']}", headers=auth_headers, json={
            "name": "美团优先规则",
            "priority": 5,
            "is_active": True,
            "match_counterparty": "美团",
            "match_product": "",
            "match_payment_method": "",
            "match_transaction_type": "",
            "category": "外卖",
            "remark": "自动备注",
        })
        assert update_resp.status_code == 200
        assert update_resp.json()["priority"] == 5
        assert update_resp.json()["category"] == "外卖"

        delete_resp = client.delete(f"/api/v1/rules/{rule['id']}", headers=auth_headers)
        assert delete_resp.status_code == 200

    def test_rule_applies_to_manual_transaction(self, client, auth_headers):
        rule_resp = client.post("/api/v1/rules", headers=auth_headers, json={
            "name": "滴滴归类交通",
            "priority": 20,
            "is_active": True,
            "match_counterparty": "滴滴",
            "match_product": "",
            "match_payment_method": "",
            "match_transaction_type": "",
            "category": "交通出行",
            "remark": "规则命中",
        })
        assert rule_resp.status_code == 201

        tx_resp = client.post("/api/v1/transactions", headers=auth_headers, json={
            "transaction_time": "2025-03-01 08:30:00",
            "direction": "expense",
            "amount": 18.5,
            "category": "",
            "counterparty": "滴滴出行",
            "product": "快车",
            "payment_method": "微信支付",
            "remark": "",
        })
        assert tx_resp.status_code == 201
        data = tx_resp.json()
        assert data["category"] == "交通出行"
        assert data["remark"] == "规则命中"

    def test_rule_applies_to_file_import(self, client, auth_headers):
        rule_resp = client.post("/api/v1/rules", headers=auth_headers, json={
            "name": "星巴克归类咖啡",
            "priority": 30,
            "is_active": True,
            "match_counterparty": "星巴克",
            "match_product": "",
            "match_payment_method": "",
            "match_transaction_type": "",
            "category": "咖啡饮品",
            "remark": "",
        })
        assert rule_resp.status_code == 201

        csv_bytes = _make_alipay_csv([
            [
                "2025-03-02 10:00:00", "", "星巴克", "sb@example.com",
                "拿铁", "支出", "32.00", "支付宝", "交易成功",
                "2025030210000001", "M100", "",
            ],
        ])
        files = {"file": ("alipay.csv", csv_bytes, "text/csv")}
        import_resp = client.post("/api/v1/imports", headers=auth_headers, files=files)
        assert import_resp.status_code == 200

        list_resp = client.get("/api/v1/transactions?search=%E6%98%9F%E5%B7%B4%E5%85%8B", headers=auth_headers)
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        assert any(item["category"] == "咖啡饮品" for item in items)
