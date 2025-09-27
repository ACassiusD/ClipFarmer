import asyncio
import json
import random
from pathlib import Path
from playwright.async_api import Playwright, async_playwright

INSTAGRAM_BASE = "https://www.instagram.com"
START_URL = f"{INSTAGRAM_BASE}/explore/reels/"
TARGET_COUNT = 5


async def run(playwright: Playwright) -> None:
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    page = await context.new_page()

    await page.goto(START_URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(1500)

    collected = set()
    seen = set()

    time_budget_ms = max(15000, 600 * TARGET_COUNT)
    start = await page.evaluate("Date.now()")

    while len(collected) < TARGET_COUNT:
        anchors = await page.eval_on_selector_all(
            "a",
            "elements => elements.map(a => a.href).filter(h => h && (h.includes('/reel/') || h.includes('/p/')))",
        )
        for href in anchors:
            if not href or not href.startswith(INSTAGRAM_BASE):
                continue
            url = href.split("?", 1)[0].rstrip("/")
            if url not in seen:
                seen.add(url)
                collected.add(url)
                if len(collected) >= TARGET_COUNT:
                    break
        if len(collected) >= TARGET_COUNT:
            break

        await page.mouse.wheel(0, 2500)
        await page.wait_for_timeout(600 + random.randint(0, 400))

        now = await page.evaluate("Date.now()")
        if (now - start) > time_budget_ms:
            break

    urls = list(collected)
    random.shuffle(urls)

    # Append/merge into instagram_reels.json in project root
    out_path = Path(__file__).resolve().parent / "instagram_reels.json"
    merged_urls = []
    seen_out = set()

    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and isinstance(existing.get("urls"), list):
                for u in existing["urls"]:
                    if isinstance(u, str) and u not in seen_out:
                        seen_out.add(u)
                        merged_urls.append(u)
        except Exception:
            pass

    for u in urls:
        if u not in seen_out:
            seen_out.add(u)
            merged_urls.append(u)

    data = {"platform": "instagram", "count": len(merged_urls), "urls": merged_urls}
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved total {len(merged_urls)} URLs to {out_path}")

    await asyncio.sleep(1.5)
    await page.close()
    await context.close()
    await browser.close()


async def main() -> None:
    async with async_playwright() as playwright:
        await run(playwright)


asyncio.run(main())
