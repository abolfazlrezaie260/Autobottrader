import asyncio
import sys
from config import Config
from browser import BrowserManager
from scheduler import PrecisionScheduler
from trader import EasyTraderAutomation

async def main():
    print("=" * 60)
    print("      Autobottrader - ربات خودکارساز معاملات ایزیتریدر مفید      ")
    print("=" * 60)

    try:
        config = Config("config.yaml")
    except Exception as e:
        print(f"[x] خطا در بارگذاری پیکربندی: {e}")
        sys.exit(1)

    browser_mgr = BrowserManager(config)
    try:
        page = await browser_mgr.initialize()
        trader = EasyTraderAutomation(page, config)

        # مرحله اول: اطمینان از لاگین بودن کاربر
        await trader.wait_for_login()

        # مرحله دوم: آماده‌سازی اولیه سفارش (ورود نماد، حجم و قیمت)
        await trader.prepare_order()

        # مرحله سوم: در صورت فعال بودن زمان‌بندی، انتظار تا زمان دقیق سرور
        if config.schedule.enabled:
            await PrecisionScheduler.wait_until(config.schedule.target_time)

        # مرحله چهارم: شلیک و ارسال سفارش
        await trader.execute_order_burst()

        print("\n[✓] عملیات با موفقیت به پایان رسید.")
        print("[*] برای بررسی وضعیت سفارش، مرورگر باز می‌ماند (برای خروج Ctrl+C بزنید)...")
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n[!] توقف برنامه توسط کاربر.")
    except Exception as e:
        print(f"\n[x] خطای پیش‌بینی نشده: {e}")
    finally:
        await browser_mgr.close()

if __name__ == "__main__":
    asyncio.run(main())
