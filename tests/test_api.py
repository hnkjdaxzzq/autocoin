"""Integration tests for the API using FastAPI TestClient.

Note: tests/conftest.py sets AUTOCOIN_DATABASE_URL and AUTOCOIN_JWT_SECRET
to a temp directory BEFORE any autocoin modules are imported.
"""
import pytest
from fastapi.testclient import TestClient

from autocoin.routers.ai_classification import (
    DEFAULT_PROMPT_TEMPLATE,
    _filter_classifiable_transactions,
    _render_prompt_template,
)
from autocoin.app import create_app
from tests.test_parsers import _make_alipay_csv, _make_cmb_securities_xls


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
        "invite_code": "tarikz",
    })
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestAuth:
    def test_register(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "username": "newuser",
            "password": "password123",
            "invite_code": "tarikz",
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
            "invite_code": "tarikz",
        })
        # Duplicate
        resp = client.post("/api/v1/auth/register", json={
            "username": "dupuser",
            "password": "password456",
            "invite_code": "tarikz",
        })
        assert resp.status_code == 409

    def test_login_success(self, client):
        # Register first
        client.post("/api/v1/auth/register", json={
            "username": "loginuser",
            "password": "password123",
            "invite_code": "tarikz",
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

    def test_change_password_success(self, client, auth_headers):
        resp = client.post("/api/v1/auth/change-password", headers=auth_headers, json={
            "old_password": "testpass123",
            "new_password": "newpass4567",
        })
        assert resp.status_code == 200
        assert resp.json()["message"] == "密码修改成功"
        # Verify can login with new password
        login_resp = client.post("/api/v1/auth/login", json={
            "username": "testuser",
            "password": "newpass4567",
        })
        assert login_resp.status_code == 200
        # Change back for other tests
        token = login_resp.json()["access_token"]
        client.post("/api/v1/auth/change-password", headers={"Authorization": f"Bearer {token}"}, json={
            "old_password": "newpass4567",
            "new_password": "testpass123",
        })

    def test_change_password_wrong_old(self, client, auth_headers):
        resp = client.post("/api/v1/auth/change-password", headers=auth_headers, json={
            "old_password": "wrongpassword",
            "new_password": "newpass4567",
        })
        assert resp.status_code == 400
        assert "原密码错误" in resp.json()["detail"]

    def test_change_password_same_password(self, client, auth_headers):
        resp = client.post("/api/v1/auth/change-password", headers=auth_headers, json={
            "old_password": "testpass123",
            "new_password": "testpass123",
        })
        assert resp.status_code == 400
        assert "新密码不能与原密码相同" in resp.json()["detail"]

    def test_change_password_unauthorized(self, client):
        resp = client.post("/api/v1/auth/change-password", json={
            "old_password": "testpass123",
            "new_password": "newpass4567",
        })
        assert resp.status_code == 401

    def test_change_password_invalid_new(self, client, auth_headers):
        # Too short
        resp = client.post("/api/v1/auth/change-password", headers=auth_headers, json={
            "old_password": "testpass123",
            "new_password": "short",
        })
        assert resp.status_code == 422
        # No letter
        resp = client.post("/api/v1/auth/change-password", headers=auth_headers, json={
            "old_password": "testpass123",
            "new_password": "1234567890",
        })
        assert resp.status_code == 422
        # No digit
        resp = client.post("/api/v1/auth/change-password", headers=auth_headers, json={
            "old_password": "testpass123",
            "new_password": "abcdefghijk",
        })
        assert resp.status_code == 422


class TestAIClassificationPreferences:
    def _register_headers(self, client, username):
        resp = client.post("/api/v1/auth/register", json={
            "username": username,
            "password": "password123",
            "invite_code": "tarikz",
        })
        assert resp.status_code == 201
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    def test_default_preferences(self, client):
        headers = self._register_headers(client, "aiprefsdefault")

        resp = client.get("/api/v1/ai-classification/preferences", headers=headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["categories"] == ""
        assert data["api_key"] == ""
        assert data["prompt_template"] == DEFAULT_PROMPT_TEMPLATE

    def test_update_preferences_is_user_scoped(self, client):
        headers = self._register_headers(client, "aiprefsowner")
        other_headers = self._register_headers(client, "aiprefsother")
        payload = {
            "categories": "餐饮,交通",
            "api_key": "sk-owner",
            "prompt_template": "分类: {categories}\n交易: {transactions}",
        }

        resp = client.put(
            "/api/v1/ai-classification/preferences",
            headers=headers,
            json=payload,
        )
        assert resp.status_code == 200
        assert resp.json() == payload

        owner_resp = client.get("/api/v1/ai-classification/preferences", headers=headers)
        other_resp = client.get("/api/v1/ai-classification/preferences", headers=other_headers)

        assert owner_resp.json() == payload
        assert other_resp.json()["categories"] == ""
        assert other_resp.json()["api_key"] == ""
        assert other_resp.json()["prompt_template"] == DEFAULT_PROMPT_TEMPLATE

    def test_classify_accepts_prompt_template_and_saves_preferences(self, client):
        headers = self._register_headers(client, "aiprefsclassify")
        payload = {
            "categories": "餐饮,交通",
            "api_key": "sk-classify",
            "prompt_template": "只返回 JSON。分类: {categories}\n交易:\n{transactions}",
        }

        resp = client.post(
            "/api/v1/ai-classification/classify",
            headers=headers,
            json=payload,
        )

        assert resp.status_code == 200
        assert '"total": 0' in resp.text
        prefs_resp = client.get("/api/v1/ai-classification/preferences", headers=headers)
        assert prefs_resp.status_code == 200
        assert prefs_resp.json() == payload

    def test_render_prompt_template_replaces_variables(self):
        prompt = _render_prompt_template(
            "分类={categories}\n数据={transactions}",
            [{
                "id": 7,
                "category": "旧分类",
                "counterparty": "商户",
                "product": "商品",
                "remark": "备注",
            }],
            ["餐饮", "交通"],
        )

        assert "分类=餐饮, 交通" in prompt
        assert 'id=7, current_category="旧分类"' in prompt
        assert 'counterparty="商户"' in prompt
        assert 'product="商品"' in prompt
        assert "备注" not in prompt
        assert "remark" not in prompt
        assert "{categories}" not in prompt
        assert "{transactions}" not in prompt

    def test_filter_classifiable_transactions_excludes_neutral_direction(self):
        transactions = [
            {"id": 1, "direction": "expense"},
            {"id": 2, "direction": "income"},
            {"id": 3, "direction": "neutral"},
            {"id": 4, "direction": "不计"},
            {"id": 5, "direction": "不计收支"},
        ]

        filtered = _filter_classifiable_transactions(transactions)

        assert [tx["id"] for tx in filtered] == [1, 2]


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

    def test_list_include_deleted(self, client, auth_headers):
        create_resp = client.post("/api/v1/transactions", headers=auth_headers, json={
            "transaction_time": "2025-01-18 10:00:00",
            "direction": "expense",
            "amount": 7,
        })
        tx_id = create_resp.json()["id"]

        delete_resp = client.delete(f"/api/v1/transactions/{tx_id}", headers=auth_headers)
        assert delete_resp.status_code == 200

        default_resp = client.get("/api/v1/transactions", headers=auth_headers)
        assert default_resp.status_code == 200
        assert tx_id not in [item["id"] for item in default_resp.json()["items"]]

        include_resp = client.get("/api/v1/transactions?include_deleted=true", headers=auth_headers)
        assert include_resp.status_code == 200
        include_data = include_resp.json()
        deleted_items = [item for item in include_data["items"] if item["id"] == tx_id]
        assert len(deleted_items) == 1
        assert deleted_items[0]["is_deleted"] == 1
        assert include_data["summary"]["total_count"] == include_data["total"]

    def test_include_deleted_is_user_scoped(self, client, auth_headers):
        register_resp = client.post("/api/v1/auth/register", json={
            "username": "deletedscopeuser",
            "password": "password123",
            "invite_code": "tarikz",
        })
        assert register_resp.status_code == 201
        other_headers = {"Authorization": f"Bearer {register_resp.json()['access_token']}"}

        create_resp = client.post("/api/v1/transactions", headers=other_headers, json={
            "transaction_time": "2025-01-19 10:00:00",
            "direction": "expense",
            "amount": 9,
        })
        other_tx_id = create_resp.json()["id"]
        delete_resp = client.delete(f"/api/v1/transactions/{other_tx_id}", headers=other_headers)
        assert delete_resp.status_code == 200

        include_resp = client.get("/api/v1/transactions?include_deleted=true", headers=auth_headers)
        assert include_resp.status_code == 200
        assert other_tx_id not in [item["id"] for item in include_resp.json()["items"]]

    def test_categories(self, client, auth_headers):
        resp = client.get("/api/v1/transactions/categories", headers=auth_headers)
        assert resp.status_code == 200
        assert "categories" in resp.json()

    def test_filter_by_payment_method_updates_summary(self, client, auth_headers):
        wx_resp = client.post("/api/v1/transactions", headers=auth_headers, json={
            "transaction_time": "2025-01-20 10:00:00",
            "direction": "expense",
            "amount": 12,
            "payment_method": "AUTOPAY_FILTER_WX",
        })
        card_resp = client.post("/api/v1/transactions", headers=auth_headers, json={
            "transaction_time": "2025-01-20 11:00:00",
            "direction": "expense",
            "amount": 88,
            "payment_method": "AUTOPAY_FILTER_CARD",
        })
        assert wx_resp.status_code == 201
        assert card_resp.status_code == 201

        resp = client.get(
            "/api/v1/transactions?payment_method=AUTOPAY_FILTER_WX",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        ids = [item["id"] for item in data["items"]]
        assert wx_resp.json()["id"] in ids
        assert card_resp.json()["id"] not in ids
        assert data["summary"]["total_count"] == data["total"]
        assert data["summary"]["total_expense"] == 12

    def test_payment_methods(self, client, auth_headers):
        keep_resp = client.post("/api/v1/transactions", headers=auth_headers, json={
            "transaction_time": "2025-01-21 10:00:00",
            "direction": "expense",
            "amount": 10,
            "payment_method": "测试卡",
        })
        dup_resp = client.post("/api/v1/transactions", headers=auth_headers, json={
            "transaction_time": "2025-01-21 11:00:00",
            "direction": "expense",
            "amount": 11,
            "payment_method": "测试卡",
        })
        empty_resp = client.post("/api/v1/transactions", headers=auth_headers, json={
            "transaction_time": "2025-01-21 12:00:00",
            "direction": "expense",
            "amount": 12,
            "payment_method": "",
        })
        deleted_resp = client.post("/api/v1/transactions", headers=auth_headers, json={
            "transaction_time": "2025-01-21 13:00:00",
            "direction": "expense",
            "amount": 13,
            "payment_method": "已删除卡",
        })
        other_register_resp = client.post("/api/v1/auth/register", json={
            "username": "paymentmethodscopeuser",
            "password": "password123",
            "invite_code": "tarikz",
        })
        assert other_register_resp.status_code == 201
        other_headers = {"Authorization": f"Bearer {other_register_resp.json()['access_token']}"}
        other_resp = client.post("/api/v1/transactions", headers=other_headers, json={
            "transaction_time": "2025-01-21 14:00:00",
            "direction": "expense",
            "amount": 14,
            "payment_method": "其他用户卡",
        })
        assert keep_resp.status_code == 201
        assert dup_resp.status_code == 201
        assert empty_resp.status_code == 201
        assert deleted_resp.status_code == 201
        assert other_resp.status_code == 201
        client.delete(f"/api/v1/transactions/{deleted_resp.json()['id']}", headers=auth_headers)

        resp = client.get("/api/v1/transactions/payment-methods", headers=auth_headers)
        assert resp.status_code == 200
        methods = resp.json()["payment_methods"]
        assert methods.count("测试卡") == 1
        assert "" not in methods
        assert "已删除卡" not in methods
        assert "其他用户卡" not in methods

    def test_sort_transactions(self, client, auth_headers):
        low_resp = client.post("/api/v1/transactions", headers=auth_headers, json={
            "transaction_time": "2025-01-22 10:00:00",
            "direction": "expense",
            "amount": 1,
            "payment_method": "B卡",
        })
        high_resp = client.post("/api/v1/transactions", headers=auth_headers, json={
            "transaction_time": "2025-01-22 11:00:00",
            "direction": "expense",
            "amount": 99,
            "payment_method": "A卡",
        })
        assert low_resp.status_code == 201
        assert high_resp.status_code == 201

        amount_resp = client.get(
            "/api/v1/transactions?start_date=2025-01-22&end_date=2025-01-22&sort_by=amount&sort_dir=desc",
            headers=auth_headers,
        )
        assert amount_resp.status_code == 200
        assert [item["id"] for item in amount_resp.json()["items"]][:2] == [
            high_resp.json()["id"],
            low_resp.json()["id"],
        ]

        payment_resp = client.get(
            "/api/v1/transactions?start_date=2025-01-22&end_date=2025-01-22&sort_by=payment_method&sort_dir=asc",
            headers=auth_headers,
        )
        assert payment_resp.status_code == 200
        assert [item["id"] for item in payment_resp.json()["items"]][:2] == [
            high_resp.json()["id"],
            low_resp.json()["id"],
        ]

    def test_update_direction_to_neutral_updates_summary(self, client, auth_headers):
        create_resp = client.post("/api/v1/transactions", headers=auth_headers, json={
            "transaction_time": "2025-01-23 10:00:00",
            "direction": "expense",
            "amount": 33,
            "payment_method": "不计测试卡",
        })
        assert create_resp.status_code == 201
        tx_id = create_resp.json()["id"]

        update_resp = client.put(f"/api/v1/transactions/{tx_id}", headers=auth_headers, json={
            "direction": "neutral",
        })
        assert update_resp.status_code == 200
        assert update_resp.json()["direction"] == "neutral"

        list_resp = client.get(
            "/api/v1/transactions?payment_method=%E4%B8%8D%E8%AE%A1%E6%B5%8B%E8%AF%95%E5%8D%A1",
            headers=auth_headers,
        )
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert data["total"] == 1
        assert data["items"][0]["direction"] == "neutral"
        assert data["summary"]["total_income"] == 0
        assert data["summary"]["total_expense"] == 0
        assert data["summary"]["balance"] == 0

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

    def test_batch_hard_delete(self, client, auth_headers):
        ids = []
        for i in range(2):
            r = client.post("/api/v1/transactions", headers=auth_headers, json={
                "transaction_time": f"2025-02-1{i+1} 12:00:00",
                "direction": "expense",
                "amount": 20 + i,
            })
            ids.append(r.json()["id"])

        resp = client.post("/api/v1/transactions/batch/hard-delete", headers=auth_headers, json={
            "ids": ids,
        })
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 2

        for tx_id in ids:
            get_resp = client.get(f"/api/v1/transactions/{tx_id}", headers=auth_headers)
            assert get_resp.status_code == 404

    def test_batch_hard_delete_soft_deleted(self, client, auth_headers):
        create_resp = client.post("/api/v1/transactions", headers=auth_headers, json={
            "transaction_time": "2025-02-20 12:00:00",
            "direction": "expense",
            "amount": 30,
        })
        tx_id = create_resp.json()["id"]
        delete_resp = client.delete(f"/api/v1/transactions/{tx_id}", headers=auth_headers)
        assert delete_resp.status_code == 200

        hard_delete_resp = client.post("/api/v1/transactions/batch/hard-delete", headers=auth_headers, json={
            "ids": [tx_id],
        })
        assert hard_delete_resp.status_code == 200
        assert hard_delete_resp.json()["deleted"] == 1

        include_resp = client.get("/api/v1/transactions?include_deleted=true", headers=auth_headers)
        assert include_resp.status_code == 200
        assert tx_id not in [item["id"] for item in include_resp.json()["items"]]

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


class TestSpecialDataProcessingRefunds:
    def _create_tx(self, client, headers, **overrides):
        payload = {
            "transaction_time": "2025-03-01 10:00:00",
            "direction": "expense",
            "amount": 10,
            "source": "wechat",
            "counterparty": "退款测试商户",
            "product": "退款测试商品",
            "payment_method": "退款测试卡",
        }
        payload.update(overrides)
        resp = client.post("/api/v1/transactions", headers=headers, json=payload)
        assert resp.status_code == 201
        return resp.json()

    def test_wechat_multiple_candidates_confirm_marks_only_selected_expense(self, client, auth_headers):
        older_expense = self._create_tx(
            client,
            auth_headers,
            transaction_time="2025-03-08 10:00:00",
            direction="expense",
            amount=66,
            source="wechat",
            payment_method="多候选卡",
        )
        newer_expense = self._create_tx(
            client,
            auth_headers,
            transaction_time="2025-03-09 10:00:00",
            direction="expense",
            amount=66,
            source="wechat",
            payment_method="多候选卡",
        )
        refund = self._create_tx(
            client,
            auth_headers,
            transaction_time="2025-03-10 10:00:00",
            direction="income",
            amount=66,
            source="wechat",
            payment_method="多候选卡",
        )

        search_resp = client.post("/api/v1/special-data-processing/refunds/search", headers=auth_headers)
        assert search_resp.status_code == 200
        items = [
            item for item in search_resp.json()["items"]
            if item["refund_transaction"]["id"] == refund["id"]
        ]
        assert len(items) == 1
        candidate_ids = [tx["id"] for tx in items[0]["expense_candidates"]]
        assert candidate_ids[:2] == [newer_expense["id"], older_expense["id"]]

        confirm_resp = client.post(
            "/api/v1/special-data-processing/refunds/confirm",
            headers=auth_headers,
            json={
                "items": [{
                    "refund_id": refund["id"],
                    "selected_expense_id": older_expense["id"],
                    "mark_neutral": True,
                }]
            },
        )
        assert confirm_resp.status_code == 200

        refund_after = client.get(f"/api/v1/transactions/{refund['id']}", headers=auth_headers).json()
        older_after = client.get(f"/api/v1/transactions/{older_expense['id']}", headers=auth_headers).json()
        newer_after = client.get(f"/api/v1/transactions/{newer_expense['id']}", headers=auth_headers).json()
        assert refund_after["direction"] == "neutral"
        assert older_after["direction"] == "neutral"
        assert newer_after["direction"] == "expense"
        assert refund_after["finishrefundcheck"] == 1
        assert older_after["finishrefundcheck"] == 1
        assert newer_after["finishrefundcheck"] == 0

    def test_unchecked_refund_marks_check_without_neutralizing(self, client, auth_headers):
        expense = self._create_tx(
            client,
            auth_headers,
            transaction_time="2025-03-11 10:00:00",
            direction="expense",
            amount=22,
            source="alipay",
            counterparty="不勾选测试商户",
            product="Coffee-Shop: Latte",
            payment_method="不勾选测试卡",
        )
        refund = self._create_tx(
            client,
            auth_headers,
            transaction_time="2025-03-12 10:00:00",
            direction="income",
            amount=22,
            source="alipay",
            counterparty="不勾选测试商户",
            product="退款- coffee－shop： LATTE",
            payment_method="不勾选测试卡",
        )

        confirm_resp = client.post(
            "/api/v1/special-data-processing/refunds/confirm",
            headers=auth_headers,
            json={
                "items": [{
                    "refund_id": refund["id"],
                    "selected_expense_id": expense["id"],
                    "mark_neutral": False,
                }]
            },
        )
        assert confirm_resp.status_code == 200

        refund_after = client.get(f"/api/v1/transactions/{refund['id']}", headers=auth_headers).json()
        expense_after = client.get(f"/api/v1/transactions/{expense['id']}", headers=auth_headers).json()
        assert refund_after["direction"] == "income"
        assert expense_after["direction"] == "expense"
        assert refund_after["finishrefundcheck"] == 1
        assert expense_after["finishrefundcheck"] == 1

    def test_hsbc_pulse_requires_amount_and_supports_product_normalization(self, client, auth_headers):
        matched_expense = self._create_tx(
            client,
            auth_headers,
            transaction_time="2025-03-13 10:00:00",
            direction="expense",
            amount=88,
            source="汇丰PULSE",
            counterparty="HSBC归一化商户",
            product="ABC-Shop: Latte (Grande)",
            payment_method="HSBC测试卡",
        )
        self._create_tx(
            client,
            auth_headers,
            transaction_time="2025-03-13 11:00:00",
            direction="expense",
            amount=99,
            source="汇丰PULSE",
            counterparty="HSBC归一化商户",
            product="ABC-Shop: Latte (Grande)",
            payment_method="HSBC测试卡",
        )
        refund = self._create_tx(
            client,
            auth_headers,
            transaction_time="2025-03-14 10:00:00",
            direction="income",
            amount=88,
            source="汇丰PULSE",
            counterparty="HSBC归一化商户",
            product="ａｂｃ－ｓｈｏｐ： latte （grande） 退款",
            payment_method="HSBC测试卡",
        )

        search_resp = client.post("/api/v1/special-data-processing/refunds/search", headers=auth_headers)
        assert search_resp.status_code == 200
        items = [
            item for item in search_resp.json()["items"]
            if item["refund_transaction"]["id"] == refund["id"]
        ]
        assert len(items) == 1
        assert [tx["id"] for tx in items[0]["expense_candidates"]] == [matched_expense["id"]]

    def test_refund_search_is_user_scoped(self, client, auth_headers):
        register_resp = client.post("/api/v1/auth/register", json={
            "username": "refundscopeuser",
            "password": "password123",
            "invite_code": "tarikz",
        })
        assert register_resp.status_code == 201
        other_headers = {"Authorization": f"Bearer {register_resp.json()['access_token']}"}

        self._create_tx(
            client,
            other_headers,
            transaction_time="2025-03-15 10:00:00",
            direction="expense",
            amount=44,
            source="wechat",
            payment_method="隔离测试卡",
        )
        other_refund = self._create_tx(
            client,
            other_headers,
            transaction_time="2025-03-16 10:00:00",
            direction="income",
            amount=44,
            source="wechat",
            payment_method="隔离测试卡",
        )

        search_resp = client.post("/api/v1/special-data-processing/refunds/search", headers=auth_headers)
        assert search_resp.status_code == 200
        refund_ids = [item["refund_transaction"]["id"] for item in search_resp.json()["items"]]
        assert other_refund["id"] not in refund_ids


class TestSpecialDataProcessingWealth:
    def _create_tx(self, client, headers, **overrides):
        payload = {
            "transaction_time": "2025-04-01 10:00:00",
            "direction": "income",
            "amount": 10,
            "source": "alipay",
            "counterparty": "余额宝",
            "product": "余额宝收益",
            "payment_method": "支付宝",
        }
        payload.update(overrides)
        resp = client.post("/api/v1/transactions", headers=headers, json=payload)
        assert resp.status_code == 201
        return resp.json()

    def test_wealth_search_filters_matching_alipay_yuebao_transactions(self, client, auth_headers):
        matched = self._create_tx(client, auth_headers, product="余额宝-收益发放")
        neutral = self._create_tx(client, auth_headers, direction="neutral", product="余额宝-已不计")
        wrong_source = self._create_tx(client, auth_headers, source="wechat", product="余额宝-微信")
        wrong_counterparty = self._create_tx(client, auth_headers, counterparty="其他", product="余额宝-其他")
        wrong_product = self._create_tx(client, auth_headers, product="基金收益")
        deleted = self._create_tx(client, auth_headers, product="余额宝-已删除")
        delete_resp = client.delete(f"/api/v1/transactions/{deleted['id']}", headers=auth_headers)
        assert delete_resp.status_code == 200

        register_resp = client.post("/api/v1/auth/register", json={
            "username": "wealthscopeuser",
            "password": "password123",
            "invite_code": "tarikz",
        })
        assert register_resp.status_code == 201
        other_headers = {"Authorization": f"Bearer {register_resp.json()['access_token']}"}
        other_user = self._create_tx(client, other_headers, product="余额宝-其他用户")

        search_resp = client.post("/api/v1/special-data-processing/wealth/search", headers=auth_headers)
        assert search_resp.status_code == 200
        data = search_resp.json()
        ids = [item["id"] for item in data["items"]]
        assert matched["id"] in ids
        assert neutral["id"] not in ids
        assert wrong_source["id"] not in ids
        assert wrong_counterparty["id"] not in ids
        assert wrong_product["id"] not in ids
        assert deleted["id"] not in ids
        assert other_user["id"] not in ids
        assert data["total"] == len(ids)

    def test_wealth_confirm_updates_only_selected_current_user_matches(self, client, auth_headers):
        selected = self._create_tx(client, auth_headers, product="余额宝-转入")
        unselected = self._create_tx(client, auth_headers, product="余额宝-收益")
        wrong_product = self._create_tx(client, auth_headers, product="基金收益")

        register_resp = client.post("/api/v1/auth/register", json={
            "username": "wealthconfirmuser",
            "password": "password123",
            "invite_code": "tarikz",
        })
        assert register_resp.status_code == 201
        other_headers = {"Authorization": f"Bearer {register_resp.json()['access_token']}"}
        other_user = self._create_tx(client, other_headers, product="余额宝-其他用户")

        confirm_resp = client.post(
            "/api/v1/special-data-processing/wealth/confirm",
            headers=auth_headers,
            json={"ids": [selected["id"], wrong_product["id"], other_user["id"]]},
        )
        assert confirm_resp.status_code == 200
        assert confirm_resp.json()["updated"] == 1

        selected_after = client.get(f"/api/v1/transactions/{selected['id']}", headers=auth_headers).json()
        unselected_after = client.get(f"/api/v1/transactions/{unselected['id']}", headers=auth_headers).json()
        wrong_after = client.get(f"/api/v1/transactions/{wrong_product['id']}", headers=auth_headers).json()
        assert selected_after["direction"] == "neutral"
        assert unselected_after["direction"] == "income"
        assert wrong_after["direction"] == "income"


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

class TestFileImportPreview:
    def test_preview_and_confirm_file_import(self, client, auth_headers):
        existing_csv = _make_alipay_csv([
            [
                "2025-03-20 09:00:00", "餐饮美食", "美团外卖", "mt@example.com",
                "早餐", "支出", "20.00", "支付宝", "交易成功",
                "2025032009000001", "M001", "",
            ],
        ])
        create_resp = client.post("/api/v1/imports", headers=auth_headers, files={
            "file": ("existing.csv", existing_csv, "text/csv"),
        })
        assert create_resp.status_code == 200

        preview_csv = _make_alipay_csv([
            [
                "2025-03-20 09:00:00", "餐饮美食", "美团外卖", "mt@example.com",
                "早餐", "支出", "20.00", "支付宝", "交易成功",
                "2025032009000001", "M001", "",
            ],
            [
                "2025-03-21 12:00:00", "", "星巴克", "sb@example.com",
                "拿铁", "支出", "32.00", "支付宝", "交易成功",
                "2025032112000001", "M002", "",
            ],
        ])
        preview_resp = client.post("/api/v1/imports/preview", headers=auth_headers, files={
            "file": ("preview.csv", preview_csv, "text/csv"),
        })
        assert preview_resp.status_code == 200
        preview = preview_resp.json()
        assert preview["total_rows"] == 2
        assert preview["duplicate_rows"] == 1
        assert preview["anomaly_rows"] == 1
        assert preview["duplicates"] == [True, False]

        confirm_resp = client.post("/api/v1/imports/confirm", headers=auth_headers, json={
            "filename": preview["filename"],
            "source": preview["source"],
            "transactions": [
                {**preview["items"][1], "category": "咖啡饮品"},
            ],
        })
        assert confirm_resp.status_code == 200
        data = confirm_resp.json()
        assert data["imported_rows"] == 1
        assert data["duplicate_rows"] == 0

    def test_preview_allows_zero_amount_file_rows(self, client, auth_headers):
        zero_csv = _make_alipay_csv([
            [
                "2025-03-22 08:00:00", "其他", "支付宝余额宝", "yb@example.com",
                "利息结转", "不计收支", "0.00", "支付宝", "交易成功",
                "2025032208000001", "M003", "",
            ],
        ])
        preview_resp = client.post("/api/v1/imports/preview", headers=auth_headers, files={
            "file": ("zero.csv", zero_csv, "text/csv"),
        })
        assert preview_resp.status_code == 200
        preview = preview_resp.json()
        assert preview["total_rows"] == 1
        assert preview["items"][0]["amount"] == 0.0
        assert preview["items"][0]["direction"] == "neutral"

    def test_preview_cmb_securities_file_import(self, client, auth_headers):
        cmb_bytes = _make_cmb_securities_xls([
            [
                "人民币", "天添利", "20260526", "1.0000", "0", "71.85",
                "72.85", "135195.08", "0", "2400962142", "产品红利发放",
                "0.00", "0.00", "0.00", "0.00", "0.00", "0.00", "0.00",
                "880013", "980413128609", "",
            ],
            [
                "人民币", "中国平安", "20260521", "54.5000", "500", "-27255.27",
                "1.00", "2700", "443753", "3200013111", "证券买入",
                "0.00", "3.52", "0.93", "0.55", "0.00", "0.27", "0.00",
                "601318", "A682083458", "",
            ],
        ])
        preview_resp = client.post("/api/v1/imports/cmb-securities/preview", headers=auth_headers, files={
            "file": ("zszq.xls", cmb_bytes, "application/vnd.ms-excel"),
        })
        assert preview_resp.status_code == 200
        preview = preview_resp.json()
        assert preview["source"] == "招商证券"
        assert preview["total_rows"] == 1
        assert preview["total_income"] == 71.85
        assert preview["items"][0]["transaction_time"] == "2026-05-26 00:00:00"
        assert preview["items"][0]["product"] == "天添利"
        assert preview["items"][0]["category"] == "股息收入"
        assert preview["items"][0]["source_order_id"] == "2400962142"

    def test_preview_ibkr_file_import(self, client, auth_headers, monkeypatch):
        from autocoin.parsers.ibkr import IbkrParser

        monkeypatch.setattr(IbkrParser, "_fetch_cny_rate", lambda self, currency: {
            "USD": 7.2,
            "HKD": 0.92,
        }[currency])

        ibkr_bytes = (
            "\ufeffStatement,Data,BrokerName,Interactive Brokers LLC\n"
            "股息,Header,货币,日期,描述,金额\n"
            "股息,Data,USD,2026-01-09,MO 现金红利,53\n"
            "股息,Data,总数,,,53\n"
            "代扣税,Header,货币,日期,描述,金额,代码\n"
            "代扣税,Data,USD,2026-01-09,MO US 税收,-15.9,\n"
            "利息,Header,货币,日期,描述,金额\n"
            "利息,Data,HKD,2026-05-05,HKD 贷方利息,29.58\n"
        ).encode("utf-8-sig")
        preview_resp = client.post("/api/v1/imports/ibkr/preview", headers=auth_headers, files={
            "file": ("ibkr.csv", ibkr_bytes, "text/csv"),
        })
        assert preview_resp.status_code == 200
        preview = preview_resp.json()
        assert preview["source"] == "盈透IBKR"
        assert preview["total_rows"] == 3
        assert preview["total_income"] == 408.81
        assert preview["total_expense"] == 114.48
        assert preview["items"][0]["transaction_time"] == "2026-01-09 00:00:00"
        assert preview["items"][0]["product"] == "MO 现金红利"
        assert preview["items"][0]["amount"] == 381.6
        assert preview["items"][0]["remark"] == "股息 USD 53"
        assert preview["items"][1]["direction"] == "expense"
        assert preview["items"][1]["remark"] == "代扣税 USD -15.9"

    def test_preview_moomoo_file_import(self, client, auth_headers, monkeypatch):
        from autocoin.parsers.moomoo import MoomooParser
        from tests.test_parsers import _make_moomoo_text

        monkeypatch.setattr(MoomooParser, "_fetch_cny_rate", lambda self, currency: {"USD": 7.2}[currency])
        monkeypatch.setattr(MoomooParser, "_extract_text", lambda self, file_bytes: _make_moomoo_text())

        preview_resp = client.post("/api/v1/imports/moomoo/preview", headers=auth_headers, files={
            "file": ("moomoo.pdf", b"%PDF-1.4", "application/pdf"),
        })
        assert preview_resp.status_code == 200
        preview = preview_resp.json()
        assert preview["source"] == "MOOMOO"
        assert preview["total_rows"] == 4
        assert preview["total_income"] == 4274.81
        assert preview["total_expense"] == 161.14
        assert preview["items"][0]["transaction_time"] == "2026-05-06 15:20:29"
        assert preview["items"][0]["product"].startswith("現金分紅 J P MORGAN")
        assert preview["items"][0]["amount"] == 1611.43
        assert preview["items"][0]["remark"] == "現金分紅 +223.81 USD"
        assert preview["items"][1]["direction"] == "expense"
        assert preview["items"][1]["remark"] == "非美國居民預扣稅 -22.38 USD"

    def test_preview_hsbc_pulse_file_import(self, client, auth_headers, monkeypatch):
        from autocoin.parsers.hsbc_pulse import HsbcPulseParser
        from tests.test_parsers import _make_hsbc_pulse_text

        monkeypatch.setattr(HsbcPulseParser, "_extract_text", lambda self, file_bytes: _make_hsbc_pulse_text())

        preview_resp = client.post("/api/v1/imports/hsbc-pulse/preview", headers=auth_headers, files={
            "file": ("pulse.pdf", b"%PDF-1.7", "application/pdf"),
        })
        assert preview_resp.status_code == 200
        preview = preview_resp.json()
        assert preview["source"] == "汇丰PULSE"
        assert preview["total_rows"] == 3
        assert preview["total_income"] == 406.85
        assert preview["total_expense"] == 9.8
        assert preview["items"][0]["transaction_time"] == "2026-04-24 00:00:00"
        assert preview["items"][0]["product"] == "MEITUAN CHN CN APPLE PAY-MOBILE:7045 退款"
        assert preview["items"][0]["direction"] == "income"
        assert preview["items"][0]["remark"] == "记账日期 2026-04-27 退款"
        assert preview["items"][1]["payment_method"] == "Pulse双币卡"


class TestImageImport:
    def test_check_duplicates_and_confirm_image_import(self, client, auth_headers):
        existing_resp = client.post("/api/v1/transactions", headers=auth_headers, json={
            "transaction_time": "2025-03-10 09:00:00",
            "direction": "expense",
            "amount": 20,
            "category": "餐饮美食",
            "counterparty": "美团外卖",
            "remark": "已有记录",
        })
        assert existing_resp.status_code == 201

        transactions = [
            {
                "transaction_time": "2025-03-10 09:00:00",
                "direction": "expense",
                "amount": 20,
                "category": "",
                "counterparty": "美团外卖",
                "product": "早餐",
                "payment_method": "微信",
                "remark": "",
            },
            {
                "transaction_time": "2025-03-11 12:00:00",
                "direction": "expense",
                "amount": 35,
                "category": "",
                "counterparty": "星巴克",
                "product": "拿铁",
                "payment_method": "支付宝",
                "remark": "",
            },
        ]

        dup_resp = client.post("/api/v1/imports/image/check-duplicates", headers=auth_headers, json={
            "transactions": transactions,
        })
        assert dup_resp.status_code == 200
        assert dup_resp.json()["duplicates"] == [True, False]

        confirm_resp = client.post("/api/v1/imports/image/confirm", headers=auth_headers, json={
            "transactions": transactions,
            "filenames": ["receipt-1.jpg", "receipt-2.jpg"],
        })
        assert confirm_resp.status_code == 200
        data = confirm_resp.json()
        assert data["imported_rows"] == 1
        assert data["duplicate_rows"] == 1


class TestDataManagementBackup:
    def test_backup_validate_and_restore(self, client, auth_headers):
        create_resp = client.post("/api/v1/transactions", headers=auth_headers, json={
            "transaction_time": "2026-06-01 08:00:00",
            "direction": "expense",
            "amount": 88.8,
            "category": "备份测试",
            "counterparty": "原始记录",
        })
        assert create_resp.status_code == 201

        export_resp = client.get("/api/v1/data-management/backup/export", headers=auth_headers)
        assert export_resp.status_code == 200
        assert "text/csv" in export_resp.headers["content-type"]
        backup_bytes = export_resp.content
        assert b"autocoin_full_database_backup" in backup_bytes
        assert b"transactions" in backup_bytes
        assert b"users" in backup_bytes

        validate_resp = client.post(
            "/api/v1/data-management/backup/validate",
            headers=auth_headers,
            files={"file": ("backup.csv", backup_bytes, "text/csv")},
        )
        assert validate_resp.status_code == 200
        assert validate_resp.json()["valid"] is True
        assert validate_resp.json()["tables"]["transactions"] >= 1

        extra_resp = client.post("/api/v1/transactions", headers=auth_headers, json={
            "transaction_time": "2026-06-02 08:00:00",
            "direction": "expense",
            "amount": 99.9,
            "category": "备份测试",
            "counterparty": "还原前新增",
        })
        assert extra_resp.status_code == 201

        restore_resp = client.post(
            "/api/v1/data-management/backup/restore",
            headers=auth_headers,
            files={"file": ("backup.csv", backup_bytes, "text/csv")},
        )
        assert restore_resp.status_code == 200
        assert restore_resp.json()["message"] == "数据还原成功"

        list_resp = client.get(
            "/api/v1/transactions?search=%E8%BF%98%E5%8E%9F%E5%89%8D%E6%96%B0%E5%A2%9E",
            headers=auth_headers,
        )
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] == 0

    def test_validate_rejects_invalid_backup(self, client, auth_headers):
        resp = client.post(
            "/api/v1/data-management/backup/validate",
            headers=auth_headers,
            files={"file": ("bad.csv", b"not,a,backup\n1,2,3\n", "text/csv")},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "数据错误，请检查上传的备份数据。"
