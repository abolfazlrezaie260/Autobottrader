# Autobottrader (Mofid EasyTrader Automation, Drafts & Dynamic Ping Compensation)

A high-precision web automation bot for **Mofid EasyTrader** built with **Python** and **Playwright**.

---

## Key Features

1. **Dynamic Ping Compensation (محاسبه خودکار پینگ و تصحیح دینامیک تایم شلیک):**
   - In the final 30 seconds before order submission, the bot automatically sends live probes to the EasyTrader server from the browser to measure real-time Round-Trip Time (RTT / Ping).
   - Computes one-way network latency: $\text{Latency} = \frac{\text{RTT}}{2}$.
   - Dynamically shifts the trigger timestamp earlier (e.g. from `08:45:00.000` to `08:44:59.960` if one-way latency is 40ms) so that the order packet lands in the trading engine precisely at the start of the market.

2. **EasyTrader Browser Clock Synchronization (#easy-clock-id):**
   - Calibrates system time against the live server clock in the browser with millisecond accuracy.

3. **Auto-Select Maximum Volume & Ceiling Price:**
   - **Max Quantity:** Automatically clicks `[data-cy="order-form-max-quantity"]` to select the highest allowable order volume.
   - **Ceiling Price:** Automatically clicks `[data-cy="order-form-max-price"]` to select the maximum price threshold.

4. **Draft (پیش‌نویس) & Burst Order Execution:**
   - Configurable action type: `action_type: "send"` (شلیک رگباری به هسته معاملات) or `"draft"` (پیش‌نویس).

5. **Permanent Session Persistence (`session_state.json`):**
   - Automatically saves and restores JWT tokens, cookies, and localStorage so you never have to log in or enter SMS 2FA again.

6. **Auto-Save Stock Details (`stocks_data/{symbol}.txt`):**
   - Auto-logs comprehensive data for any stock viewed in EasyTrader.

---

## Configuration (`config.yaml`)

```yaml
order:
  symbol: "کرازی"
  side: "buy"
  quantity: 0
  use_max_quantity: true   # بیشترین حجم پیشنهادی
  price: 0
  use_ceiling_price: true  # سقف قیمت مجاز
  action_type: "send"      # send (ارسال سفارش) یا draft (پیش‌نویس)

schedule:
  enabled: true
  target_time: "08:45:00.000" # زمان هدف رسیدن سفارش به سرور
  dynamic_ping_compensation: true # محاسبه خودکار پینگ و اصلاح زمان شلیک
  ping_lookback_seconds: 30       # اندازه‌گیری پینگ در ۳۰ ثانیه پایانی
  ping_samples: 5                 # تعداد نمونه‌های پینگ
  max_attempts: 5
  interval_ms: 200
```

## Quick Start

```bash
git pull
python3 main.py
```
