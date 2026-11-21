"""Pre-flight checks run before a product can be promoted.

- Gumroad link: fetched live. A 404/410 (deleted or unpublished product)
  removes the product from today's promos. If the page title doesn't mention
  the product name, the link may point at the wrong product, which is flagged.
  If Gumroad can't be reached, the product stays in but is marked unverified.
- Previews: every listed file must exist, be a real PNG or JPEG, and be at
  least HD_MIN_SHORT_SIDE pixels on its short side. A product with no usable
  preview is removed from promos, because promos must show the real PDF.
"""

from __future__ import annotations

import html
import re
import struct
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .products import Product

HD_MIN_SHORT_SIDE = 1080
USER_AGENT = "Mozilla/5.0 (compatible; contentkit-link-check/1.0)"


@dataclass
class CheckResult:
    product_id: str
    link_status: str = "skipped"  # ok | mismatch | dead | unreachable | skipped
    link_detail: str = ""
    good_previews: list[str] = field(default_factory=list)
    preview_problems: list[str] = field(default_factory=list)

    @property
    def promotable(self) -> bool:
        return self.link_status != "dead" and bool(self.good_previews)

    def messages(self) -> list[str]:
        out = []
        if self.link_status in ("dead", "mismatch", "unreachable"):
            out.append(f"{self.product_id}: Gumroad link {self.link_status}: {self.link_detail}")
        out += [f"{self.product_id}: {p}" for p in self.preview_problems]
        if not self.promotable:
            out.append(f"{self.product_id}: left out of today's promos until fixed.")
        return out


# ---- Gumroad link -------------------------------------------------------

Fetcher = Callable[[str], tuple[int, str]]


def http_fetch(url: str, timeout: float = 15.0) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(200_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""


def _norm(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}


def check_link(product: Product, fetch: Fetcher = http_fetch) -> tuple[str, str]:
    try:
        status, body = fetch(product.gumroad_url)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return "unreachable", f"could not reach Gumroad ({exc}); check the link by hand"
    if status in (404, 410):
        return "dead", f"{product.gumroad_url} returned {status} (deleted or unpublished?)"
    if status >= 400:
        return "unreachable", f"{product.gumroad_url} returned {status}; check it by hand"
    m = re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I)
    title = html.unescape(m.group(1)).strip() if m else ""
    wanted = _norm(product.name)
    if wanted and title and not (wanted & _norm(title)):
        return "mismatch", f"page title is '{title}', expected something like '{product.name}'"
    return "ok", title


# ---- Preview images -----------------------------------------------------

def image_size(path: Path) -> tuple[str, int, int] | None:
    """Return (format, width, height) for PNG/JPEG files, else None."""
    with path.open("rb") as f:
        head = f.read(32)
        if head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR":
            w, h = struct.unpack(">II", head[16:24])
            return "png", w, h
        if head[:2] != b"\xff\xd8":
            return None
        f.seek(2)
        while True:
            marker = f.read(2)
            if len(marker) < 2 or marker[0] != 0xFF:
                return None
            code = marker[1]
            if code in (0xD8, 0x01) or 0xD0 <= code <= 0xD7:
                continue
            seg_len = struct.unpack(">H", f.read(2))[0]
            if code in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                        0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                f.read(1)
                h, w = struct.unpack(">HH", f.read(4))
                return "jpeg", w, h
            f.seek(seg_len - 2, 1)


def check_previews(product: Product, base_dir: Path) -> tuple[list[str], list[str]]:
    good, problems = [], []
    if not product.preview_files:
        return good, ["no preview_files listed; export 3-4 real pages from the PDF"]
    for rel in product.preview_files:
        path = (base_dir / rel)
        if not path.is_file():
            problems.append(f"preview not found: {rel}")
            continue
        try:
            info = image_size(path)
        except (OSError, struct.error):
            info = None
        if not info:
            problems.append(f"preview is not a readable PNG/JPEG: {rel}")
            continue
        _, w, h = info
        if min(w, h) < HD_MIN_SHORT_SIDE:
            problems.append(f"preview too small for HD ({w}x{h}, need {HD_MIN_SHORT_SIDE}px short side): {rel}")
            continue
        good.append(rel)
    return good, problems


def run_checks(products: list[Product], base_dir: Path, *, check_links: bool = True,
               fetch: Fetcher | None = None) -> dict[str, CheckResult]:
    fetch = fetch or http_fetch
    results = {}
    for p in products:
        r = CheckResult(p.id)
        if check_links:
            r.link_status, r.link_detail = check_link(p, fetch)
        r.good_previews, r.preview_problems = check_previews(p, base_dir)
        results[p.id] = r
    return results
