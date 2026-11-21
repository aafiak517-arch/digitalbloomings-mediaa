"""Platform-specific captions, titles and hashtags.

Each platform gets its own wording and hashtag count instead of one caption
pasted everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass

from .products import Product
from .scripts import ReelScript

BRAND = "Digital Bloomings Kids"
BASE_TAGS = ("#printables", "#preschool", "#momlife", "#kidsactivities", "#homeschool")
PROMO_TAGS = ("#printableworksheets", "#preschoolworksheets", "#preschoolteacher",
              "#kindergarten", "#learningathome", "#screenfreeactivities")

# Hard limits published by each platform; we stay under them.
YOUTUBE_TITLE_MAX = 100
PINTEREST_TITLE_MAX = 100
PINTEREST_DESC_MAX = 500
TIKTOK_CAPTION_MAX = 2200
INSTAGRAM_TAG_MAX = 30


@dataclass(frozen=True)
class PlatformPost:
    platform: str
    title: str | None
    caption: str
    hashtags: tuple[str, ...]

    @property
    def full_text(self) -> str:
        return f"{self.caption}\n\n{' '.join(self.hashtags)}".strip()


def _tags(script: ReelScript, product: Product | None, extra: tuple[str, ...] = ()) -> list[str]:
    tags: list[str] = []
    if product:
        tags += ["#" + k.replace(" ", "").lower() for k in product.keywords]
        tags += list(PROMO_TAGS)
    tags += list(extra) + list(BASE_TAGS)
    seen: set[str] = set()
    out = []
    for t in tags:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def build_posts(script: ReelScript, product: Product | None,
                topic_tags: tuple[str, ...] = ()) -> list[PlatformPost]:
    tags = _tags(script, product, topic_tags)
    body = " ".join(script.lines)
    if product:
        price = f" Just {product.price}." if product.price else ""
        link = product.gumroad_url
        ig = (f"{script.hook} {body}\n\n{product.name}: {product.pages} printable pages "
              f"for ages {product.ages}.{price}\n\nShop: tap the link in bio or visit {link}")
        tt = f"{script.hook} {product.name} is on Gumroad. Link in bio: {link}"
        fb = (f"{script.hook}\n\n{body}\n\n{product.name} ({product.pages} pages, ages "
              f"{product.ages}).{price} Instant download, print at home.\n\n👉 {link}")
        yt_title = f"{script.hook} {product.name} #shorts"
        yt_desc = f"{body}\n\nGet {product.name}: {link}\n\nSubscribe to {BRAND} for more printables."
        pin_title = f"{product.name} | Printable for Ages {product.ages}"
        pin_desc = (f"{product.highlights[0]}. {product.highlights[1]}. {product.pages} US Letter "
                    f"pages, instant PDF download. {' '.join(product.keywords)}. Shop: {link}")
    else:
        ig = f"{script.hook}\n\n{body}\n\nSave this for later and follow @{BRAND.replace(' ', '').lower()} for daily ideas."
        tt = f"{script.hook} {script.cta}"
        fb = f"{script.hook}\n\n{body}\n\nShare this with a mom who needs it today."
        yt_title = f"{script.title} #shorts"
        yt_desc = f"{body}\n\nSubscribe to {BRAND} for simple learning ideas every day."
        pin_title = f"{script.title} | Easy Preschool Idea"
        pin_desc = f"{script.hook} {body} More screen-free learning ideas from {BRAND}."

    return [
        PlatformPost("instagram", None, ig, tuple(tags[:15])),
        PlatformPost("tiktok", None, _clip(tt, TIKTOK_CAPTION_MAX), tuple(tags[:5])),
        PlatformPost("facebook", None, fb, tuple(tags[:3])),
        PlatformPost("youtube_shorts", _clip(yt_title, YOUTUBE_TITLE_MAX), yt_desc,
                     tuple(["#shorts", *tags[:2]])),
        # Pinterest ranks on keywords in the text, not hashtags.
        PlatformPost("pinterest", _clip(pin_title, PINTEREST_TITLE_MAX),
                     _clip(pin_desc, PINTEREST_DESC_MAX), ()),
    ]
