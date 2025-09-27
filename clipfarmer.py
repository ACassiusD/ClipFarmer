#!/usr/bin/env python3

import argparse
import asyncio
import json
import os
import random
import sys
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
from rich import print as rprint
from playwright.async_api import async_playwright, BrowserContext, Page


INSTAGRAM_BASE = "https://www.instagram.com"
REELS_EXPLORE_URL = f"{INSTAGRAM_BASE}/explore/reels/"
LOGIN_URL = f"{INSTAGRAM_BASE}/accounts/login/"

YOUTUBE_BASE = "https://www.youtube.com"
YOUTUBE_SHORTS_URL = f"{YOUTUBE_BASE}/shorts"


async def ensure_login(page: Page, username: str | None, password: str | None, verbose: bool = False) -> None:
    if verbose:
        rprint("[cyan]Navigating to Instagram login page...[/cyan]")
    await page.goto(LOGIN_URL, wait_until="domcontentloaded")
    try:
        # If already logged in, redirect may happen; check for login form first
        if await page.locator("input[name='username']").count() == 0:
            if verbose:
                rprint("[cyan]Login form not present, likely already logged in.[/cyan]")
            return
        if not username or not password:
            rprint("[yellow]No credentials provided; proceeding without login.[/yellow]")
            return
        if verbose:
            rprint("[cyan]Filling credentials...[/cyan]")
        await page.fill("input[name='username']", username)
        await page.fill("input[name='password']", password)
        await page.click("button[type='submit']")
        await page.wait_for_timeout(3000)
        # Handle possible dialogs
        dismiss_selectors = [
            "button:has-text('Not Now')",
            "button:has-text('Save Info')",
            "button:has-text('Allow all')",
        ]
        for sel in dismiss_selectors:
            if await page.locator(sel).count() > 0:
                if verbose:
                    rprint(f"[cyan]Dismissing dialog via selector: {sel}[/cyan]")
                await page.click(sel)
                await page.wait_for_timeout(1000)
    except Exception as exc:
        rprint(f"[yellow]Login step encountered an issue: {exc}[/yellow]")


async def collect_reel_urls(page: Page, target_count: int, verbose: bool = False) -> list[str]:
    if verbose:
        rprint("[cyan]Opening Explore/Reels feed...[/cyan]")
    await page.goto(REELS_EXPLORE_URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)

    collected: set[str] = set()
    seen_anchors: set[str] = set()

    max_scrolls = max(10, target_count * 3)
    for idx in range(max_scrolls):
        anchors = await page.eval_on_selector_all(
            "a",
            "elements => elements.map(a => a.href).filter(h => h && (h.includes('/reel/') || h.includes('/p/')))",
        )
        for href in anchors:
            # Normalize and keep only instagram links
            if not href or not href.startswith(INSTAGRAM_BASE):
                continue
            # Prefer /reel/ form; accept /p/ as some reels surface as posts
            if "/reel/" in href or "/p/" in href:
                if href not in seen_anchors:
                    seen_anchors.add(href)
                    collected.add(href.split("?", 1)[0].rstrip("/"))
        if verbose:
            rprint(f"[cyan]Scroll {idx+1}/{max_scrolls}: collected so far {len(collected)}[/cyan]")
        if len(collected) >= target_count * 2:
            break

        await page.mouse.wheel(0, 2000)
        await page.wait_for_timeout(1500 + random.randint(0, 1000))

    urls = list(collected)
    random.shuffle(urls)
    if verbose:
        rprint(f"[cyan]Picked {min(target_count, len(urls))} random reel URLs.[/cyan]")
    return urls[:target_count]


async def extract_thumbnail_from_current_page(page: Page) -> str | None:
    # Try twitter:image first, then og:image
    selectors = [
        "meta[name='twitter:image']",
        "meta[property='og:image']",
    ]
    for sel in selectors:
        try:
            content = await page.locator(sel).get_attribute("content")
            if content:
                return content.replace("&amp;", "&")
        except Exception:
            continue
    return None


async def enrich_with_thumbnails(page: Page, urls: list[str], verbose: bool = False) -> list[dict]:
    items: list[dict] = []
    for i, url in enumerate(urls, 1):
        thumbnail: str | None = None
        try:
            if verbose:
                rprint(f"[cyan]({i}/{len(urls)}) Opening post to extract thumbnail: {url}[/cyan]")
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(800)
            thumbnail = await extract_thumbnail_from_current_page(page)
        except Exception as exc:
            rprint(f"[yellow]Failed to extract thumbnail for {url}: {exc}[/yellow]")
        items.append({"url": url, "thumbnail": thumbnail})
    return items


