import json
from datetime import date
from pathlib import Path

import pytest

from contentkit.cli import main
from contentkit.planner import History, choose_angle, plan_day, record
from contentkit.platforms import PINTEREST_DESC_MAX, YOUTUBE_TITLE_MAX
from contentkit.products import CatalogError, load_catalog, parse_product
from contentkit.scripts import (MAX_REEL_SECONDS, PROMO_ANGLES, TOPICS,
                                build_educational, build_promo)

# Test-only store name; never shipped as a real link.
STORE = "https://teststore.gumroad.com/l/"


def raw(pid, **over):
    base = {
        "id": pid,
        "name": f"{pid.title()} Pack",
        "gumroad_url": STORE + pid,
        "ages": "3-5",
        "pages": 30,
        "highlights": ["Letter tracing practice", "Beginning sounds pictures"],
        "keywords": ["preschool printables"],
        "preview_files": ["p1.png", "p2.png"],
    }
    base.update(over)
    return base


def write_png(path, w, h):
    import struct, zlib
    path.parent.mkdir(parents=True, exist_ok=True)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    chunk = b"IHDR" + ihdr
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + chunk
                     + struct.pack(">I", zlib.crc32(chunk)))


def fake_gumroad(pages):
    """Fetcher stub: url -> (status, html) or an exception to raise."""
    def fetch(url):
        result = pages.get(url, (404, ""))
        if isinstance(result, Exception):
            raise result
        return result
    return fetch


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    # Every test gets live-looking Gumroad pages titled after the product id.
    def fetch(url):
        slug = url.rsplit("/", 1)[-1]
        return 200, f"<html><title>{slug.title()} Pack</title></html>"
    monkeypatch.setattr("contentkit.checks.http_fetch", fetch)


@pytest.fixture
def catalog(tmp_path):
    for name in ("p1.png", "p2.png"):
        write_png(tmp_path / name, 1275, 1650)
    data = {"products": [
        raw("abc"),
        raw("xmas", season={"start": "11-15", "end": "12-24"}),
        raw("turkey", season={"start": "11-01", "end": "11-26"}),
        raw("shapes"),
    ]}
    path = tmp_path / "products.json"
    path.write_text(json.dumps(data))
    return path


# ---- catalog validation -------------------------------------------------

@pytest.mark.parametrize("url", [
    "http://teststore.gumroad.com/l/abc",          # not https
    "https://gumroad.com/abc",                     # no /l/
    "https://etsy.com/l/abc",                      # wrong site
    "https://your-store.gumroad.com/l/abc",        # template placeholder
    "https://teststore.gumroad.com/l/example",     # placeholder slug
])
def test_rejects_bad_gumroad_urls(url):
    with pytest.raises(CatalogError):
        parse_product(raw("abc", gumroad_url=url))


def test_accepts_store_and_bare_gumroad_urls():
    assert parse_product(raw("abc")).gumroad_url == STORE + "abc"
    parse_product(raw("abc", gumroad_url="https://gumroad.com/l/abc"))


def test_requires_fields_and_unique_ids(tmp_path):
    with pytest.raises(CatalogError, match="highlights"):
        parse_product(raw("abc", highlights=[]))
    with pytest.raises(CatalogError, match="season"):
        parse_product(raw("abc", season={"start": "11-01"}))
    path = tmp_path / "c.json"
    path.write_text(json.dumps([raw("abc"), raw("abc")]))
    with pytest.raises(CatalogError, match="duplicate"):
        load_catalog(path)


def test_sample_catalog_is_rejected_until_links_are_real():
    sample = Path(__file__).parent.parent / "examples" / "products.sample.json"
    with pytest.raises(CatalogError, match="placeholder"):
        load_catalog(sample)


def test_season_window_wraps_new_year():
    p = parse_product(raw("ny", season={"start": "12-20", "end": "01-10"}))
    assert p.in_season(date(2026, 12, 25))
    assert p.in_season(date(2027, 1, 5))
    assert not p.in_season(date(2026, 11, 21))
    assert p.days_left_in_season(date(2026, 12, 25)) == 16


# ---- scripts ------------------------------------------------------------

def test_every_angle_and_topic_fits_under_15_seconds():
    long_p = parse_product(raw("long", name="Ultimate Preschool Learning Bundle",
                               highlights=["Over two hundred tracing and phonics pages",
                                           "Counting, shapes, colors and fine motor practice"],
                               season={"start": "01-01", "end": "12-31"}))
    for angle in PROMO_ANGLES:
        s = build_promo(long_p, angle, date(2026, 11, 21))
        assert s.est_seconds < MAX_REEL_SECONDS, (angle, s.voiceover)
        assert len(s.hook.split()) <= 8
        assert s.link == long_p.gumroad_url
        assert long_p.gumroad_url in s.on_screen_text
    for topic in TOPICS:
        assert build_educational(topic).est_seconds < MAX_REEL_SECONDS, topic.id


