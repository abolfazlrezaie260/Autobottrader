import os
import shutil

# Ensure PLAYWRIGHT_NODEJS_PATH points to system Node.js on macOS
if "PLAYWRIGHT_NODEJS_PATH" not in os.environ:
    candidate_node_paths = [
        shutil.which("node"),
        "/opt/homebrew/bin/node",
        "/usr/local/bin/node",
    ]
    for np in candidate_node_paths:
        if np and os.path.exists(np):
            os.environ["PLAYWRIGHT_NODEJS_PATH"] = np
            break

import json
import random
import asyncio
from typing import Optional
from playwright.async_api import async_playwright, BrowserContext, Page
from config import Config

SESSION_STATE_FILE = "session_state.json"

# Stealth script to evade bot detection (Anti-Fingerprinting)
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});

// Mock languages and Chrome runtime object
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
    """Find installed Google Chrome or Chromium browser executable on macOS"""
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

    async def _launch_persistent(self) -> BrowserContext:
        """Launch system Chrome directly with persistent user directory and saved session state"""
        profile_dir = os.path.abspath(self.config.app.user_data_dir)
        os.makedirs(profile_dir, exist_ok=True)
        print(f"[+] Launching browser with persistent profile at: {profile_dir}")

        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars",
            "--start-maximized"
        ]

        chrome_exec = find_system_chrome()
        launch_kwargs = {
            "user_data_dir": profile_dir,
            "headless": self.config.app.headless,
            "args": args,
            "viewport": None,
            "ignore_default_args": ["--enable-automation"]
        }

        # Restore saved cookies and localStorage tokens if available
        if os.path.exists(SESSION_STATE_FILE):
            print(f"[✓] Loading saved session tokens from '{SESSION_STATE_FILE}'")
            launch_kwargs["storage_state"] = SESSION_STATE_FILE

        if chrome_exec:
            print(f"[✓] Auto-detected installed system browser: {chrome_exec}")
            launch_kwargs["executable_path"] = chrome_exec
        else:
            launch_kwargs["channel"] = "chrome"

        return await self.playwright.chromium.launch_persistent_context(**launch_kwargs)

    async def initialize(self) -> Page:
        """Initialize browser with persistent context or connect over CDP with automatic fallback"""
        self.playwright = await async_playwright().start()

        if self.config.app.connection_mode == "cdp":
            print(f"[+] Connecting to existing browser over CDP: {self.config.app.cdp_endpoint}")
            try:
                browser = await self.playwright.chromium.connect_over_cdp(self.config.app.cdp_endpoint)
                self.context = browser.contexts[0] if browser.contexts else await browser.new_context()
                self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
            except Exception as e:
                print(f"[!] CDP connection refused on {self.config.app.cdp_endpoint} ({e})")
                print("[*] Chrome with --remote-debugging-port=9222 was not running.")
                print("[*] Automatically launching system Chrome directly...")
                self.context = await self._launch_persistent()
                self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        else:
            self.context = await self._launch_persistent()
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

        # Inject stealth evasions into page
        await self.page.add_init_script(STEALTH_JS)
        return self.page

    async def close(self):
        if self.context:
            try:
                # Save latest state before closing
                await self.context.storage_state(path=SESSION_STATE_FILE)
            except Exception:
                pass
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