async def accept_youtube_consent(page: Page, verbose: bool = False) -> None:
    # Handle various consent dialog variants
    selectors = [
        "button:has-text('I agree')",
        "button:has-text('Accept all')",
        "#introAgreeButton",
        "tp-yt-paper-button:has-text('I agree')",
    ]
    for sel in selectors:
        try:
            if await page.locator(sel).count() > 0:
                if verbose:
                    rprint(f"[cyan]Accepting YouTube consent dialog via: {sel}[/cyan]")
                await page.click(sel, timeout=2000)
                await page.wait_for_timeout(1000)
                break
        except Exception:
            continue


async def collect_youtube_shorts_urls(page: Page, target_count: int, verbose: bool = False) -> list[str]:
    if verbose:
        rprint("[cyan]Opening YouTube Shorts feed...[/cyan]")
    await page.goto(YOUTUBE_SHORTS_URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)
    await accept_youtube_consent(page, verbose=verbose)

    collected: set[str] = set()
    seen: set[str] = set()
    max_scrolls = max(12, target_count * 6)

    for idx in range(max_scrolls):
        anchors = await page.eval_on_selector_all(
            "a",
            "elements => elements.map(a => a.getAttribute('href')).filter(h => h && h.includes('/shorts/'))",
        )
        for href in anchors:
            if not href:
                continue
            url = href
            if href.startswith("/shorts/"):
                url = f"{YOUTUBE_BASE}{href}"
            if "/shorts/" in url:
                if url not in seen:
                    seen.add(url)
                    collected.add(url.split("?", 1)[0].rstrip("/"))
        if verbose:
            rprint(f"[cyan]Scroll {idx+1}/{max_scrolls}: collected so far {len(collected)}[/cyan]")
        if len(collected) >= target_count * 2:
            break
        await page.mouse.wheel(0, 2500)
        await page.wait_for_timeout(1200 + random.randint(0, 800))

    urls = list(collected)
    random.shuffle(urls)
    if verbose:
        rprint(f"[cyan]Picked {min(target_count, len(urls))} random Shorts URLs.[/cyan]")
    return urls[:target_count]


def _load_existing_urls_from_jsonl(path: Path) -> set[str]:
    existing: set[str] = set()
    if not path.exists():
        return existing
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    data = obj.get("data") if isinstance(obj, dict) else None
                    urls = []
                    if isinstance(data, dict):
                        if isinstance(data.get("urls"), list):
                            urls.extend([u for u in data["urls"] if isinstance(u, str)])
                        # Also scan items array for url fields
                        items = data.get("items")
                        if isinstance(items, list):
                            for it in items:
                                if isinstance(it, dict) and isinstance(it.get("url"), str):
                                    urls.append(it["url"])
                    # Fallback: top-level urls if older format
                    elif isinstance(obj, dict) and isinstance(obj.get("urls"), list):
                        urls.extend([u for u in obj["urls"] if isinstance(u, str)])
                    for u in urls:
                        existing.add(u)
                except Exception:
                    continue
    except Exception:
        return existing
    return existing


def append_jsonl_unique(platform: str, urls: list[str], items: list[dict] | None, log_path: Path, verbose: bool = False) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    existing = _load_existing_urls_from_jsonl(log_path)
    new_urls = [u for u in urls if u not in existing]
    if not new_urls:
        if verbose:
            rprint(f"[yellow]No new {platform} URLs to append; skipping log write.[/yellow]")
        return
    new_items: list[dict] | None = None
    if items:
        keep = set(new_urls)
        new_items = [it for it in items if isinstance(it, dict) and it.get("url") in keep]
    envelope = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "data": {
            "platform": platform,
            "count": len(new_urls),
            "urls": new_urls,
            **({"items": new_items} if new_items is not None else {}),
        },
    }
    try:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(envelope, ensure_ascii=False) + "\n")
        if verbose:
            rprint(f"[green]Appended {len(new_urls)} new {platform} URLs to {log_path}[/green]")
    except Exception as exc:
        rprint(f"[yellow]Failed to append to log {log_path}: {exc}[/yellow]")


