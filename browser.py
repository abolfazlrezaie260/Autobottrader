import os
import random
import asyncio
from typing import Optional
from playwright.async_api import async_playwright, BrowserContext, Page
from config import Config

# اسکریپت خنثی‌سازی تشخیص خودکارسازی مرورگر (Anti-Fingerprinting / Stealth)
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});

// شبیه‌سازی پلاگین‌ها و زبان‌ها
Object.defineProperty(navigator, 'languages', {
    get: () => ['fa-IR', 'fa', 'en-US', 'en']
});

window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: {}
};
"""

class BrowserManager:
    def __init__(self, config: Config):
        self.config = config
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def initialize(self) -> Page:
        """راه‌اندازی مرورگر بر اساس پروفایل دائمی یا CDP جهت حفظ لاگین کاربر"""
        self.playwright = await async_playwright().start()

        if self.config.app.connection_mode == "cdp":
            print(f"[+] اتصال به مرورگر در حال اجرا از طریق CDP: {self.config.app.cdp_endpoint}")
            browser = await self.playwright.chromium.connect_over_cdp(self.config.app.cdp_endpoint)
            self.context = browser.contexts[0] if browser.contexts else await browser.new_context()
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        else:
            profile_dir = os.path.abspath(self.config.app.user_data_dir)
            os.makedirs(profile_dir, exist_ok=True)
            print(f"[+] راه‌اندازی مرورگر با پروفایل دائمی در: {profile_dir}")

            args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--start-maximized"
            ]

            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=self.config.app.headless,
                channel="chrome",  # در صورت وجود از گوگل کروم رسمی استفاده می‌کند
                args=args,
                viewport=None,
                ignore_default_args=["--enable-automation"]
            )
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

        # اعمال اسکریپت Stealth روی صفحه
        await self.page.add_init_script(STEALTH_JS)
        return self.page

    async def close(self):
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
