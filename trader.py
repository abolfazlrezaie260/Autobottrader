import random
import asyncio
import re
from typing import Optional, Dict, Any
from playwright.async_api import Page
from config import Config

def parse_number(text: Optional[str]) -> Optional[int]:
    """تبدیل اعداد دارای کاما، فاصله و ارقام فارسی/انگلیسی به عدد صحیح"""
    if not text:
        return None
    # تبدیل ارقام فارسی به انگلیسی
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    for i, p_digit in enumerate(persian_digits):
        text = text.replace(p_digit, str(i))
    # حذف کاما و فاصله‌ها
    cleaned = re.sub(r"[^\d]", "", text.strip())
    return int(cleaned) if cleaned else None

class EasyTraderAutomation:
    """
    مدیریت اتوماسیون تعاملات و ارسال سفارش در ایزیتریدر مفید
    بهینه‌سازی‌شده بر اساس ساختار دقیق DOM و سلکتورهای data-cy
    """
    def __init__(self, page: Page, config: Config):
        self.page = page
        self.config = config

    async def human_delay(self, min_factor: float = 1.0, max_factor: float = 1.0):
        """ایجاد تاخیر تصادفی بین اقدامات برای شبیه‌سازی رفتار طبیعی کاربر"""
        delay_ms = random.randint(
            int(self.config.anti_detection.random_delay_min_ms * min_factor),
            int(self.config.anti_detection.random_delay_max_ms * max_factor)
        )
        await asyncio.sleep(delay_ms / 1000.0)

    async def human_click(self, selector: str, timeout: int = 10000):
        """حرکت ماوس با انحراف و کلیک انسانی در نقطه‌ای تصادفی از دکمه"""
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
        """تایپ مقادیر با تاخیرهای متغیر بین کلیدها"""
        elem = await self.page.wait_for_selector(selector, timeout=timeout)
        await elem.click()
        await self.human_delay(0.5, 1.0)
        
        # پاک کردن محتوای قبلی
        await self.page.keyboard.press("Control+A")
        await self.page.keyboard.press("Backspace")
        
        for char in str(text):
            await self.page.keyboard.type(char, delay=random.randint(35, 95))
        await self.human_delay(0.5, 1.0)

    async def wait_for_login(self):
        """بررسی وضعیت لاگین بودن کاربر و در صورت نیاز انتظار برای ورود دستی"""
        print("[*] در حال باز کردن صفحه ایزیتریدر...")
        await self.page.goto(self.config.app.url, wait_until="domcontentloaded")
        
        print("[*] بررسی وضعیت احراز هویت کاربر...")
        # استفاده از سلکتورهای استخراج‌شده از سورس ایزیتریدر
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
            print("[!] نشست فعال یافت نشد. لطفاً در پنجره مرورگر لاگین کنید (نام کاربری، رمز، 2FA).")
            print("[!] پس از بارگذاری صفحه اصلی و داشبورد، ربات به طور خودکار به کار خود ادامه می‌دهد.")
            print("=" * 60)
            
            while True:
                for sel in logged_in_selectors:
                    if await self.page.query_selector(sel):
                        is_logged_in = True
                        break
                if is_logged_in:
                    break
                await asyncio.sleep(2)

        print("[✓] ورود موفق کاربر تأیید شد.")

    async def get_active_symbol_name(self) -> Optional[str]:
        """دریافت نام نماد فعال از طریق سلکتور symbol-header-symbol-name"""
        try:
            elem = await self.page.query_selector("[data-cy='symbol-header-symbol-name']")
            if elem:
                text = await elem.inner_text()
                return text.strip()
        except Exception:
            pass
        return None

    async def get_symbol_state(self) -> Optional[str]:
        """بررسی وضعیت مجاز/متوقف بودن نماد از طریق المان symbol-state-icon"""
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
        استخراج سقف و کف قیمت مجاز روزانه از نمودار شمعی (symbol-detail-candle)
        minPrice -> کف قیمت
        maxPrice -> سقف قیمت (مورد نیاز سرخطی)
        prevPrice -> قیمت پایانی دیروز
        lastPrice -> آخرین معامله
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
            print(f"[!] خطا در استخراج آستانه قیمت: {e}")

        return prices

    async def get_market_depth_summary(self) -> Dict[str, Any]:
        """استخراج اطلاعات بهترین مظنه‌ها و صف خرید/فروش (Best Limits)"""
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
            print(f"[!] خطا در دریافت خلاصه مظنه‌ها: {e}")

        return summary

    async def prepare_order(self):
        """
        آماده‌سازی فرم سفارش:
        ۱. بررسی اینکه آیا نماد هدف هم‌اکنون باز است یا خیر (صرفه‌جویی در جستجو)
        ۲. بررسی وضعیت مجاز بودن نماد
        ۳. استخراج سقف قیمت از روی candle max price در صورت نیاز
        ۴. کلیک روی دکمه خرید/فروش
        ۵. درج حجم و قیمت در پنل سفارش
        """
        target_symbol = self.config.order.symbol.strip()
        current_symbol = await self.get_active_symbol_name()

        print(f"[*] نماد درخواستی: {target_symbol} | نماد فعال فعلی: {current_symbol}")

        # در صورتی که نماد هدف از قبل باز نیست، جستجو انجام می‌شود
        if current_symbol != target_symbol:
            print(f"[*] در حال جستجوی نماد {target_symbol}...")
            search_selector = "[data-cy='quick-search-input'], input[placeholder*='جستجو']"
            try:
                await self.human_type(search_selector, target_symbol)
                await self.page.keyboard.press("Enter")
                await asyncio.sleep(1.5)
            except Exception as e:
                print(f"[!] خطا در جستجوی نماد: {e}")
        else:
            print("[✓] نماد مورد نظر از قبل در صفحه لود شده است (صرفه‌جویی در زمان جستجو).")

        # بررسی وضعیت نماد
        state = await self.get_symbol_state()
        if state:
            print(f"[*] وضعیت معاملاتی نماد: {state}")
            if state != "مجاز":
                print(f"[!] هشدار: وضعیت نماد '{state}' است و ممکن است سفارش رد شود.")

        # استخراج قیمت‌ها
        thresholds = await self.get_price_thresholds()
        print(f"[*] آستانه قیمت استخراج‌شده: کف={thresholds['min']} | سقف={thresholds['max']} | آخرین={thresholds['last']}")

        # تعیین قیمت نهایی
        final_price = self.config.order.price
        if self.config.order.use_ceiling_price:
            if thresholds["max"]:
                final_price = thresholds["max"]
                print(f"[✓] قیمت سقف روزانه به صورت خودکار اعمال شد: {final_price}")
            else:
                print("[!] سقف قیمت از candle خوانده نشد؛ روی مقدار دستی یا پیش‌فرض حساب می‌شود.")

        # نمایش وضعیت مظنه قبل از سفارش
        depth = await self.get_market_depth_summary()
        if depth["total_buy_volume"]:
            print(f"[*] وضعیت فعلی صف خرید: حجم={depth['total_buy_volume']} | تعداد={depth['total_buy_count']}")

        # کلیک روی دکمه خرید یا فروش برای باز کردن فرم
        order_btn_selector = "button[data-cy='order-buy-btn']" if self.config.order.side == "buy" else "button[data-cy='order-sell-btn']"
        print(f"[*] کلیک روی دکمه {self.config.order.side} ({order_btn_selector})...")
        await self.human_click(order_btn_selector)

        # پر کردن حجم سفارش
        quantity_selector = "[data-cy='order-volume-input'], input[name='volume'], input[placeholder*='حجم']"
        try:
            await self.human_type(quantity_selector, str(self.config.order.quantity))
            print(f"[✓] حجم سفارش وارد شد: {self.config.order.quantity}")
        except Exception as e:
            print(f"[!] فیلد حجم سفارش یافت نشد: {e}")

        # پر کردن قیمت سفارش
        if final_price > 0:
            price_selector = "[data-cy='order-price-input'], input[name='price'], input[placeholder*='قیمت']"
            try:
                await self.human_type(price_selector, str(final_price))
                print(f"[✓] قیمت سفارش وارد شد: {final_price}")
            except Exception as e:
                print(f"[!] فیلد قیمت سفارش یافت نشد: {e}")

        print("[✓] فرم سفارش با موفقیت تنظیم شد و آماده شلیک در زمان موعود است.")

    async def execute_order_burst(self):
        """ارسال سفارش با کلیک بر روی دکمه ارسال سفارش"""
        # دکمه ارسال نهایی در پنجره/پنل خرید ایزیتریدر
        submit_selectors = [
            "[data-cy='order-submit-btn']",
            "[data-cy='order-send-btn']",
            "button[type='submit'].order-buy-btn",
            "button[data-cy='order-buy-btn']"
        ]
        
        print(f"[*] شلیک سفارش به هسته معاملات (حداکثر تلاش: {self.config.schedule.max_attempts})...")

        for attempt in range(1, self.config.schedule.max_attempts + 1):
            clicked = False
            for sel in submit_selectors:
                try:
                    btn = await self.page.query_selector(sel)
                    if btn and await btn.is_visible():
                        await btn.click()
                        print(f"[✓] شلیک #{attempt} روی سلکتور '{sel}' انجام شد.")
                        clicked = True
                        break
                except Exception as e:
                    print(f"[!] خطا در کلیک سلکتور {sel}: {e}")

            if not clicked:
                print(f"[!] هیچ دکمه ارسال فعالی در تلاش #{attempt} یافت نشد.")

            if attempt < self.config.schedule.max_attempts:
                await asyncio.sleep(self.config.schedule.interval_ms / 1000.0)
