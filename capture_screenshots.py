"""Automated screenshot capture for README documentation.

Creates a demo user with realistic mock data, captures screenshots of all pages,
then cleans up the demo user.
"""
import os
import sys
import json
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path

BASE_URL = "http://localhost:8000"
API = f"{BASE_URL}/api/v1"
IMG_DIR = Path(__file__).parent / "docs" / "images"
IMG_DIR.mkdir(parents=True, exist_ok=True)

DEMO_USER = "demo_screenshot_user"
DEMO_PASS = "DemoPass123"

# Realistic demo transactions
DEMO_TXS = [
    {"transaction_time": "2026-02-25 12:30:00", "direction": "expense", "amount": 35.00, "category": "餐饮美食", "counterparty": "美团外卖", "product": "午餐套餐", "payment_method": "微信支付"},
    {"transaction_time": "2026-02-25 08:15:00", "direction": "expense", "amount": 6.00, "category": "餐饮美食", "counterparty": "瑞幸咖啡", "product": "生椰拿铁", "payment_method": "支付宝"},
    {"transaction_time": "2026-02-24 19:00:00", "direction": "expense", "amount": 128.00, "category": "餐饮美食", "counterparty": "海底捞火锅", "product": "晚餐", "payment_method": "支付宝"},
    {"transaction_time": "2026-02-24 14:20:00", "direction": "expense", "amount": 15.80, "category": "交通出行", "counterparty": "滴滴出行", "product": "快车", "payment_method": "微信支付"},
    {"transaction_time": "2026-02-23 10:00:00", "direction": "income", "amount": 15000.00, "category": "工资收入", "counterparty": "某科技有限公司", "product": "2月工资"},
    {"transaction_time": "2026-02-23 16:30:00", "direction": "expense", "amount": 299.00, "category": "生活日用", "counterparty": "京东", "product": "家居用品", "payment_method": "京东支付"},
    {"transaction_time": "2026-02-22 20:00:00", "direction": "expense", "amount": 45.00, "category": "休闲娱乐", "counterparty": "网易云音乐", "product": "年度会员", "payment_method": "支付宝"},
    {"transaction_time": "2026-02-22 09:30:00", "direction": "expense", "amount": 8.50, "category": "交通出行", "counterparty": "北京地铁", "product": "地铁充值"},
    {"transaction_time": "2026-02-21 11:00:00", "direction": "expense", "amount": 89.00, "category": "生活日用", "counterparty": "盒马鲜生", "product": "生鲜蔬果", "payment_method": "支付宝"},
    {"transaction_time": "2026-02-20 15:00:00", "direction": "expense", "amount": 1200.00, "category": "住房缴费", "counterparty": "国家电网", "product": "电费", "payment_method": "银行卡"},
    {"transaction_time": "2026-02-19 13:00:00", "direction": "income", "amount": 500.00, "category": "其他收入", "counterparty": "微信红包", "product": "生日红包"},
    {"transaction_time": "2026-02-18 18:30:00", "direction": "expense", "amount": 68.00, "category": "餐饮美食", "counterparty": "必胜客", "product": "比萨套餐", "payment_method": "微信支付"},
    {"transaction_time": "2026-02-17 10:00:00", "direction": "expense", "amount": 399.00, "category": "服饰美容", "counterparty": "优衣库", "product": "春装外套", "payment_method": "支付宝"},
    {"transaction_time": "2026-02-16 20:00:00", "direction": "expense", "amount": 29.90, "category": "休闲娱乐", "counterparty": "腾讯视频", "product": "月度会员"},
    {"transaction_time": "2026-02-15 09:00:00", "direction": "income", "amount": 200.00, "category": "其他收入", "counterparty": "闲鱼", "product": "二手物品出售"},
    {"transaction_time": "2026-02-14 19:30:00", "direction": "expense", "amount": 520.00, "category": "餐饮美食", "counterparty": "西贝莜面村", "product": "情人节晚餐", "payment_method": "微信支付"},
    {"transaction_time": "2026-02-13 08:00:00", "direction": "expense", "amount": 4.50, "category": "交通出行", "counterparty": "哈啰单车", "product": "骑行"},
    {"transaction_time": "2026-02-12 16:00:00", "direction": "expense", "amount": 159.00, "category": "医疗健康", "counterparty": "大众美团医疗", "product": "体检套餐"},
    {"transaction_time": "2026-02-10 12:00:00", "direction": "expense", "amount": 22.00, "category": "餐饮美食", "counterparty": "麦当劳", "product": "巨无霸套餐", "payment_method": "支付宝"},
    {"transaction_time": "2026-02-08 14:00:00", "direction": "expense", "amount": 3500.00, "category": "住房缴费", "counterparty": "房东", "product": "3月房租", "payment_method": "银行卡"},
    # Add more for Jan to fill out charts
    {"transaction_time": "2026-01-25 10:00:00", "direction": "income", "amount": 15000.00, "category": "工资收入", "counterparty": "某科技有限公司", "product": "1月工资"},
    {"transaction_time": "2026-01-20 12:00:00", "direction": "expense", "amount": 3500.00, "category": "住房缴费", "counterparty": "房东", "product": "2月房租"},
    {"transaction_time": "2026-01-15 18:00:00", "direction": "expense", "amount": 256.00, "category": "餐饮美食", "counterparty": "海底捞", "product": "聚餐"},
    {"transaction_time": "2026-01-10 09:00:00", "direction": "expense", "amount": 89.00, "category": "生活日用", "counterparty": "盒马鲜生", "product": "生鲜蔬果"},
    {"transaction_time": "2026-01-05 14:00:00", "direction": "expense", "amount": 199.00, "category": "服饰美容", "counterparty": "ZARA", "product": "冬季上衣"},
]


