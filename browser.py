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

// شبیه‌سازی زبان‌ها و سیستم‌عامل
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

KNOWN_CHROME_PATHS = [
    "/Applications/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    os.path.expanduser("~/Applications/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"),
]

def find_system_chrome() -> Optional[str]:
    """یافتن خودکار مسیر مرورگر کروم یا کرومیوم نصب‌شده روی مک"""
    for path in KNOWN_CHROME_PATHS:
        if os.path.exists(path):
            return path
    return None

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

            # بررسی وجود کروم سیستم برای بی‌نیازی از دانلود کرومیوم پلی‌رایت
            chrome_exec = find_system_chrome()
            launch_kwargs = {
                "user_data_dir": profile_dir,
                "headless": self.config.app.headless,
                "args": args,
                "viewport": None,
                "ignore_default_args": ["--enable-automation"]
            }

            if chrome_exec:
                print(f"[✓] استفاده خودکار از مرورگر نصب‌شده روی مک: {chrome_exec}")
                launch_kwargs["executable_path"] = chrome_exec
            else:
                launch_kwargs["channel"] = "chrome"

            self.context = await self.playwright.chromium.launch_persistent_context(**launch_kwargs)
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

        # اعمال اسکریپت Stealth روی صفحه
        await self.page.add_init_script(STEALTH_JS)
        return self.page

    async def close(self):
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