def test_topic_ids_unique():
    ids = [t.id for t in TOPICS]
    assert len(ids) == len(set(ids))


def test_missing_previews_are_flagged(catalog):
    p = parse_product(raw("nopreview", preview_files=[]))
    s = build_promo(p, "what_you_get", date(2026, 11, 21))
    assert any("MISSING PREVIEWS" in n for n in s.visual_notes)


# ---- planning -----------------------------------------------------------

def test_plan_has_2_promos_3_educational_and_prefers_season(catalog):
    kit = plan_day(load_catalog(catalog), date(2026, 11, 21), History())
    assert len(kit.promos) == 2 and len(kit.educational) == 3
    # Thanksgiving window ends first, then Christmas.
    assert [r.script.product_id for r in kit.promos] == ["turkey", "xmas"]
    # The two promos never share an angle on the same day.
    assert [r.script.key for r in kit.promos][0] == "seasonal"
    assert len({r.script.key for r in kit.promos}) == 2
    assert len({r.script.key for r in kit.educational}) == 3


def test_out_of_season_products_rotate_by_last_promoted(catalog):
    products = load_catalog(catalog)
    history = History()
    day = date(2026, 3, 1)  # no seasonal products
    first = plan_day(products, day, history)
    record(first, history)
    second = plan_day(products, date(2026, 3, 2), history)
    assert {r.script.product_id for r in first.promos} == {"abc", "shapes"}
    # Only two non-seasonal-priority products left untouched: xmas and turkey.
    assert {r.script.product_id for r in second.promos} == {"turkey", "xmas"}


def test_angles_do_not_repeat_until_exhausted():
    p = parse_product(raw("abc"))
    history = History()
    seen = []
    for i in range(len(PROMO_ANGLES) - 1):  # non-seasonal angles
        a = choose_angle(p, date(2026, 3, 1), history)
        seen.append(a)
        history.promos.setdefault("abc", []).append({"date": f"2026-03-{i + 1:02d}", "angle": a})
    assert len(seen) == len(set(seen))
    # Next pick wraps to the oldest one.
    assert choose_angle(p, date(2026, 3, 9), history) == seen[0]


def test_topics_rotate_without_repeats_for_five_days(catalog):
    products = load_catalog(catalog)
    history = History()
    used = []
    for d in range(1, 6):
        kit = plan_day(products, date(2026, 3, d), history)
        record(kit, history)
        used += [r.script.key for r in kit.educational]
    assert len(used) == len(set(used)) == 15


def test_single_product_catalog_warns(tmp_path):
    path = tmp_path / "one.json"
    path.write_text(json.dumps([raw("abc")]))
    kit = plan_day(load_catalog(path), date(2026, 3, 1), History())
    assert len(kit.promos) == 1
    assert any("Only 1 product" in w for w in kit.warnings)


# ---- platform posts -----------------------------------------------------

def test_platform_posts_differ_and_respect_limits(catalog):
    kit = plan_day(load_catalog(catalog), date(2026, 11, 21), History())
    for reel in kit.reels:
        by = {p.platform: p for p in reel.posts}
        assert set(by) == {"instagram", "tiktok", "facebook", "youtube_shorts", "pinterest"}
        assert len({p.caption for p in reel.posts}) == 5
        assert len(by["youtube_shorts"].title) <= YOUTUBE_TITLE_MAX
        assert len(by["pinterest"].caption) <= PINTEREST_DESC_MAX
        assert "#shorts" in by["youtube_shorts"].hashtags
        assert len(by["instagram"].hashtags) <= 15
        assert by["pinterest"].hashtags == ()
        if reel.script.kind == "promo":
            for post in reel.posts:
                assert reel.script.link in post.full_text, post.platform
        else:
            assert all("gumroad" not in p.full_text for p in reel.posts)


def test_price_only_appears_when_given(catalog):
    kit = plan_day(load_catalog(catalog), date(2026, 3, 1), History())
    assert all("$" not in p.caption for r in kit.reels for p in r.posts)
    p = parse_product(raw("abc", price="$4.99"))
    from contentkit.platforms import build_posts
    s = build_promo(p, "what_you_get", date(2026, 3, 1))
    assert any("$4.99" in post.caption for post in build_posts(s, p))


# ---- CLI ----------------------------------------------------------------

