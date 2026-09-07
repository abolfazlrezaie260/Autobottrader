import random
import asyncio
import re
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
    Manages interactions, symbol verification, and order placement on Mofid EasyTrader
    Optimized based on EasyTrader's DOM structure and data-cy attributes.
    """
    def __init__(self, page: Page, config: Config):
        self.page = page
        self.config = config

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
            "[data-cy='order-buy-btn']",
            "[data-cy='market-depth-best-limit']",
            "[data-cy='symbol-header-last-span']"
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

    async def get_active_symbol_name(self) -> Optional[str]:
        """Read currently active symbol from symbol-header-symbol-name element"""
        try:
            elem = await self.page.query_selector("[data-cy='symbol-header-symbol-name']")
            if elem:
                text = await elem.inner_text()
                return text.strip()
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
        Extract daily floor and ceiling prices from candle chart (symbol-detail-candle)
        minPrice -> Daily Floor
        maxPrice -> Daily Ceiling (Required for queuing / سرخطی)
        prevPrice -> Previous Close
        lastPrice -> Last Traded Price
        """
        prices = {"min": None, "max": None, "prev": None, "last": None, "closing": None}
        
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
            print(f"[!] Error reading price limits: {e}")

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

    async def prepare_order(self):
        """
        Prepare order form:
        1. Check if target symbol is already active on screen (avoids unnecessary search delay)
        2. Check symbol trading status (مجاز)
        3. Extract dynamic ceiling price from candle maxPrice if configured
        4. Click Buy/Sell button to open order panel
        5. Populate quantity and price inputs
        """
        target_symbol = self.config.order.symbol.strip()
        current_symbol = await self.get_active_symbol_name()

        print(f"[*] Target symbol: {target_symbol} | Currently active: {current_symbol}")

        # Search for symbol only if not already opened
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

        # Verify trading status
        state = await self.get_symbol_state()
        if state:
            print(f"[*] Market trading state: {state}")
            if state != "مجاز":
                print(f"[!] Warning: Symbol state is '{state}' (orders might be rejected if not 'مجاز').")

        # Extract price limits
        thresholds = await self.get_price_thresholds()
        print(f"[*] Extracted daily price limits: Floor={thresholds['min']} | Ceiling={thresholds['max']} | Last={thresholds['last']}")

        # Determine price to use
        final_price = self.config.order.price
        if self.config.order.use_ceiling_price:
            if thresholds["max"]:
                final_price = thresholds["max"]
                print(f"[✓] Daily ceiling price applied automatically: {final_price}")
            else:
                print("[!] Could not extract ceiling price from candle; using manual/fallback price.")

        # Show queue depth summary before opening order form
        depth = await self.get_market_depth_summary()
        if depth["total_buy_volume"]:
            print(f"[*] Market buy queue status: Volume={depth['total_buy_volume']} | Orders={depth['total_buy_count']}")

        # Click Buy or Sell button to open order drawer/form
        order_btn_selector = "button[data-cy='order-buy-btn']" if self.config.order.side == "buy" else "button[data-cy='order-sell-btn']"
        print(f"[*] Clicking {self.config.order.side} button ({order_btn_selector})...")
        await self.human_click(order_btn_selector)

        # Fill order volume/quantity
        quantity_selector = "[data-cy='order-volume-input'], input[name='volume'], input[placeholder*='حجم']"
        try:
            await self.human_type(quantity_selector, str(self.config.order.quantity))
            print(f"[✓] Order volume populated: {self.config.order.quantity}")
        except Exception as e:
            print(f"[!] Volume input field not found: {e}")

        # Fill order price
        if final_price > 0:
            price_selector = "[data-cy='order-price-input'], input[name='price'], input[placeholder*='قیمت']"
            try:
                await self.human_type(price_selector, str(final_price))
                print(f"[✓] Order price populated: {final_price}")
            except Exception as e:
                print(f"[!] Price input field not found: {e}")

        print("[✓] Order form prepared and armed for execution at target time.")

    async def execute_order_burst(self):
        """Execute final order submission burst"""
        submit_selectors = [
            "[data-cy='order-submit-btn']",
            "[data-cy='order-send-btn']",
            "button[type='submit'].order-buy-btn",
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
