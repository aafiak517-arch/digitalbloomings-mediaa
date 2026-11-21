"""Render a DailyKit as a Markdown work sheet and as JSON."""

from __future__ import annotations

import json

from .planner import DailyKit

PLATFORM_LABELS = {
    "instagram": "Instagram Reels",
    "tiktok": "TikTok",
    "facebook": "Facebook Page",
    "youtube_shorts": "YouTube Shorts",
    "pinterest": "Pinterest (Idea / Video Pin)",
}


LINK_LABELS = {
    "ok": "live",
    "mismatch": "live, title doesn't match",
    "dead": "DEAD (404)",
    "unreachable": "not verified",
    "skipped": "not checked",
}


def to_markdown(kit: DailyKit) -> str:
    out = [f"# Daily content kit: {kit.day.strftime('%A, %B %-d, %Y')}", ""]
    out.append(f"{len(kit.promos)} promotional + {len(kit.educational)} educational reels. "
               "Nothing here is published yet; every post below is ready to upload.")
    out.append("")
    if kit.warnings:
        out.append("## Fix before editing")
        out += [f"- {w}" for w in kit.warnings]
        out.append("")
    if kit.checks is not None:
        out.append("## Pre-flight checks")
        out.append("| Product | Gumroad link | HD previews | Promo today? |")
        out.append("|---|---|---|---|")
        for pid, c in kit.checks.items():
            link = LINK_LABELS.get(c.link_status, c.link_status)
            previews = f"{len(c.good_previews)} ok" + (f", {len(c.preview_problems)} problem(s)" if c.preview_problems else "")
            out.append(f"| {pid} | {link} | {previews} | {'eligible' if c.promotable else 'no, fix first'} |")
        out.append("")
    if kit.promos:
        out.append("## Products promoted today")
        out += [f"- {r.script.title.split(':')[0]}: {r.script.link}" for r in kit.promos]
        out.append("")

    for reel in kit.reels:
        s = reel.script
        out.append(f"## Reel {reel.number} ({s.kind}): {s.title}")
        out.append(f"Estimated length: {s.est_seconds}s ({s.word_count} words)")
        if s.link:
            out.append(f"Gumroad link (show on screen and in captions): {s.link}")
        out.append("")
        out.append("**Voiceover** (energetic, confident female US English)")
        out.append(f"> **Hook (0-2s):** {s.hook}")
        for line in s.lines:
            out.append(f"> {line}")
        out.append(f"> **CTA:** {s.cta}")
        out.append("")
        out.append("**Subtitles / on-screen text**")
        out += [f"{i}. {t}" for i, t in enumerate(s.on_screen_text, start=1)]
        out.append("")
        out.append("**Visuals**")
        out += [f"- {n}" for n in s.visual_notes]
        out.append("")
        for post in reel.posts:
            out.append(f"### {PLATFORM_LABELS[post.platform]}")
            if post.title:
                out.append(f"**Title:** {post.title}")
                out.append("")
            out.append("```text")
            out.append(post.full_text)
            out.append("```")
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def to_json(kit: DailyKit) -> str:
    data = {
        "date": kit.day.isoformat(),
        "warnings": kit.warnings,
        "checks": None if kit.checks is None else {
            pid: {"link_status": c.link_status, "link_detail": c.link_detail,
                  "good_previews": c.good_previews, "preview_problems": c.preview_problems,
                  "promotable": c.promotable}
            for pid, c in kit.checks.items()
        },
        "reels": [
            {
                "number": r.number,
                "kind": r.script.kind,
                "key": r.script.key,
                "title": r.script.title,
                "product_id": r.script.product_id,
                "link": r.script.link,
                "est_seconds": r.script.est_seconds,
                "hook": r.script.hook,
                "lines": list(r.script.lines),
                "cta": r.script.cta,
                "voiceover": r.script.voiceover,
                "on_screen_text": list(r.script.on_screen_text),
                "visual_notes": list(r.script.visual_notes),
                "posts": [
                    {"platform": p.platform, "title": p.title,
                     "caption": p.caption, "hashtags": list(p.hashtags)}
                    for p in r.posts
                ],
            }
            for r in kit.reels
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)