def test_cli_writes_kit_and_records_history(catalog, tmp_path):
    out = tmp_path / "kits"
    hist = out / "history.json"
    rc = main(["--catalog", str(catalog), "--date", "2026-11-21",
               "--out", str(out), "--history", str(hist), "--record"])
    assert rc == 0
    md = (out / "2026-11-21.md").read_text()
    assert "## Reel 5 (educational)" in md
    assert STORE + "turkey" in md
    data = json.loads((out / "2026-11-21.json").read_text())
    assert len(data["reels"]) == 5
    assert json.loads(hist.read_text())["promos"]["turkey"][0]["angle"] == "seasonal"


def test_cli_fails_cleanly_on_bad_catalog(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps([raw("abc", gumroad_url="https://example.com/x")]))
    assert main(["--catalog", str(path), "--out", str(tmp_path)]) == 2
    assert "not a Gumroad product URL" in capsys.readouterr().err


# ---- pre-flight checks --------------------------------------------------

from contentkit.checks import check_link, check_previews, image_size, run_checks  # noqa: E402


def test_link_check_statuses():
    import urllib.error
    p = parse_product(raw("abc"))
    ok = fake_gumroad({p.gumroad_url: (200, "<title>Abc Pack | Gumroad</title>")})
    assert check_link(p, ok)[0] == "ok"
    assert check_link(p, fake_gumroad({}))[0] == "dead"
    wrong = fake_gumroad({p.gumroad_url: (200, "<title>Halloween Mazes</title>")})
    assert check_link(p, wrong)[0] == "mismatch"
    down = fake_gumroad({p.gumroad_url: urllib.error.URLError("timeout")})
    assert check_link(p, down)[0] == "unreachable"
    assert check_link(p, fake_gumroad({p.gumroad_url: (503, "")}))[0] == "unreachable"


def test_image_size_reads_png_and_jpeg(tmp_path):
    import struct
    write_png(tmp_path / "a.png", 1275, 1650)
    assert image_size(tmp_path / "a.png") == ("png", 1275, 1650)
    jpg = tmp_path / "b.jpg"
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + b"\x00" * 9
    sof = b"\xff\xc0" + struct.pack(">HBHH", 17, 8, 1650, 1275) + b"\x00" * 10
    jpg.write_bytes(b"\xff\xd8" + app0 + sof)
    assert image_size(jpg) == ("jpeg", 1275, 1650)
    (tmp_path / "c.png").write_text("not an image")
    assert image_size(tmp_path / "c.png") is None


def test_preview_check_flags_missing_small_and_fake(tmp_path):
    write_png(tmp_path / "good.png", 1275, 1650)
    write_png(tmp_path / "small.png", 600, 800)
    (tmp_path / "fake.png").write_text("text")
    p = parse_product(raw("abc", preview_files=["good.png", "small.png", "fake.png", "gone.png"]))
    good, problems = check_previews(p, tmp_path)
    assert good == ["good.png"]
    joined = " ".join(problems)
    assert "too small" in joined and "not a readable" in joined and "not found" in joined


def test_failing_products_are_left_out_of_promos(tmp_path):
    write_png(tmp_path / "p1.png", 1275, 1650)
    products = [
        parse_product(raw("good", preview_files=["p1.png"])),
        parse_product(raw("deadlink", preview_files=["p1.png"])),
        parse_product(raw("nopics", preview_files=["missing.png"])),
        parse_product(raw("unverified", preview_files=["p1.png", "missing.png"])),
    ]
    import urllib.error
    fetch = fake_gumroad({
        STORE + "good": (200, "<title>Good Pack</title>"),
        STORE + "nopics": (200, "<title>Nopics Pack</title>"),
        STORE + "unverified": urllib.error.URLError("offline"),
    })
    checks = run_checks(products, tmp_path, fetch=fetch)
    assert [pid for pid, c in checks.items() if c.promotable] == ["good", "unverified"]
    kit = plan_day(products, date(2026, 3, 1), History(), checks)
    assert {r.script.product_id for r in kit.promos} == {"good", "unverified"}
    text = " ".join(kit.warnings)
    assert "deadlink: Gumroad link dead" in text
    assert "nopics: left out" in text
    assert "unverified: Gumroad link unreachable" in text
    # Only previews that passed are used in the edit notes.
    unverified = next(r for r in kit.promos if r.script.product_id == "unverified")
    assert not any("missing.png" in n for n in unverified.script.visual_notes)


def test_no_link_check_flag_skips_network(catalog, tmp_path, monkeypatch):
    def boom(url):
        raise AssertionError("network used")
    monkeypatch.setattr("contentkit.checks.http_fetch", boom)
    out = tmp_path / "kits"
    assert main(["--catalog", str(catalog), "--date", "2026-11-21", "--out", str(out),
                 "--history", str(out / "h.json"), "--no-link-check"]) == 0
    assert "not checked" in (out / "2026-11-21.md").read_text()
