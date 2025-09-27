import asyncio
import json
from pathlib import Path
from playwright.async_api import Playwright, async_playwright

# Starting URL for the Shorts viewer (customize if needed)
START_URL = "https://www.youtube.com/shorts/hhoIPjrZeVs"


async def wait_url_change(page, prev: str, timeout_ms: int = 4000) -> bool:
    try:
        await page.wait_for_function("prev => location.href !== prev", prev, timeout=timeout_ms)
        return True
    except Exception:
        return False


async def run(playwright: Playwright) -> None:
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(START_URL)

    # Ensure we're in the Shorts viewer
    try:
        await page.wait_for_url("**/shorts/**", timeout=5000)
    except Exception:
        pass

    # Ensure focus
    try:
        await page.focus("body")
    except Exception:
        pass

    target_count = 50
    collected = set()
    attempts = 0

    while len(collected) < target_count and attempts < 500:
        cur = page.url
        if "/shorts/" in cur and cur not in collected:
            print(cur)
            collected.add(cur)
            await asyncio.sleep(0.4)
            if len(collected) >= target_count:
                break

        prev = page.url
        advanced = False

        # 1) Try ArrowDown
        try:
            await page.keyboard.press("ArrowDown")
            if await wait_url_change(page, prev, timeout_ms=2500):
                advanced = True
        except Exception:
            pass

        # 2) Try mouse wheel if needed
        if not advanced:
            try:
                await page.mouse.wheel(0, 4000)
                if await wait_url_change(page, prev, timeout_ms=2000):
                    advanced = True
            except Exception:
                pass

        # 3) Fallback: click another shorts link
        if not advanced:
            try:
                hrefs = await page.eval_on_selector_all(
                    "a[href^='/shorts/']",
                    "els => els.map(a => a.getAttribute('href')).filter(Boolean)"
                )
                next_url = None
                for href in hrefs:
                    full = f"https://www.youtube.com{href.split('?', 1)[0].rstrip('/')}"
                    if full not in collected:
                        next_url = full
                        break
                if next_url:
                    await page.goto(next_url)
                    await page.wait_for_url("**/shorts/**", timeout=4000)
                    advanced = True
            except Exception:
                pass

        attempts += 1
        await asyncio.sleep(0.3)

    # Append/merge into youtube.json in project root
    out_path = Path(__file__).resolve().parent / "youtube.json"
    merged_urls = []
    seen = set()

    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and isinstance(existing.get("urls"), list):
                for u in existing["urls"]:
                    if isinstance(u, str) and u not in seen:
                        seen.add(u)
                        merged_urls.append(u)
        except Exception:
            # If file is corrupt or different format, ignore and rebuild
            pass

    # Add new ones, preserving previous order
    for u in collected:
        if u not in seen:
            seen.add(u)
            merged_urls.append(u)

    data = {"platform": "youtube", "count": len(merged_urls), "urls": merged_urls}
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved total {len(merged_urls)} URLs to {out_path}")

    # Keep the browser visible briefly before closing
    await asyncio.sleep(2)
    await page.close()

    # ---------------------
    await context.close()
    await browser.close()


async def main() -> None:
    async with async_playwright() as playwright:
        await run(playwright)


asyncio.run(main())
