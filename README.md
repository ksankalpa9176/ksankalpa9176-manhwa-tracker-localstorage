# Manhwa Tracker

Static site (GitHub Pages) with a light/dark UI, a personal reading list and a scraper for arenascan.com.

## Files
- `reading.json`: your reading list plus dismissed new titles. **You own this file.** Use Export in the site, replace this file, commit.
- `releases.json`: written by the scraper. Latest chapter for the titles in `reading.json` only.
- `new-titles.json`: written by the scraper. New series with fewer than 10 chapters that are not in your reading list and not dismissed.
- `scraper.py`: `python scraper.py [pages]`. Runs every 4 hours via `.github/workflows/scraper.yml`.

## How it fits together
- Your progress (chapters read, edits, dismissed titles) autosaves in the browser. A static site cannot write to the repo, so the dot on Export means `reading.json` is out of date.
- Tracking a new title moves it from New titles into your reading list; the scraper drops it from `new-titles.json` on its next run.
- First visit on a device with no saved data loads `reading.json` as the starting list.

## Deploy
Settings > Actions > General > Workflow permissions: Read and write. Settings > Pages: `main` / root.