def setup_demo_data():
    """Register demo user and insert sample transactions."""
    print("Creating demo user...")
    resp = requests.post(f"{API}/auth/register", json={
        "username": DEMO_USER,
        "password": DEMO_PASS,
    })
    if resp.status_code == 409:
        # Already exists, log in
        resp = requests.post(f"{API}/auth/login", json={
            "username": DEMO_USER,
            "password": DEMO_PASS,
        })
    if resp.status_code not in (200, 201):
        print(f"Auth failed: {resp.status_code} {resp.text}")
        sys.exit(1)

    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Check if already has data
    check = requests.get(f"{API}/transactions?page_size=1", headers=headers)
    if check.json().get("total", 0) > 5:
        print("Demo data already exists, skipping insertion.")
        return token, headers

    print(f"Inserting {len(DEMO_TXS)} demo transactions...")
    for tx in DEMO_TXS:
        r = requests.post(f"{API}/transactions", headers=headers, json=tx)
        if r.status_code != 201:
            print(f"  Failed: {r.status_code} {r.text}")

    return token, headers


def cleanup_demo_user():
    """Delete the demo user's data."""
    import sqlite3
    db_path = Path(__file__).parent / "autocoin.db"
    conn = sqlite3.connect(str(db_path))
    uid = conn.execute("SELECT id FROM users WHERE username = ?", (DEMO_USER,)).fetchone()
    if uid:
        uid = uid[0]
        conn.execute("DELETE FROM transactions WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM import_batches WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM users WHERE id = ?", (uid,))
        conn.commit()
        print(f"Cleaned up demo user (id={uid})")
    conn.close()


