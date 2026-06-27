"""Integration tests for the API using FastAPI TestClient.

Note: tests/conftest.py sets AUTOCOIN_DATABASE_URL and AUTOCOIN_JWT_SECRET
to a temp directory BEFORE any autocoin modules are imported.
"""
import pytest
from fastapi.testclient import TestClient

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