async def run_instagram(count: int, out_path: str | None, persistent_dir: str | None, headful: bool, slowmo: int, verbose: bool) -> int:
    load_dotenv()

    username = os.getenv("IG_USERNAME")
    password = os.getenv("IG_PASSWORD")

    async with async_playwright() as p:
        if persistent_dir:
            if verbose:
                rprint("[cyan]Launching persistent Chromium context for Instagram...[/cyan]")
            context: BrowserContext = await p.chromium.launch_persistent_context(
                user_data_dir=persistent_dir,
                headless=not headful,
                slow_mo=slowmo if slowmo > 0 else None,
                args=["--disable-blink-features=AutomationControlled"],
            )
        else:
            if verbose:
                rprint("[cyan]Launching Chromium for Instagram...[/cyan]")
            browser = await p.chromium.launch(
                headless=not headful,
                slow_mo=slowmo if slowmo > 0 else None,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context()
            await context.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                """
            )
        page = await context.new_page()
        await ensure_login(page, username, password, verbose=verbose)
        urls = await collect_reel_urls(page, count, verbose=verbose)
        items = await enrich_with_thumbnails(page, urls, verbose=verbose)

        # Full output to stdout and file (including thumbnails)
        full_result = {"platform": "instagram", "count": len(urls), "urls": urls, "items": items}
        output = json.dumps(full_result, ensure_ascii=False, indent=2)
        print(output)

        # Default to outputs/instagram_reels.json if no --out provided
        if out_path is None:
            out_path = str((Path(__file__).resolve().parent / "outputs" / "instagram_reels.json"))
        out_path_path = Path(out_path)
        out_path_path.parent.mkdir(parents=True, exist_ok=True)
        out_path_path.write_text(output, encoding="utf-8")
        rprint(f"[green]Saved to {out_path}[/green]")

        # Append to log with de-duplication
        append_jsonl_unique(
            platform="instagram",
            urls=urls,
            items=items,
            log_path=Path(__file__).resolve().parent / "logs" / "instagram.jsonl",
            verbose=verbose,
        )

        await context.close()
    return 0


async def run_youtube_shorts(count: int, out_path: str | None, headful: bool, slowmo: int, verbose: bool) -> int:
    async with async_playwright() as p:
        if verbose:
            rprint("[cyan]Launching Chromium for YouTube Shorts...[/cyan]")
        browser = await p.chromium.launch(headless=not headful, slow_mo=slowmo if slowmo > 0 else None)
        context = await browser.new_context()
        page = await context.new_page()
        urls = await collect_youtube_shorts_urls(page, count, verbose=verbose)
        result = {"platform": "youtube", "count": len(urls), "urls": urls}
        output = json.dumps(result, ensure_ascii=False, indent=2)
        print(output)
        # Default to outputs/youtube.json if no --out provided
        if out_path is None:
            out_path = str((Path(__file__).resolve().parent / "outputs" / "youtube.json"))
        out_path_path = Path(out_path)
        out_path_path.parent.mkdir(parents=True, exist_ok=True)
        out_path_path.write_text(output, encoding="utf-8")
        rprint(f"[green]Saved to {out_path}[/green]")

        # Append to log with de-duplication
        append_jsonl_unique(
            platform="youtube",
            urls=urls,
            items=None,
            log_path=Path(__file__).resolve().parent / "logs" / "youtube.jsonl",
            verbose=verbose,
        )

        await context.close()
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect random Instagram Reels or YouTube Shorts URLs")
    # Global visibility/debug flags
    parser.add_argument("--headful", action="store_true", help="Run browser with UI visible")
    parser.add_argument("--slowmo", type=int, default=0, help="Slow down actions by N ms (e.g., 250)")
    parser.add_argument("--verbose", action="store_true", help="Print progress logs")

    subparsers = parser.add_subparsers(dest="command")

    reels_parser = subparsers.add_parser("reels", help="Collect Instagram Reels")
    reels_parser.add_argument("--count", type=int, default=10, help="Number of reels to collect")
    reels_parser.add_argument("--out", type=str, default=None, help="Optional output JSON file path")
    reels_parser.add_argument("--persistent", type=str, default=None, help="Persistent user data dir")

    shorts_parser = subparsers.add_parser("shorts", help="Collect YouTube Shorts")
    shorts_parser.add_argument("--count", type=int, default=5, help="Number of shorts to collect")
    shorts_parser.add_argument("--out", type=str, default=None, help="Optional output JSON file path")

    # Backwards compatibility: if no subcommand provided, assume reels
    parser.add_argument("--count", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--out", type=str, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--persistent", type=str, default=None, help=argparse.SUPPRESS)

    args = parser.parse_args()
    if args.command is None:
        # Map top-level flags to reels defaults
        args.command = "reels"
        if getattr(args, "count") is None:
            args.count = 10
    return args


if __name__ == "__main__":
    args = parse_args()
    try:
        if args.command == "reels":
            code = asyncio.run(
                run_instagram(args.count, args.out, getattr(args, "persistent", None), args.headful, args.slowmo, args.verbose)
            )
        elif args.command == "shorts":
            code = asyncio.run(
                run_youtube_shorts(args.count, args.out, args.headful, args.slowmo, args.verbose)
            )
        else:
            rprint("[red]Unknown command[/red]")
            code = 2
        sys.exit(code)
    except KeyboardInterrupt:
        sys.exit(130)