def capture_screenshots(token):
    """Use Playwright to capture all screenshots."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ===== Desktop screenshots (1280x800) =====
        desktop = browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=2)
        page = desktop.new_page()

        # Set auth token
        page.goto(BASE_URL)
        page.evaluate(f"""() => {{
            localStorage.setItem('autocoin_token', '{token}');
            localStorage.setItem('autocoin_username', '{DEMO_USER}');
            localStorage.removeItem('autocoin_theme');
        }}""")

        # --- Login page (no token) ---
        print("  Capturing login page...")
        page2 = desktop.new_page()
        page2.goto(f"{BASE_URL}/#/login")
        page2.wait_for_timeout(800)
        page2.screenshot(path=str(IMG_DIR / "login.png"))
        page2.close()

        # --- Dashboard ---
        print("  Capturing dashboard...")
        page.goto(f"{BASE_URL}/#/dashboard")
        page.wait_for_timeout(2000)
        page.screenshot(path=str(IMG_DIR / "dashboard.png"))

        # --- Transactions ---
        print("  Capturing transactions...")
        page.goto(f"{BASE_URL}/#/transactions")
        page.wait_for_timeout(2000)
        page.screenshot(path=str(IMG_DIR / "transactions.png"))

        # --- Transactions with export dropdown ---
        print("  Capturing export dropdown...")
        page.click("#btn-export-toggle")
        page.wait_for_timeout(400)
        page.screenshot(path=str(IMG_DIR / "export-dropdown.png"))
        page.click("#btn-export-toggle")  # close it
        page.wait_for_timeout(200)

        # --- Transactions with batch selection ---
        print("  Capturing batch operations...")
        checkboxes = page.query_selector_all(".tx-row-check")
        for i, cb in enumerate(checkboxes[:3]):
            cb.click()
            page.wait_for_timeout(100)
        page.wait_for_timeout(300)
        page.screenshot(path=str(IMG_DIR / "batch-operations.png"))
        # Deselect
        sa = page.query_selector("#tx-select-all")
        if sa:
            sa.click()
            page.wait_for_timeout(100)
            sa.click()  # toggle back to none

        # --- Import page ---
        print("  Capturing import page...")
        page.goto(f"{BASE_URL}/#/import")
        page.wait_for_timeout(1500)
        page.screenshot(path=str(IMG_DIR / "import.png"))

        # --- Stats page ---
        print("  Capturing stats page...")
        page.goto(f"{BASE_URL}/#/stats")
        page.wait_for_timeout(2500)
        page.screenshot(path=str(IMG_DIR / "stats.png"))

        # --- Dark mode ---
        print("  Capturing dark mode...")
        page.evaluate("""() => {
            document.documentElement.setAttribute('data-theme', 'dark');
            localStorage.setItem('autocoin_theme', 'dark');
        }""")
        page.goto(f"{BASE_URL}/#/dashboard")
        page.wait_for_timeout(2000)
        page.screenshot(path=str(IMG_DIR / "dark-mode.png"))

        # Dark mode transactions
        page.goto(f"{BASE_URL}/#/transactions")
        page.wait_for_timeout(2000)
        page.screenshot(path=str(IMG_DIR / "dark-transactions.png"))

        # Reset to light
        page.evaluate("""() => {
            document.documentElement.setAttribute('data-theme', 'light');
            localStorage.setItem('autocoin_theme', 'light');
        }""")

        desktop.close()

        # ===== Mobile screenshots (375x812, iPhone-like) =====
        mobile = browser.new_context(
            viewport={"width": 375, "height": 812},
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
        )
        mpage = mobile.new_page()

        # Set auth
        mpage.goto(BASE_URL)
        mpage.evaluate(f"""() => {{
            localStorage.setItem('autocoin_token', '{token}');
            localStorage.setItem('autocoin_username', '{DEMO_USER}');
            localStorage.removeItem('autocoin_theme');
        }}""")

        # --- Mobile login ---
        print("  Capturing mobile login...")
        mpage2 = mobile.new_page()
        mpage2.goto(f"{BASE_URL}/#/login")
        mpage2.wait_for_timeout(800)
        mpage2.screenshot(path=str(IMG_DIR / "mobile-login.png"))
        mpage2.close()

        # --- Mobile dashboard ---
        print("  Capturing mobile dashboard...")
        mpage.goto(f"{BASE_URL}/#/dashboard")
        mpage.wait_for_timeout(2000)
        mpage.screenshot(path=str(IMG_DIR / "mobile-dashboard.png"))

        # --- Mobile transactions ---
        print("  Capturing mobile transactions...")
        mpage.goto(f"{BASE_URL}/#/transactions")
        mpage.wait_for_timeout(2000)
        mpage.screenshot(path=str(IMG_DIR / "mobile-transactions.png"))

        # --- Mobile dark mode ---
        print("  Capturing mobile dark mode...")
        mpage.evaluate("""() => {
            document.documentElement.setAttribute('data-theme', 'dark');
        }""")
        mpage.goto(f"{BASE_URL}/#/dashboard")
        mpage.wait_for_timeout(2000)
        mpage.screenshot(path=str(IMG_DIR / "mobile-dark.png"))

        mobile.close()
        browser.close()

    print(f"All screenshots saved to {IMG_DIR}/")


if __name__ == "__main__":
    print("=== AutoCoin Screenshot Capture ===\n")

    # Step 1: Setup demo data
    token, headers = setup_demo_data()

    # Step 2: Capture screenshots
    print("\nCapturing screenshots...")
    capture_screenshots(token)

    # Step 3: Cleanup demo user
    print("\nCleaning up demo user...")
    cleanup_demo_user()

    print("\n✅ Done! Screenshots saved to docs/images/")
