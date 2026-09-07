# Autobottrader (Mofid EasyTrader Automation, Drafts & Stock Data Logger)

A high-precision web automation bot for **Mofid EasyTrader** built with **Python** and **Playwright**.

---

## Key Features

1. **Draft (پیش‌نویس) & Order Execution:**
   - Supports creating **Drafts** (`action_type: "draft"`) via `[data-cy="oms-order-form-draft-button-buy"]`.
   - Supports direct trading engine orders (`action_type: "send"`).

2. **Auto-Select Maximum Volume & Ceiling Price:**
   - **Max Quantity:** Automatically clicks `[data-cy="order-form-max-quantity"]` to select the highest allowable order volume.
   - **Ceiling Price:** Automatically clicks `[data-cy="order-form-max-price"]` to select the maximum price threshold.

3. **Auto-Save Stock Details to Text Files (`stocks_data/{symbol}.txt`):**
   - Whenever you open any stock in EasyTrader (e.g. کرازی, فولاد, داروند, لبن), the bot automatically detects it and logs its complete data into an individual text file:
     - Symbol Name
     - Ceiling & Floor prices (سقف و کف قیمت مجاز)
     - Previous close, last traded, closing prices
     - Market trading state (مجاز / متوقف)
     - Buy & Sell queue depth (best limit, volume, orders count)
     - User current owned quantity (دارایی فعلی)
     - Live EasyTrader server clock timestamp

4. **Permanent Session Persistence (`session_state.json`):**
   - Automatically saves and restores JWT tokens, cookies, and localStorage so you never have to enter SMS 2FA again after the initial login.

5. **Sub-millisecond Precision Scheduler:**
   - Configurable trigger time down to milliseconds (e.g. `08:44:59.850`) for IPOs and order queueing.
   - Immediate execution mode when `schedule.enabled: false`.

---

## Quick Start (سهم کرازی - ثبت پیش‌نویس با حداکثر حجم و قیمت)

در فایل `config.yaml`:
```yaml
order:
  symbol: "کرازی"
  side: "buy"
  quantity: 0
  use_max_quantity: true   # انتخاب خودکار بیشترین حجم پیشنهادی
  price: 0
  use_ceiling_price: true  # انتخاب خودکار سقف قیمت
  action_type: "draft"     # ثبت به عنوان پیش‌نویس
```

اجرا در ترمینال:
```bash
git pull
python3 main.py
```
