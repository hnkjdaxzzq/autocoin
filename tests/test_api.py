"""Integration tests for the API using FastAPI TestClient.

Note: tests/conftest.py sets AUTOCOIN_DATABASE_URL and AUTOCOIN_JWT_SECRET
to a temp directory BEFORE any autocoin modules are imported.
"""
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

import autocoin.routers.ai_classification as ai_classification_router
from autocoin.routers.ai_classification import (
    DEFAULT_CATEGORIES,
    DEFAULT_PROMPT_TEMPLATE,
    AIClassificationBatchError,
    _filter_classifiable_transactions,
    _classify_batch_with_split,
    _normalize_ai_result_item,
    _parse_categories,
    _request_debug_preview,
    _response_debug_preview,
    _response_finished_by_length,
    _render_prompt_template,
    _summarize_error,
)
from autocoin.app import create_app, _seconds_until_next_sunday_3am
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


class TestAppSchedule:
    def test_stock_cache_cleanup_runs_next_sunday_at_3am(self):
        saturday_noon = datetime(2026, 7, 4, 12, 0, 0)
        assert _seconds_until_next_sunday_3am(saturday_noon) == 15 * 60 * 60

        sunday_before_run = datetime(2026, 7, 5, 2, 30, 0)
        assert _seconds_until_next_sunday_3am(sunday_before_run) == 30 * 60

        sunday_after_run = datetime(2026, 7, 5, 3, 0, 0)
        assert _seconds_until_next_sunday_3am(sunday_after_run) == 7 * 24 * 60 * 60


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
        assert data["categories"] == DEFAULT_CATEGORIES
        assert data["api_key"] == ""
        assert data["prompt_template"] == DEFAULT_PROMPT_TEMPLATE
        assert data["only_expense"] is True
        assert data["default_prompt_template"] == DEFAULT_PROMPT_TEMPLATE

    def test_update_preferences_is_user_scoped(self, client):
        headers = self._register_headers(client, "aiprefsowner")
        other_headers = self._register_headers(client, "aiprefsother")
        payload = {
            "categories": "餐饮,交通",
            "api_key": "sk-owner",
            "prompt_template": "分类: {categories}\n交易: {transactions}",
            "only_expense": False,
        }

        resp = client.put(
            "/api/v1/ai-classification/preferences",
            headers=headers,
            json=payload,
        )
        assert resp.status_code == 200
        data = resp.json()
        for key, value in payload.items():
            if key == "only_expense":
                continue
            assert data[key] == value
        assert data["only_expense"] is True
        assert data["default_prompt_template"] == DEFAULT_PROMPT_TEMPLATE

        owner_resp = client.get("/api/v1/ai-classification/preferences", headers=headers)
        other_resp = client.get("/api/v1/ai-classification/preferences", headers=other_headers)

        owner_data = owner_resp.json()
        for key, value in payload.items():
            if key == "only_expense":
                continue
            assert owner_data[key] == value
        assert owner_data["only_expense"] is True
        assert owner_data["default_prompt_template"] == DEFAULT_PROMPT_TEMPLATE
        assert other_resp.json()["categories"] == DEFAULT_CATEGORIES
        assert other_resp.json()["api_key"] == ""
        assert other_resp.json()["prompt_template"] == DEFAULT_PROMPT_TEMPLATE
        assert other_resp.json()["only_expense"] is True
        assert other_resp.json()["default_prompt_template"] == DEFAULT_PROMPT_TEMPLATE

    def test_classify_accepts_prompt_template_and_saves_preferences(self, client):
        headers = self._register_headers(client, "aiprefsclassify")
        payload = {
            "categories": "餐饮,交通",
            "api_key": "sk-classify",
            "prompt_template": "只返回 JSON。分类: {categories}\n交易:\n{transactions}",
            "only_expense": False,
            "only_unclassified": False,
            "limit": 5,
            "debug": True,
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
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
        prefs_data = prefs_resp.json()
        for key, value in payload.items():
            if key in ("only_expense", "only_unclassified", "limit", "debug", "start_date", "end_date"):
                continue
            assert prefs_data[key] == value
        assert prefs_data["only_expense"] is True
        assert prefs_data["default_prompt_template"] == DEFAULT_PROMPT_TEMPLATE
        assert "only_unclassified" not in prefs_data
        assert "limit" not in prefs_data
        assert "debug" not in prefs_data
        assert "start_date" not in prefs_data
        assert "end_date" not in prefs_data

    def test_render_prompt_template_replaces_variables(self):
        prompt = _render_prompt_template(
            "分类编号:\n{category_map}\n分类={categories}\n数据={transactions}",
            [{
                "id": 7,
                "category": "旧分类",
                "counterparty": "商户",
                "product": "商品|换行\n清理",
                "remark": "备注",
            }],
            ["餐饮", "交通"],
        )

        assert "1=餐饮" in prompt
        assert "2=交通" in prompt
        assert "分类=餐饮, 交通" in prompt
        assert "7|旧分类|商户|商品 换行 清理" in prompt
        assert "备注" not in prompt
        assert "remark" not in prompt
        assert "{categories}" not in prompt
        assert "{category_map}" not in prompt
        assert "{transactions}" not in prompt

    def test_filter_classifiable_transactions_defaults_to_expense_only(self):
        transactions = [
            {"id": 1, "direction": "expense", "is_ai_classified": 0},
            {"id": 2, "direction": "income", "is_ai_classified": 0},
            {"id": 3, "direction": "neutral", "is_ai_classified": 0},
            {"id": 4, "direction": "不计", "is_ai_classified": 0},
            {"id": 5, "direction": "不计收支", "is_ai_classified": 0},
            {"id": 6, "direction": "expense", "is_ai_classified": 1},
        ]

        filtered = _filter_classifiable_transactions(transactions)

        assert [tx["id"] for tx in filtered] == [1]

    def test_filter_classifiable_transactions_can_include_non_neutral(self):
        transactions = [
            {"id": 1, "direction": "expense", "is_ai_classified": 0},
            {"id": 2, "direction": "income", "is_ai_classified": 0},
            {"id": 3, "direction": "neutral", "is_ai_classified": 0},
            {"id": 4, "direction": "不计", "is_ai_classified": 0},
            {"id": 5, "direction": "不计收支", "is_ai_classified": 0},
            {"id": 6, "direction": "income", "is_ai_classified": 1},
        ]

        filtered = _filter_classifiable_transactions(transactions, only_expense=False)

        assert [tx["id"] for tx in filtered] == [1, 2]

    def test_filter_classifiable_transactions_can_include_ai_classified(self):
        transactions = [
            {"id": 1, "direction": "expense", "is_ai_classified": 0},
            {"id": 2, "direction": "expense", "is_ai_classified": 1},
        ]

        filtered = _filter_classifiable_transactions(transactions, only_unclassified=False)

        assert [tx["id"] for tx in filtered] == [1, 2]

    def test_normalize_ai_result_item_accepts_compact_category_id(self):
        category_map = {1: "餐饮", 2: "交通"}

        assert _normalize_ai_result_item([7, 2], category_map) == (7, "交通")
        assert _normalize_ai_result_item([8, "1"], category_map) == (8, "餐饮")
        assert _normalize_ai_result_item({"id": 8, "category_id": "1"}, category_map) == (None, "")
        assert _normalize_ai_result_item({"id": 9, "category": "餐饮"}, category_map) == (None, "")
        assert _normalize_ai_result_item([10, "购物"], category_map) == (None, "")
        assert _normalize_ai_result_item([11, "PULSE交易"], category_map) == (None, "")

    def test_parse_categories_supports_chinese_and_english_commas(self):
        categories = _parse_categories("餐饮美食，交通出行, 汽车，母婴儿童")

        assert categories == ["餐饮美食", "交通出行", "汽车", "母婴儿童"]

    def test_summarize_error_keeps_details_and_truncates(self):
        summary = _summarize_error(RuntimeError("bad key sk-secret-value " + ("x" * 300)))

        assert "sk-secret-value" in summary
        assert len(summary) <= 1000

    def test_response_debug_preview_includes_finish_reason_and_usage(self):
        class Message:
            role = "assistant"
            content = ""

            def model_dump(self, exclude_none=True):
                return {"role": self.role, "content": self.content}

        class Choice:
            index = 0
            finish_reason = "stop"
            message = Message()

        class Usage:
            def model_dump(self, exclude_none=True):
                return {"prompt_tokens": 12, "completion_tokens": 0}

        class Response:
            id = "resp-1"
            model = "deepseek-v4-flash"
            created = 123
            object = "chat.completion"
            choices = [Choice()]
            usage = Usage()

        preview = _response_debug_preview(Response())

        assert '"finish_reason": "stop"' in preview
        assert '"content_length": 0' in preview
        assert '"prompt_tokens": 12' in preview

    def test_response_finished_by_length_detects_length_reason(self):
        class Choice:
            finish_reason = "length"

        class Response:
            choices = [Choice()]

        assert _response_finished_by_length(Response()) is True

    def test_request_debug_preview_includes_batch_request_data(self):
        preview = _request_debug_preview(
            "请分类\n1|餐饮|商户|商品",
            [{
                "id": 1,
                "category": "餐饮",
                "counterparty": "商户|A",
                "product": "商品\nB",
            }],
            ["餐饮", "交通"],
        )

        assert '"model": "deepseek-v4-flash"' in preview
        assert '"max_tokens": 8192' in preview
        assert '"batch_transaction_count": 1' in preview
        assert '"batch_transaction_ids": [' in preview
        assert "1|餐饮|商户 A|商品 B" in preview
        assert "api_key" not in preview

    def test_classify_batch_with_split_retries_splittable_error(self, monkeypatch):
        calls = []

        def fake_classify_batch(api_key, transactions, categories, prompt_template, debug=False):
            calls.append([tx["id"] for tx in transactions])
            if len(transactions) > 2:
                raise AIClassificationBatchError("truncated", splittable=True)
            return [
                {
                    "id": tx["id"],
                    "old_category": tx.get("category") or "",
                    "new_category": "餐饮",
                    "counterparty": tx.get("counterparty") or "",
                    "product": tx.get("product") or "",
                    "transaction_time": tx.get("transaction_time") or "",
                }
                for tx in transactions
            ]

        monkeypatch.setattr(ai_classification_router, "_classify_batch", fake_classify_batch)
        transactions = [{"id": idx, "category": ""} for idx in range(1, 5)]

        results = _classify_batch_with_split(
            "sk-test",
            transactions,
            ["餐饮"],
            "{transactions}",
            debug=True,
        )

        assert calls == [[1, 2, 3, 4], [1, 2], [3, 4]]
        assert [item["id"] for item in results] == [1, 2, 3, 4]

    def test_confirm_marks_all_submitted_transactions_as_ai_classified(self, client):
        headers = self._register_headers(client, "aiconfirmmarks")
        create_resp = client.post("/api/v1/transactions", headers=headers, json={
            "transaction_time": "2026-06-01 12:00:00",
            "direction": "expense",
            "amount": 12.5,
            "category": "餐饮",
            "counterparty": "商户",
        })
        assert create_resp.status_code == 201
        tid = create_resp.json()["id"]

        resp = client.post(
            "/api/v1/ai-classification/confirm",
            headers=headers,
            json={"results": [{"id": tid, "category": "餐饮"}]},
        )

        assert resp.status_code == 200
        assert resp.json()["updated"] == 1
        tx_resp = client.get(f"/api/v1/transactions/{tid}", headers=headers)
        assert tx_resp.status_code == 200
        assert tx_resp.json()["category"] == "餐饮"
        assert tx_resp.json()["is_ai_classified"] == 1


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

    def test_reclassify_does_not_duplicate_original_category_remark(self, client, auth_headers):
        rule_resp = client.post("/api/v1/rules", headers=auth_headers, json={
            "name": "便利店归类日用",
            "priority": 40,
            "is_active": True,
            "match_counterparty": "便利店",
            "match_product": "",
            "match_payment_method": "",
            "match_transaction_type": "",
            "category": "日用百货",
            "remark": "",
        })
        assert rule_resp.status_code == 201

        tx_resp = client.post("/api/v1/transactions", headers=auth_headers, json={
            "transaction_time": "2025-03-03 09:00:00",
            "direction": "expense",
            "amount": 12.0,
            "category": "餐饮美食",
            "counterparty": "便利店",
            "product": "矿泉水",
            "payment_method": "支付宝",
            "remark": "手动备注；原数据分类为：餐饮美食",
        })
        assert tx_resp.status_code == 201
        tx = tx_resp.json()

        reclassify_resp = client.post("/api/v1/rules/reclassify", headers=auth_headers)
        assert reclassify_resp.status_code == 200

        updated = client.get(f"/api/v1/transactions/{tx['id']}", headers=auth_headers).json()
        assert updated["category"] == "日用百货"
        assert updated["remark"] == "手动备注；原数据分类为：餐饮美食"
        assert updated["remark"].count("原数据分类为：") == 1

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
        assert preview["total_rows"] == 3
        assert preview["total_income"] == 4262.47
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


class TestStockManagement:
    def _register_headers(self, client, username):
        resp = client.post("/api/v1/auth/register", json={
            "username": username,
            "password": "password123",
            "invite_code": "tarikz",
        })
        assert resp.status_code == 201
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    def test_create_allows_lookup_failure(self, client, monkeypatch):
        from autocoin.services.stock_market_service import StockLookupError, StockMarketService

        def fail_lookup(self, market, stock_id):
            raise StockLookupError("行情不可用")

        monkeypatch.setattr(StockMarketService, "_fetch_remote", fail_lookup)
        headers = self._register_headers(client, "stockfailure")

        resp = client.post("/api/v1/stock-management/stocks", headers=headers, json={
            "stock_market": "CN",
            "stock_id": "600000",
            "stock_amount": 10,
            "stock_average_price": 7.5,
            "stock_alias": "浦发",
        })

        assert resp.status_code == 201
        data = resp.json()
        assert data["lookup_error"] == "行情不可用"
        assert len(data["item"]["stock_vid"]) == 16
        assert data["item"]["stock_currency"] == "CNY"

    def test_summary_alias_sync_and_records_pagination(self, client, monkeypatch):
        from autocoin.services.stock_market_service import StockMarketService

        def fake_lookup(self, market, stock_id):
            return {"stock_name": "测试股票", "current_price": 20.0}

        monkeypatch.setattr(StockMarketService, "_fetch_remote", fake_lookup)
        headers = self._register_headers(client, "stockowner")

        for idx in range(6):
            resp = client.post("/api/v1/stock-management/stocks", headers=headers, json={
                "stock_market": "CN",
                "stock_id": "600519",
                "stock_amount": 10 if idx == 0 else 1,
                "stock_average_price": 5 if idx == 0 else (None if idx == 1 else 8),
                "stock_alias": "贵州茅台" if idx < 5 else "茅台",
                "stock_remark": f"批次{idx}",
                "stock_transaction_date": "2026-07-01" if idx == 0 else None,
            })
            assert resp.status_code == 201
            if idx == 1:
                data = resp.json()["item"]
                assert data["stock_average_price"] == 20.0
                assert data["stock_entry_time"]
            if idx == 0:
                assert resp.json()["item"]["stock_transaction_date"] == "2026-07-01"

        summary_resp = client.get("/api/v1/stock-management/stocks/summary", headers=headers)
        assert summary_resp.status_code == 200
        items = summary_resp.json()["items"]
        assert len(items) == 1
        item = items[0]
        assert item["stock_alias"] == "茅台"
        assert item["stock_amount"] == 15
        assert item["total_value"] == 300
        assert item["total_cost"] == 102
        assert item["current_return_rate"] == 194.1
        assert item["current_price"] == 20.0
        assert item["stock_average_price"] == 6.8

        records_resp = client.get("/api/v1/stock-management/stocks/CN/600519/records?page=1", headers=headers)
        assert records_resp.status_code == 200
        records = records_resp.json()
        assert records["total"] == 6
        assert records["page_size"] == 5
        assert records["total_pages"] == 2
        assert len(records["items"]) == 5
        assert {record["stock_alias"] for record in records["items"]} == {"茅台"}

    def test_lookup_uses_existing_schema_without_id_column(self, client, monkeypatch):
        from autocoin.services.stock_market_service import StockMarketService

        def fake_lookup(self, market, stock_id):
            return {"stock_name": "Apple Inc.", "current_price": 200.0}

        monkeypatch.setattr(StockMarketService, "_fetch_remote", fake_lookup)
        headers = self._register_headers(client, "stocklookup")

        resp = client.get("/api/v1/stock-management/lookup?stock_market=US&stock_id=AAPL", headers=headers)

        assert resp.status_code == 200
        assert resp.json()["stock_name"] == "Apple Inc."

    def test_cn_stock_details_returns_summary_records_and_sections(self, client, monkeypatch):
        from autocoin.services.stock_market_service import StockMarketService

        def fake_lookup(self, market, stock_id):
            return {
                "stock_name": "中国移动",
                "current_price": 100.0,
                "raw_api_source": "test",
                "raw_api_data": {"代码": stock_id},
            }

        def fake_sections(self, market, stock_id, force_refresh=False):
            assert market == "CN"
            assert stock_id == "600941"
            return [
                {
                    "title": "巨潮资讯历史分红",
                    "source": "akshare.stock_dividend_cninfo",
                    "status": "ok",
                    "columns": ["派息比例", "派息日"],
                    "rows": [{"派息比例": 22.012, "派息日": "2026-06-05"}],
                    "error": None,
                },
                {
                    "title": "新浪财经分红历史",
                    "source": "akshare.stock_history_dividend_detail",
                    "status": "ok",
                    "columns": ["派息", "除权除息日"],
                    "rows": [{"派息": 22.012, "除权除息日": "2026-06-05"}],
                    "error": None,
                },
                {
                    "title": "东方财富分红送配详情",
                    "source": "akshare.stock_fhps_detail_em",
                    "status": "ok",
                    "columns": ["现金分红-现金分红比例"],
                    "rows": [{"现金分红-现金分红比例": 22.012}],
                    "error": None,
                },
                {
                    "title": "同花顺分红情况",
                    "source": "akshare.stock_fhps_detail_ths",
                    "status": "ok",
                    "columns": ["分红方案说明"],
                    "rows": [{"分红方案说明": "10派22.012元(含税)"}],
                    "error": None,
                },
            ]

        monkeypatch.setattr(StockMarketService, "_fetch_remote", fake_lookup)
        monkeypatch.setattr(StockMarketService, "external_sections", fake_sections)
        headers = self._register_headers(client, "stockdetailscn")

        create_resp = client.post("/api/v1/stock-management/stocks", headers=headers, json={
            "stock_market": "CN",
            "stock_id": "600941",
            "stock_amount": 2,
            "stock_average_price": 80,
            "stock_alias": "移动",
        })
        assert create_resp.status_code == 201

        resp = client.get("/api/v1/stock-management/stocks/CN/600941/details", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["stock_name"] == "中国移动"
        assert data["summary"]["total_value"] == 200
        assert data["summary"]["total_cost"] == 160
        assert data["lookup"]["raw_api_data"]["代码"] == "600941"
        assert len(data["records"]) == 1
        assert len(data["external_sections"]) == 4
        assert data["external_sections"][0]["rows"][0]["派息日"] == "2026-06-05"

    def test_us_stock_details_keeps_failed_external_section(self, client, monkeypatch):
        from autocoin.services.stock_market_service import StockMarketService

        def fake_lookup(self, market, stock_id):
            return {"stock_name": "JEPI", "current_price": 55.0}

        def fake_sections(self, market, stock_id, force_refresh=False):
            assert market == "US"
            assert stock_id == "JEPI"
            return [
                {
                    "title": "Yahoo Finance 基础信息",
                    "source": "yfinance.Ticker.get_info",
                    "status": "ok",
                    "columns": ["field", "value"],
                    "rows": [{"field": "yield", "value": 0.0845}],
                    "error": None,
                },
                {
                    "title": "Yahoo Finance 历史股息",
                    "source": "yfinance.Ticker.get_dividends",
                    "status": "ok",
                    "columns": ["date", "dividend"],
                    "rows": [{"date": "2026-06-01", "dividend": 0.389}],
                    "error": None,
                },
                {
                    "title": "Yahoo Finance 公司行为",
                    "source": "yfinance.Ticker.actions",
                    "status": "ok",
                    "columns": ["Dividends", "Stock Splits", "Capital Gains"],
                    "rows": [{"Dividends": 0.389, "Stock Splits": 0, "Capital Gains": 0}],
                    "error": None,
                },
                {
                    "title": "Yahoo Finance 非零分红/拆股历史",
                    "source": "yfinance.Ticker.history(actions=True)",
                    "status": "error",
                    "columns": [],
                    "rows": [],
                    "error": "Yahoo timeout",
                },
            ]

        monkeypatch.setattr(StockMarketService, "_fetch_remote", fake_lookup)
        monkeypatch.setattr(StockMarketService, "external_sections", fake_sections)
        headers = self._register_headers(client, "stockdetailsus")

        create_resp = client.post("/api/v1/stock-management/stocks", headers=headers, json={
            "stock_market": "US",
            "stock_id": "JEPI",
            "stock_amount": 3,
            "stock_average_price": 50,
        })
        assert create_resp.status_code == 201

        resp = client.get("/api/v1/stock-management/stocks/US/JEPI/details", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["stock_currency"] == "USD"
        assert data["external_sections"][1]["rows"][0]["dividend"] == 0.389
        assert data["external_sections"][3]["status"] == "error"
        assert data["external_sections"][3]["error"] == "Yahoo timeout"

    def test_stock_details_requires_auth_and_valid_market(self, client, monkeypatch):
        from autocoin.services.stock_market_service import StockMarketService

        def fake_lookup(self, market, stock_id):
            return {"stock_name": "测试股票", "current_price": 20.0}

        monkeypatch.setattr(StockMarketService, "_fetch_remote", fake_lookup)
        monkeypatch.setattr(StockMarketService, "external_sections", lambda self, market, stock_id: [])
        headers = self._register_headers(client, "stockdetailsauth")

        create_resp = client.post("/api/v1/stock-management/stocks", headers=headers, json={
            "stock_market": "CN",
            "stock_id": "600519",
            "stock_amount": 1,
            "stock_average_price": 10,
        })
        assert create_resp.status_code == 201

        unauth_resp = client.get("/api/v1/stock-management/stocks/CN/600519/details")
        assert unauth_resp.status_code == 401

        invalid_resp = client.get("/api/v1/stock-management/stocks/HK/600519/details", headers=headers)
        assert invalid_resp.status_code == 422

    def test_cn_lookup_falls_back_when_akshare_fails(self, client, monkeypatch):
        from autocoin.services.stock_market_service import StockMarketService

        def fail_akshare(self, stock_id):
            raise RuntimeError("AKShare remote closed")

        def fake_tencent(self, stock_id):
            return {
                "stock_name": "中国海油",
                "current_price": 27.5,
                "raw_api_source": "tencent.qt.gtimg",
                "raw_api_data": {
                    "symbol": "sh600938",
                    "field_count": 4,
                    "fields": ["1", "中国海油", "600938", "27.5"],
                },
            }

        monkeypatch.setattr(StockMarketService, "_fetch_cn_akshare", fail_akshare)
        monkeypatch.setattr(StockMarketService, "_fetch_cn_tencent", fake_tencent)
        headers = self._register_headers(client, "stockcnfallback")

        resp = client.get("/api/v1/stock-management/lookup?stock_market=CN&stock_id=600938", headers=headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["stock_name"] == "中国海油"
        assert data["current_price"] == 27.5
        assert data["raw_api_source"] == "tencent.qt.gtimg"
        assert data["raw_api_data"]["fields"][1] == "中国海油"

        cached_resp = client.get("/api/v1/stock-management/lookup?stock_market=CN&stock_id=600938", headers=headers)
        assert cached_resp.status_code == 200
        cached = cached_resp.json()
        assert cached["from_cache"] is True
        assert cached["raw_api_data"]["fields"][3] == "27.5"

    def test_stock_lookup_uses_unified_query_cache(self, client, monkeypatch):
        from autocoin.services.stock_market_service import StockMarketService

        calls = {"count": 0}

        def fake_lookup(self, market, stock_id):
            calls["count"] += 1
            return {
                "stock_name": "缓存股票",
                "current_price": 12.3,
                "raw_api_source": "test.lookup",
                "raw_api_data": {"call": calls["count"]},
            }

        monkeypatch.setattr(StockMarketService, "_fetch_remote", fake_lookup)
        headers = self._register_headers(client, "stockquerycache")

        first = client.get("/api/v1/stock-management/lookup?stock_market=CN&stock_id=600001", headers=headers)
        second = client.get("/api/v1/stock-management/lookup?stock_market=CN&stock_id=600001", headers=headers)

        assert first.status_code == 200
        assert second.status_code == 200
        assert calls["count"] == 1
        assert first.json()["from_cache"] is False
        assert second.json()["from_cache"] is True
        assert second.json()["raw_api_data"]["call"] == 1

    def test_stock_summary_does_not_refresh_prices_by_default(self, client, monkeypatch):
        from autocoin.services.stock_market_service import StockLookupError, StockMarketService

        calls = {"count": 0}

        def fail_lookup(self, market, stock_id):
            calls["count"] += 1
            raise StockLookupError("行情不可用")

        monkeypatch.setattr(StockMarketService, "_fetch_remote", fail_lookup)
        headers = self._register_headers(client, "stocksummarylazy")

        create_resp = client.post("/api/v1/stock-management/stocks", headers=headers, json={
            "stock_market": "CN",
            "stock_id": "600002",
            "stock_amount": 2,
            "stock_average_price": 10,
        })
        assert create_resp.status_code == 201
        assert calls["count"] == 1

        summary_resp = client.get("/api/v1/stock-management/stocks/summary", headers=headers)
        assert summary_resp.status_code == 200
        item = summary_resp.json()["items"][0]
        assert calls["count"] == 1
        assert item["current_price"] is None
        assert item["total_value"] is None
        assert item["current_return_rate"] is None
        assert item["lookup_error"] is None

        refresh_resp = client.get("/api/v1/stock-management/stocks/summary?refresh_prices=true", headers=headers)
        assert refresh_resp.status_code == 200
        assert calls["count"] == 2
        assert refresh_resp.json()["items"][0]["lookup_error"] == "行情不可用"

    def test_stock_summary_uses_stale_cache_before_async_refresh(self, client, monkeypatch):
        from datetime import datetime, timedelta

        from autocoin.database import SessionLocal
        from autocoin.models.stock_query_cache import StockQueryCache
        from autocoin.services.stock_market_service import STOCK_CACHE_TTL, StockLookupError, StockMarketService

        calls = {"count": 0}

        def fake_lookup(self, market, stock_id):
            calls["count"] += 1
            if calls["count"] > 1:
                raise StockLookupError("行情刷新失败")
            return {
                "stock_name": "过期缓存股",
                "current_price": 12.0,
                "raw_api_source": "test.lookup",
                "raw_api_data": {"call": calls["count"]},
            }

        monkeypatch.setattr(StockMarketService, "_fetch_remote", fake_lookup)
        headers = self._register_headers(client, "stockstaleprice")

        create_resp = client.post("/api/v1/stock-management/stocks", headers=headers, json={
            "stock_market": "CN",
            "stock_id": "600003",
            "stock_amount": 2,
            "stock_average_price": 10,
        })
        assert create_resp.status_code == 201
        assert calls["count"] == 1

        db = SessionLocal()
        try:
            cache = (
                db.query(StockQueryCache)
                .filter(
                    StockQueryCache.stock_market == "CN",
                    StockQueryCache.stock_id == "600003",
                    StockQueryCache.query_key == "lookup",
                )
                .first()
            )
            assert cache is not None
            cache.queried_at = datetime.utcnow() - STOCK_CACHE_TTL - timedelta(seconds=1)
            db.commit()
        finally:
            db.close()

        summary_resp = client.get("/api/v1/stock-management/stocks/summary", headers=headers)
        assert summary_resp.status_code == 200
        item = summary_resp.json()["items"][0]
        assert calls["count"] == 1
        assert item["current_price"] == 12.0
        assert item["total_value"] == 24.0
        assert item["price_from_cache"] is True
        assert item["price_cache_stale"] is True
        assert item["price_refresh_needed"] is True

        refresh_resp = client.get("/api/v1/stock-management/stocks/summary?refresh_prices=true", headers=headers)
        assert refresh_resp.status_code == 200
        assert calls["count"] == 2
        assert refresh_resp.json()["items"][0]["lookup_error"] == "行情刷新失败"

    def test_stock_external_sections_use_unified_query_cache(self, client, monkeypatch):
        from autocoin.services.stock_market_service import StockMarketService

        calls = {"count": 0}

        def fake_lookup(self, market, stock_id):
            return {"stock_name": "JEPI", "current_price": 55.0}

        def fake_us_sections(self, stock_id, force_refresh=False):
            return [
                self._section_from_call(
                    "Yahoo Finance 基础信息",
                    "yfinance.Ticker.get_info",
                    stock_id,
                    make_section,
                    force_refresh=force_refresh,
                )
            ]

        def make_section():
            calls["count"] += 1
            return [{"field": "yield", "value": calls["count"]}]

        monkeypatch.setattr(StockMarketService, "_fetch_remote", fake_lookup)
        monkeypatch.setattr(StockMarketService, "_us_external_sections", fake_us_sections)
        headers = self._register_headers(client, "stocksectioncache")

        create_resp = client.post("/api/v1/stock-management/stocks", headers=headers, json={
            "stock_market": "US",
            "stock_id": "JEPI",
            "stock_amount": 1,
            "stock_average_price": 50,
        })
        assert create_resp.status_code == 201

        first = client.get("/api/v1/stock-management/stocks/US/JEPI/details", headers=headers)
        second = client.get("/api/v1/stock-management/stocks/US/JEPI/details", headers=headers)
        refreshed = client.get("/api/v1/stock-management/stocks/US/JEPI/details?force_refresh=true", headers=headers)

        assert first.status_code == 200
        assert second.status_code == 200
        assert refreshed.status_code == 200
        assert calls["count"] == 2
        assert first.json()["external_sections"][0]["from_cache"] is False
        assert second.json()["external_sections"][0]["from_cache"] is True
        assert second.json()["external_sections"][0]["rows"][0]["value"] == 1
        assert refreshed.json()["external_sections"][0]["from_cache"] is False
        assert refreshed.json()["external_sections"][0]["rows"][0]["value"] == 2
        assert refreshed.json()["updated_at"]

    def test_cleanup_expired_stock_api_cache(self, client):
        from datetime import datetime, timedelta

        from autocoin.database import SessionLocal
        from autocoin.models.stock_api_cache import StockApiCache
        from autocoin.models.stock_query_cache import StockQueryCache
        from autocoin.services.stock_market_service import STOCK_CACHE_TTL, StockMarketService

        now = datetime.utcnow()
        db = SessionLocal()
        try:
            expired = StockApiCache(
                stock_market="US",
                stock_id="EXPIRED",
                stock_name="Expired",
                current_price=1.0,
                stock_currency="USD",
                queried_at=now - STOCK_CACHE_TTL - timedelta(seconds=1),
                created_at=now,
                updated_at=now,
            )
            fresh = StockApiCache(
                stock_market="US",
                stock_id="FRESH",
                stock_name="Fresh",
                current_price=2.0,
                stock_currency="USD",
                queried_at=now - STOCK_CACHE_TTL + timedelta(seconds=1),
                created_at=now,
                updated_at=now,
            )
            expired_query = StockQueryCache(
                stock_market="US",
                stock_id="EXPIRED",
                query_key="external:test",
                payload="{}",
                queried_at=now - STOCK_CACHE_TTL - timedelta(seconds=1),
                created_at=now,
                updated_at=now,
            )
            fresh_query = StockQueryCache(
                stock_market="US",
                stock_id="FRESH",
                query_key="external:test",
                payload="{}",
                queried_at=now - STOCK_CACHE_TTL + timedelta(seconds=1),
                created_at=now,
                updated_at=now,
            )
            db.add_all([expired, fresh, expired_query, fresh_query])
            db.commit()

            deleted = StockMarketService(db).cleanup_expired_cache(now=now)
            db.commit()

            assert deleted >= 2
            assert db.query(StockApiCache).filter(StockApiCache.stock_id == "EXPIRED").first() is None
            assert db.query(StockApiCache).filter(StockApiCache.stock_id == "FRESH").first() is not None
            assert db.query(StockQueryCache).filter(StockQueryCache.stock_id == "EXPIRED").first() is None
            assert db.query(StockQueryCache).filter(StockQueryCache.stock_id == "FRESH").first() is not None
        finally:
            db.close()
