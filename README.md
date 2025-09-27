## ClipFarmer: Instagram Reels URL Collector

Collect 10 random Instagram Reels URLs using a headless browser (Playwright).

### Features
- Uses Playwright Chromium to open Instagram Explore/Reels
- Supports login via environment variables or `.env`
- Scrolls and samples 10 unique Reel permalinks
- Outputs JSON to stdout and optionally saves to a file
- New: Fetch 5 random YouTube Shorts URLs

### Legal & Ethical Note
Use only on content you are permitted to access. Respect Instagram's and YouTube's Terms of Use and robots directives. This tool automates a standard web browser; heavy scraping can trigger rate limits or account restrictions.

### Requirements
- Python 3.10+
- Playwright browsers installed

### Setup

1) Create and activate a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

2) Install dependencies
```bash
pip install -r requirements.txt
python -m playwright install chromium
```

3) Create a `.env` file (optional if passing env vars directly)
```bash
echo 'IG_USERNAME=your_username' >> .env
echo 'IG_PASSWORD=your_password' >> .env
```

### Usage

Instagram Reels (default command):
```bash
python clipfarmer.py reels --count 10
```

Back-compat (reels without subcommand):
```bash
python clipfarmer.py --count 10
```

YouTube Shorts:
```bash
python clipfarmer.py shorts --count 5
```

Save output to a file:
```bash
python clipfarmer.py reels --count 10 --out reels.json
python clipfarmer.py shorts --count 5 --out shorts.json
```

Persistent login for Instagram:
```bash
python clipfarmer.py reels --count 10 --persistent ./ig_profile
```

### See what's going on (debug/visibility)
Use global flags to watch the browser and print progress:
- `--headful`: show the browser UI
- `--verbose`: print step-by-step logs
- `--slowmo N`: delay each action by N ms (e.g., 250)

Examples:
```bash
# Instagram with visible browser, verbose logs, and 250ms slow-mo
python clipfarmer.py --headful --verbose --slowmo 250 reels --count 10

# YouTube Shorts with visible browser and logs
python clipfarmer.py --headful --verbose shorts --count 5
```

### Notes
- First Instagram run may prompt for checkpoint/2FA; use `--persistent` to reuse the session afterward.
- If IG login fails, the script will still try public explore but results may be fewer.
- Randomness is achieved by overscrolling the feeds, shuffling, and sampling.

### Example
To fetch the example reel shared:
- Example Instagram post: [`https://www.instagram.com/p/DLdBvC9umKl`](https://www.instagram.com/p/DLdBvC9umKl)

This script gathers similar `reel/` permalinks from Explore/Reels.
