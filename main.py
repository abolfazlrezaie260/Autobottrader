import asyncio
import sys
from config import Config
from browser import BrowserManager
from scheduler import PrecisionScheduler
from trader import EasyTraderAutomation

async def main():
    print("=" * 60)
    print("      Autobottrader - Mofid EasyTrader Automation Bot      ")
    print("=" * 60)

    try:
        config = Config("config.yaml")
    except Exception as e:
        print(f"[X] Error loading configuration: {e}")
        sys.exit(1)

    browser_mgr = BrowserManager(config)
    try:
        page = await browser_mgr.initialize()
        trader = EasyTraderAutomation(page, config)

        # Step 1: Ensure user is authenticated
        await trader.wait_for_login()

        # Step 2: Prepare order (symbol check, quantity, price)
        await trader.prepare_order()

        # Step 3: Wait for scheduled execution time if enabled
        if config.schedule.enabled:
            await PrecisionScheduler.wait_until(config.schedule.target_time)

        # Step 4: Fire burst order submission
        await trader.execute_order_burst()

        print("\n[✓] Automation completed successfully.")
        print("[*] Browser will remain open to monitor order status (Press Ctrl+C to exit)...")
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n[!] Execution stopped by user.")
    except Exception as e:
        print(f"\n[X] Unexpected error: {e}")
    finally:
        await browser_mgr.close()

if __name__ == "__main__":
    asyncio.run(main())
