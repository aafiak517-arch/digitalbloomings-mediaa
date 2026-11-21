# Digital Bloomings Kids: media tools

Tools for the Digital Bloomings Kids & Parenting content workflow.

## Daily content kit (`contentkit`)

Builds the day's 5 reels (2 promotional, 3 educational) from your product
catalog, with voiceover scripts, subtitles, visual notes, and a separate
caption, title and hashtag set for Instagram, TikTok, Facebook, YouTube Shorts
and Pinterest.

It only plans and writes content. It does not upload or schedule anything.

### Setup

Python 3.10+ with no extra packages. `pytest` is needed only for tests.

1. Copy `examples/products.sample.json` to `products.json`.
2. Replace every `your-store` link with the exact Gumroad URL of the real
   product. The tool refuses placeholder or non-Gumroad links, so a promo can
   never go out with a made-up URL.
3. List 3 or 4 real page exports from each PDF under `preview_files`. Products
   without them are flagged in the kit, because promos must show the actual
   product.
4. Add `price` only if you want it in captions, written exactly as it is on
   Gumroad (for example `"$4.99"`).

Seasonal products take a `season` window as `MM-DD` dates. Windows repeat every
year and can wrap New Year (`"start": "12-20", "end": "01-10"`).

### Run

```bash
python -m contentkit --catalog products.json --record
python -m contentkit --catalog products.json --date 2026-11-24 --out kits
```

This writes `kits/<date>.md` (the work sheet) and `kits/<date>.json` (the same
data for automation). `--record` saves the picks to `kits/history.json` so the
next day rotates to different products, angles and topics.

### How reels are picked

- **Promos:** two different products a day. Products inside their selling
  window come first, the one closest to its end date first, then the least
  recently promoted ones. Each product works through 6 angles (what you get,
  screen-free hour, zero prep, classroom ready, skills, seasonal countdown)
  before any angle repeats, and the two promos on one day never share an angle.
- **Educational:** 15 topics on phonics, early math, fine motor skills,
  routines and parenting, rotated least recently used first. Each lists Mixkit
  search terms for free-license clips.
- **Length:** every script is checked to run under 15 seconds at an upbeat
  voiceover pace (about 160 words a minute plus a 1.5 second end card), with a
  hook of 8 words or fewer for the first 2 seconds.

### Tests

```bash
python -m pytest
```
