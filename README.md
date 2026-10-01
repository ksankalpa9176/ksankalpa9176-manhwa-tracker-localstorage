# Manhwa Tracker

Static site (GitHub Pages) with a light/dark UI, a personal reading list, and an automatic chapter scraper for arenascan.com.

## How it works

* **Automatic Local Saving:** Your reading progress (chapters read, custom edits, dismissed titles) saves automatically in your browser's local storage.
* **Export & Import Backups:** Use the **Export** button to download a local `reading.json` backup of your list, or **Import** to restore or transfer your list to another browser/device.
* **New Titles:** Discovers new series with fewer than 10 chapters. Tracking a new title moves it directly into your personal reading list.

## Files

* `reading.json`: The default starter list for new visitors who don't have local browser data saved yet.
* `releases.json`: Written automatically by the scraper. Contains the latest chapter info for tracked titles.
* `new-titles.json`: Written automatically by the scraper. Lists newly discovered series with fewer than 10 chapters.
* `scraper.py`: `python scraper.py [pages]`. Scrapes latest releases and runs every 4 hours via `.github/workflows/scraper.yml`.

## Deployment

1. **GitHub Actions Permissions:** Go to **Settings > Actions > General > Workflow permissions** and select **Read and write permissions**.
2. **GitHub Pages:** Go to **Settings > Pages** and set source to **Deploy from a branch** (`main` / `root`).
