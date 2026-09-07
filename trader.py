import random
import asyncio
from playwright.async_api import Page
from config import Config

class EasyTraderAutomation:
    """کلاس مدیریت تعاملات و ارسال سفارش در ایزیتریدر مفید"""
    def __init__(self, page: Page, config: Config):
        self.page = page
        self.config = config

    async def human_delay(self):
        """ایجاد تاخیر تصادفی بین اقدامات برای شبیه‌سازی رفتار طبیعی کاربر"""
        delay_ms = random.randint(
            self.config.anti_detection.random_delay_min_ms,
            self.config.anti_detection.random_delay_max_ms
        )
        await asyncio.sleep(delay_ms / 1000.0)

    async def human_click(self, selector: str):
        """حرکت ماوس با انحراف و کلیک انسانی"""
        elem = await self.page.wait_for_selector(selector, timeout=10000)
        box = await elem.bounding_box()
        if box and self.config.anti_detection.human_mouse_movement:
            # کلیک در نقطه‌ای تصادفی داخل ابعاد المان
            offset_x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
            offset_y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
            await self.page.mouse.move(offset_x, offset_y, steps=random.randint(5, 12))
            await self.human_delay()
            await self.page.mouse.click(offset_x, offset_y)
        else:
            await elem.click()

    async def human_type(self, selector: str, text: str):
        """تایپ مقادیر با تاخیرهای متغیر بین کلیدها"""
        elem = await self.page.wait_for_selector(selector, timeout=10000)
        await elem.click()
        await self.human_delay()
        # پاک کردن محتوای قبلی فیلد
        await self.page.keyboard.press("Control+A")
        await self.page.keyboard.press("Backspace")
        
        for char in str(text):
            await self.page.keyboard.type(char, delay=random.randint(40, 110))
        await self.human_delay()

    async def wait_for_login(self):
        """بررسی لاگین بودن کاربر و در صورت نیاز انتظار برای ورود دستی کاربر"""
        print("[*] در حال باز کردن صفحه ایزیتریدر...")
        await self.page.goto(self.config.app.url, wait_until="domcontentloaded")
        
        print("[*] بررسی وضعیت احراز هویت و ورود کاربر...")
        logged_in_selectors = [
            "[data-cy='user-profile-btn']",
            "[data-cy='order-buy-btn']",
            ".user-menu",
            "app-header"
        ]
        
        is_logged_in = False
        for _ in range(5):
            for sel in logged_in_selectors:
                if await self.page.query_selector(sel):
                    is_logged_in = True
                    break
            if is_logged_in:
                break
            await asyncio.sleep(1)

        if not is_logged_in:
            print("=" * 60)
            print("[!] کاربر هنوز وارد نشده است.")
            print("[!] لطفاً نام کاربری، رمز عبور و کد یکبار مصرف (2FA) را در مرورگر باز شده وارد نمایید.")
            print("[!] پس از ورود کامل و لود شدن داشبورد، برنامه به صورت خودکار ادامه خواهد یافت.")
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

    async def prepare_order(self):
        """آماده‌سازی فرم سفارش (انتخاب نماد، درج حجم و قیمت) پیش از لحظه ارسال"""
        symbol = self.config.order.symbol
        print(f"[*] در حال آماده‌سازی سفارش نماد: {symbol}")

        # ۱. جستجوی نماد
        search_selector = "[data-cy='quick-search-input'], input[placeholder*='جستجو']"
        try:
            search_input = await self.page.wait_for_selector(search_selector, timeout=7000)
            if search_input:
                await self.human_type(search_selector, symbol)
                await self.page.keyboard.press("Enter")
                await self.human_delay()
        except Exception as e:
            print(f"[!] جستجوی خودکار نماد با اخطار مواجه شد (ممکن است نماد از قبل باز باشد): {e}")

        # ۲. انتخاب تب خرید یا فروش
        side_btn = "[data-cy='order-buy-tab']" if self.config.order.side == "buy" else "[data-cy='order-sell-tab']"
        if await self.page.query_selector(side_btn):
            await self.human_click(side_btn)

        # ۳. وارد کردن حجم سفارش
        quantity_selector = "[data-cy='order-volume-input'], input[name='volume']"
        try:
            await self.human_type(quantity_selector, str(self.config.order.quantity))
        except Exception as e:
            print(f"[!] فیلد حجم سفارش یافت نشد: {e}")

        # ۴. تعیین قیمت (سقف قیمت روزانه یا قیمت عددی)
        if self.config.order.use_ceiling_price:
            ceiling_selector = "[data-cy='price-ceiling-btn'], .top-threshold"
            try:
                if await self.page.query_selector(ceiling_selector):
                    await self.human_click(ceiling_selector)
            except Exception:
                pass
        elif self.config.order.price > 0:
            price_selector = "[data-cy='order-price-input'], input[name='price']"
            await self.human_type(price_selector, str(self.config.order.price))

        print("[✓] فرم سفارش با موفقیت مقداردهی شد و آماده ارسال است.")

    async def execute_order_burst(self):
        """ارسال سفارش با کلیک بر روی دکمه خرید data-cy='order-buy-btn'"""
        buy_btn_selector = "[data-cy='order-buy-btn']"
        print(f"[*] شلیک سفارش به سامانه (تعداد ارسال: {self.config.schedule.max_attempts})...")

        for attempt in range(1, self.config.schedule.max_attempts + 1):
            try:
                btn = await self.page.query_selector(buy_btn_selector)
                if btn:
                    await btn.click()
                    print(f"[✓] درخواست خرید #{attempt} ارسال گردید.")
                else:
                    print(f"[!] سلکتور {buy_btn_selector} در این لحظه در دسترس نیست.")
            except Exception as e:
                print(f"[!] خطا در کلیک دکمه ارسال: {e}")
            
            if attempt < self.config.schedule.max_attempts:
                await asyncio.sleep(self.config.schedule.interval_ms / 1000.0)
