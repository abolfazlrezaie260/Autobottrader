# Autobottrader (Mofid EasyTrader Automation & Stock Data Logger)

A high-precision web automation bot for **Mofid EasyTrader** built with **Python** and **Playwright**.

---

## Key Features

1. **Auto-Save Stock Details to Text Files (`stocks_data/{symbol}.txt`):**
   - Whenever you open any stock in EasyTrader (e.g. فولاد, داروند, لبن, شپنا), the bot automatically detects it and logs its complete data into an individual text file:
     - Symbol Name
     - Ceiling & Floor prices (سقف و کف قیمت مجاز)
     - Previous close, last traded, closing prices
     - Market trading state (مجاز / متوقف)
     - Buy & Sell queue depth (best limit, volume, orders count)
     - User current owned quantity (دارایی فعلی)
     - Live EasyTrader server clock timestamp

2. **Accurate Angular & EasyTrader Selectors:**
   - Volume Input: `[data-cy="order-form-input-quantity"]` / `#quantity`
   - Price Input: `[data-cy="order-form-input-price"]` / `#price`
   - Quick Max Price Button: `[data-cy="order-form-max-price"]`
   - Submit Buy Button: `[data-cy="oms-order-form-submit-button-buy"]`
   - Server Clock: `#easy-clock-id` / `[data-cy="order-list-clock"]`
   - Order List & Alerts: `[data-cy="order-list-container"]` / `[data-cy="state-notification-alert"]`

3. **Sub-millisecond Precision Scheduler:**
   - Configurable trigger time down to milliseconds (e.g. `08:44:59.850`) for IPOs and order queueing.
   - Dual-phase timing: non-blocking sleep followed by a 50ms busy-wait loop.

4. **Stealth & Anti-Bot Evading:**
   - Connects directly to Google Chrome via CDP (`--remote-debugging-port=9222`) or uses persistent profile.
   - Injects stealth scripts removing `navigator.webdriver`.
   - Natural mouse curves and randomized keystroke delays.

---

## Directory Structure

```
Autobottrader/
├── config.yaml          # Target symbol, quantity, schedule time, storage
├── config.py            # Dataclass configuration loader
├── browser.py           # Chrome/Chromium manager & stealth injection
├── scheduler.py         # Millisecond precision timer
├── trader.py            # EasyTrader DOM interactions, data extractor & order executor
├── main.py              # Application lifecycle & background symbol watcher
├── requirements.txt     # Python dependencies
├── stocks_data/         # Auto-generated folder containing {symbol}.txt files
└── README.md
```

---

## Quick Start

```bash
# 1. Pull the latest code
git pull

# 2. Launch Google Chrome with debugging port
"/Applications/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing" --remote-debugging-port=9222 --user-data-dir="$HOME/chrome_easytrader_profile" &

# 3. Run the bot
python3 main.py
```
