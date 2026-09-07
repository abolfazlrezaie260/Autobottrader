import random
import asyncio
import os
import re
from datetime import datetime
from typing import Optional, Dict, Any
from playwright.async_api import Page
from config import Config

def parse_number(text: Optional[str]) -> Optional[int]:
    """Parse comma-separated or Persian/English numeral string to integer"""
    if not text:
        return None
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    for i, p_digit in enumerate(persian_digits):
        text = text.replace(p_digit, str(i))
    cleaned = re.sub(r"[^\d]", "", text.strip())
    return int(cleaned) if cleaned else None

class EasyTraderAutomation:
    """
    Manages interactions, symbol monitoring, data logging, and order execution
    on Mofid EasyTrader based on verified DOM attributes.
    """
    def __init__(self, page: Page, config: Config):
        self.page = page
        self.config = config
        self.last_saved_symbol: Optional[str] = None

    async def human_delay(self, min_factor: float = 1.0, max_factor: float = 1.0):
        """Introduce randomized delay to emulate human behavior"""
        delay_ms = random.randint(
            int(self.config.anti_detection.random_delay_min_ms * min_factor),
            int(self.config.anti_detection.random_delay_max_ms * max_factor)
        )
        await asyncio.sleep(delay_ms / 1000.0)

    async def human_click(self, selector: str, timeout: int = 10000):
        """Move mouse with natural jitter and click at random offset within element box"""
        elem = await self.page.wait_for_selector(selector, timeout=timeout)
        box = await elem.bounding_box()
        if box and self.config.anti_detection.human_mouse_movement:
            offset_x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
            offset_y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
            await self.page.mouse.move(offset_x, offset_y, steps=random.randint(4, 10))
            await self.human_delay(0.5, 1.0)
            await self.page.mouse.click(offset_x, offset_y)
        else:
            await elem.click()

    async def human_type(self, selector: str, text: str, timeout: int = 10000):
        """Type values with variable inter-keystroke delays"""
        elem = await self.page.wait_for_selector(selector, timeout=timeout)
        await elem.click()
        await self.human_delay(0.5, 1.0)
        
        # Clear existing text
        await self.page.keyboard.press("Control+A")
        await self.page.keyboard.press("Backspace")
        
        for char in str(text):
            await self.page.keyboard.type(char, delay=random.randint(35, 95))
        await self.human_delay(0.5, 1.0)

    async def wait_for_login(self):
        """Check user authentication status and wait for manual login if needed"""
        print("[*] Navigating to EasyTrader...")
        await self.page.goto(self.config.app.url, wait_until="domcontentloaded")
        
        print("[*] Checking user authentication state...")
        logged_in_selectors = [
            "[data-cy='symbol-header-symbol-name']",
            "[data-cy='order-form-header-symbol-name']",
            "[data-cy='order-buy-btn']",
            "[data-cy='market-depth-best-limit']",
            "[data-cy='order-list-clock']"
        ]
        
        is_logged_in = False
        for _ in range(6):
            for sel in logged_in_selectors:
                if await self.page.query_selector(sel):
                    is_logged_in = True
                    break
            if is_logged_in:
                break
            await asyncio.sleep(1)

        if not is_logged_in:
            print("=" * 60)
            print("[!] No active session found. Please log in within the browser (Username, Password, 2FA SMS).")
            print("[!] Once the dashboard loads, the bot will automatically resume execution.")
            print("=" * 60)
            
            while True:
                for sel in logged_in_selectors:
                    if await self.page.query_selector(sel):
                        is_logged_in = True
                        break
                if is_logged_in:
                    break
                await asyncio.sleep(2)

        print("[✓] User login confirmed successfully.")

    async def get_server_clock(self) -> Optional[str]:
        """Read EasyTrader server clock (#easy-clock-id)"""
        clock_selectors = ["#easy-clock-id", "[data-cy='order-list-clock'] span"]
        for sel in clock_selectors:
            try:
                elem = await self.page.query_selector(sel)
                if elem:
                    text = await elem.inner_text()
                    if text and text.strip():
                        return text.strip()
            except Exception:
                pass
        return None

    async def get_active_symbol_name(self) -> Optional[str]:
        """Read currently active symbol name from header or order form"""
        selectors = [
            "[data-cy='symbol-header-symbol-name']",
            "[data-cy='order-form-header-symbol-name']"
        ]
        for sel in selectors:
            try:
                elem = await self.page.query_selector(sel)
                if elem:
                    text = await elem.inner_text()
                    clean = text.strip()
                    if clean:
                        return clean
            except Exception:
                pass
        return None

    async def get_symbol_state(self) -> Optional[str]:
        """Check whether the symbol trading state is active (مجاز) via symbol-state-icon"""
        try:
            elem = await self.page.query_selector("symbol-state-icon span[title]")
            if elem:
                title = await elem.get_attribute("title")
                return title.strip() if title else None
        except Exception:
            pass
        return None

    async def get_price_thresholds(self) -> Dict[str, Optional[int]]:
        """
        Extract daily floor and ceiling prices from candle chart and order form buttons
        minPrice -> Daily Floor
        maxPrice -> Daily Ceiling
        """
        prices = {"min": None, "max": None, "prev": None, "last": None, "closing": None}
        
        # 1. From candle chart
        try:
            max_elem = await self.page.query_selector("[data-cy='symbol-detail-candle-max-price']")
            if max_elem:
                prices["max"] = parse_number(await max_elem.inner_text())

            min_elem = await self.page.query_selector("[data-cy='symbol-detail-candle-min-price']")
            if min_elem:
                prices["min"] = parse_number(await min_elem.inner_text())

            prev_elem = await self.page.query_selector("[data-cy='symbol-detail-candle-prev-price']")
            if prev_elem:
                prices["prev"] = parse_number(await prev_elem.inner_text())

            last_elem = await self.page.query_selector("[data-cy='symbol-header-last-span']")
            if last_elem:
                prices["last"] = parse_number(await last_elem.inner_text())

            closing_elem = await self.page.query_selector("[data-cy='symbol-header-closing-price']")
            if closing_elem:
                prices["closing"] = parse_number(await closing_elem.inner_text())
        except Exception as e:
            print(f"[!] Error reading candle prices: {e}")

        # 2. Fallback or cross-check from order form max/min price buttons if open
        if not prices["max"]:
            try:
                form_max_elem = await self.page.query_selector("[data-cy='order-form-max-price'] span")
                if form_max_elem:
                    prices["max"] = parse_number(await form_max_elem.inner_text())
            except Exception:
                pass

        if not prices["min"]:
            try:
                form_min_elem = await self.page.query_selector("[data-cy='order-form-min-price'] span")
                if form_min_elem:
                    prices["min"] = parse_number(await form_min_elem.inner_text())
            except Exception:
                pass

        return prices

    async def get_market_depth_summary(self) -> Dict[str, Any]:
        """Extract best bid/ask limits and total queue sizes"""
        summary = {
            "best_buy_price": None,
            "best_sell_price": None,
            "total_buy_volume": None,
            "total_sell_volume": None,
            "total_buy_count": None
        }
        try:
            buy_price_elem = await self.page.query_selector("[data-cy='best-buy-limit-price-0']")
            if buy_price_elem:
                summary["best_buy_price"] = parse_number(await buy_price_elem.inner_text())

            sell_price_elem = await self.page.query_selector("[data-cy='best-sell-limit-price-0']")
            if sell_price_elem:
                summary["best_sell_price"] = parse_number(await sell_price_elem.inner_text())

            buy_vol_elem = await self.page.query_selector("[data-cy='market-depth-aggregates-buy-volume']")
            if buy_vol_elem:
                summary["total_buy_volume"] = parse_number(await buy_vol_elem.inner_text())

            sell_vol_elem = await self.page.query_selector("[data-cy='market-depth-aggregates-sell-volume']")
            if sell_vol_elem:
                summary["total_sell_volume"] = parse_number(await sell_vol_elem.inner_text())

            buy_cnt_elem = await self.page.query_selector("[data-cy='market-depth-aggregates-buy-count']")
            if buy_cnt_elem:
                summary["total_buy_count"] = parse_number(await buy_cnt_elem.inner_text())
        except Exception as e:
            print(f"[!] Error fetching market depth: {e}")

        return summary

    async def get_user_current_asset(self) -> Optional[int]:
        """Read user's current owned quantity/asset for this symbol"""
        try:
            elem = await self.page.query_selector("[data-cy='order-summary-asset']")
            if elem:
                return parse_number(await elem.inner_text())
        except Exception:
            pass
        return None

    async def save_symbol_info(self, symbol_name: Optional[str] = None) -> Optional[str]:
        """
        Save comprehensive details of the currently opened stock into a dedicated text file:
        stocks_data/{symbol}.txt
        """
        if not symbol_name:
            symbol_name = await self.get_active_symbol_name()

        if not symbol_name:
            return None

        # Clean symbol name from extra characters
        symbol_name = symbol_name.replace("/", "-").strip()

        prices = await self.get_price_thresholds()
        depth = await self.get_market_depth_summary()
        state = await self.get_symbol_state() or "نامشخص"
        server_clock = await self.get_server_clock() or "N/A"
        user_asset = await self.get_user_current_asset()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        output_dir = self.config.storage.output_dir
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, f"{symbol_name}.txt")

        content = f"""============================================================
Symbol (نماد): {symbol_name}
Recorded At: {now_str}
EasyTrader Server Clock: {server_clock}
============================================================
[Trading Status / وضعیت نماد]: {state}

[Daily Price Thresholds / دامنه نوسان روزانه]:
  • Ceiling Price (سقف قیمت مجاز): {prices['max'] if prices['max'] is not None else 'N/A'}
  • Floor Price   (کف قیمت مجاز):  {prices['min'] if prices['min'] is not None else 'N/A'}
  • Prev Close    (پایانی دیروز):  {prices['prev'] if prices['prev'] is not None else 'N/A'}
  • Last Traded   (آخرین معامله):  {prices['last'] if prices['last'] is not None else 'N/A'}
  • Closing Price (قیمت پایانی):   {prices['closing'] if prices['closing'] is not None else 'N/A'}

[Market Depth & Queues / اطلاعات صف و مظنه]:
  • Buy Queue (صف خرید):
      - Best Limit Price: {depth['best_buy_price'] if depth['best_buy_price'] is not None else 'N/A'}
      - Total Volume:     {depth['total_buy_volume'] if depth['total_buy_volume'] is not None else 'N/A'}
      - Total Orders:     {depth['total_buy_count'] if depth['total_buy_count'] is not None else 'N/A'}
  • Sell Queue (صف فروش):
      - Best Limit Price: {depth['best_sell_price'] if depth['best_sell_price'] is not None else 'N/A'}
      - Total Volume:     {depth['total_sell_volume'] if depth['total_sell_volume'] is not None else 'N/A'}

[Account Holdings / وضعیت دارایی کاربر در نماد]:
  • Current Owned Quantity: {user_asset if user_asset is not None else 'N/A'}
============================================================
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"[✓] Successfully saved data for symbol '{symbol_name}' to {file_path}")
        self.last_saved_symbol = symbol_name
        return file_path

    async def watch_symbols_task(self):
        """Background watcher: saves text file for any stock opened by the user"""
        print("[*] Stock watcher active. Any stock opened in EasyTrader will be auto-saved to files.")
        while True:
            try:
                current = await self.get_active_symbol_name()
                if current and current != self.last_saved_symbol:
                    # Give UI a brief moment to render depths & candle
                    await asyncio.sleep(0.8)
                    await self.save_symbol_info(current)
            except Exception:
                pass
            await asyncio.sleep(1.0)

    async def prepare_order(self):
        """
        Prepare order form with verified selectors:
        1. Check/verify active symbol
        2. Save symbol data to text file
        3. Open order form if closed
        4. Populate quantity via [data-cy='order-form-input-quantity'] or #quantity
        5. Populate price or click [data-cy='order-form-max-price'] for ceiling
        """
        target_symbol = self.config.order.symbol.strip()
        current_symbol = await self.get_active_symbol_name()

        print(f"[*] Target symbol: {target_symbol} | Currently active: {current_symbol}")

        if current_symbol != target_symbol:
            print(f"[*] Searching for symbol: {target_symbol}...")
            search_selector = "[data-cy='quick-search-input'], input[placeholder*='جستجو']"
            try:
                await self.human_type(search_selector, target_symbol)
                await self.page.keyboard.press("Enter")
                await asyncio.sleep(1.5)
            except Exception as e:
                print(f"[!] Search error / timeout: {e}")
        else:
            print("[✓] Target symbol is already active on screen (skipping search step).")

        # Save symbol info to disk
        await self.save_symbol_info(target_symbol)

        # Verify trading status
        state = await self.get_symbol_state()
        if state and state != "مجاز":
            print(f"[!] Warning: Symbol state is '{state}' (orders might be rejected if not 'مجاز').")

        # Extract price limits
        thresholds = await self.get_price_thresholds()
        print(f"[*] Daily price limits: Floor={thresholds['min']} | Ceiling={thresholds['max']} | Last={thresholds['last']}")

        # Ensure order panel is opened
        quantity_input_sel = "[data-cy='order-form-input-quantity'], #quantity"
        form_is_open = await self.page.query_selector(quantity_input_sel)
        if not form_is_open:
            order_btn_selector = "button[data-cy='order-buy-btn']" if self.config.order.side == "buy" else "button[data-cy='order-sell-btn']"
            print(f"[*] Opening order drawer via {order_btn_selector}...")
            await self.human_click(order_btn_selector)
            await asyncio.sleep(0.5)

        # Fill order volume/quantity using verified selector
        try:
            await self.human_type(quantity_input_sel, str(self.config.order.quantity))
            print(f"[✓] Order quantity populated: {self.config.order.quantity}")
        except Exception as e:
            print(f"[!] Quantity input field not found: {e}")

        # Set price: If use_ceiling_price is true, try clicking max-price button or type ceiling
        if self.config.order.use_ceiling_price:
            max_btn_sel = "[data-cy='order-form-max-price']"
            max_btn = await self.page.query_selector(max_btn_sel)
            if max_btn:
                print("[*] Clicking auto max price button [data-cy='order-form-max-price']...")
                await self.human_click(max_btn_sel)
                print("[✓] Ceiling price selected via max price button.")
            elif thresholds["max"]:
                price_input_sel = "[data-cy='order-form-input-price'], #price"
                await self.human_type(price_input_sel, str(thresholds["max"]))
                print(f"[✓] Ceiling price populated directly: {thresholds['max']}")
        elif self.config.order.price > 0:
            price_input_sel = "[data-cy='order-form-input-price'], #price"
            await self.human_type(price_input_sel, str(self.config.order.price))
            print(f"[✓] Custom price populated: {self.config.order.price}")

        # Save again to capture updated order form summary/assets
        await self.save_symbol_info(target_symbol)
        print("[✓] Order form prepared and armed for execution at target time.")

    async def execute_order_burst(self):
        """Execute final order submission burst using verified submit selector"""
        submit_selectors = [
            "[data-cy='oms-order-form-submit-button-buy']",
            "button[data-cy='oms-order-form-submit-button-buy']",
            "[data-cy='order-submit-btn']",
            "button[data-cy='order-buy-btn']"
        ]
        
        print(f"[*] Firing orders to trading engine (Max attempts: {self.config.schedule.max_attempts})...")

        for attempt in range(1, self.config.schedule.max_attempts + 1):
            clicked = False
            for sel in submit_selectors:
                try:
                    btn = await self.page.query_selector(sel)
                    if btn and await btn.is_visible():
                        await btn.click()
                        print(f"[✓] Sent order attempt #{attempt} via '{sel}'.")
                        clicked = True
                        break
                except Exception as e:
                    print(f"[!] Error clicking '{sel}': {e}")

            if not clicked:
                print(f"[!] No active submit button found on attempt #{attempt}.")

            if attempt < self.config.schedule.max_attempts:
                await asyncio.sleep(self.config.schedule.interval_ms / 1000.0)

        # Post-submission check on order list
        await asyncio.sleep(1.5)
        await self.check_recent_order_status()

    async def check_recent_order_status(self):
        """Check order status inside order-list container"""
        try:
            alert = await self.page.query_selector("[data-cy='state-notification-alert']")
            if alert:
                alert_text = await alert.inner_text()
                print(f"[!] Order List Alert: {alert_text or 'خطا در سفارش'}")
            else:
                print("[✓] No immediate order error detected in order list.")
        except Exception:
            pass
