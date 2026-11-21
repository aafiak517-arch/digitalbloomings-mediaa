"""Reel script templates: promotional angles and educational topics.

Every script is kept short enough to be read in under 15 seconds by an
energetic voiceover. Durations are estimated from word count, so the check is
deterministic and can run in tests and CI.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Callable

from .products import Product

# Upbeat US English voiceover pace, words per second (~160 wpm).
WORDS_PER_SECOND = 2.7
# Seconds reserved for the end card with the link and logo.
END_CARD_SECONDS = 1.5
MAX_REEL_SECONDS = 15.0


class ScriptTooLongError(ValueError):
    pass


@dataclass(frozen=True)
class ReelScript:
    kind: str  # "promo" or "educational"
    key: str  # angle key or topic id
    title: str
    hook: str  # spoken + on screen in the first 2 seconds
    lines: tuple[str, ...]  # remaining voiceover lines, one subtitle each
    cta: str
    on_screen_text: tuple[str, ...]
    visual_notes: tuple[str, ...]
    product_id: str | None = None
    link: str | None = None

    @property
    def voiceover(self) -> str:
        return " ".join((self.hook, *self.lines, self.cta))

    @property
    def word_count(self) -> int:
        return len(self.voiceover.split())

    @property
    def est_seconds(self) -> float:
        spoken = self.word_count / WORDS_PER_SECOND
        return math.ceil((spoken + END_CARD_SECONDS) * 10) / 10

    def check_length(self) -> None:
        if self.est_seconds >= MAX_REEL_SECONDS:
            raise ScriptTooLongError(
                f"{self.kind}:{self.key} runs ~{self.est_seconds}s "
                f"({self.word_count} words); must be under {MAX_REEL_SECONDS}s"
            )
        if len(self.hook.split()) > 8:
            raise ScriptTooLongError(
                f"{self.kind}:{self.key} hook is too long for a 2-second open"
            )


# --------------------------------------------------------------------------
# Promotional angles
# --------------------------------------------------------------------------

PromoBuilder = Callable[[Product, date], tuple[str, list[str], str]]


def _angle_what_you_get(p: Product, day: date):
    hook = f"{p.pages} pages. One download."
    lines = [f"{p.name} for ages {p.ages}.", f"{p.highlights[0]}.", f"{p.highlights[1]}."]
    return hook, lines, "Print it today. Link on screen!"


def _angle_screen_free(p: Product, day: date):
    hook = "Need a screen-free hour?"
    lines = [f"Print {p.name}.", f"{p.highlights[0]}, ages {p.ages}."]
    return hook, lines, "Grab it now. Link on screen!"


def _angle_busy_parent(p: Product, day: date):
    hook = "No prep. No mess. Just print."
    lines = [f"{p.name}: {p.pages} pages of {p.highlights[0].lower()}."]
    return hook, lines, "Get yours at the link!"


def _angle_teacher_ready(p: Product, day: date):
    hook = "Teachers, your next center is ready."
    lines = [f"{p.name}, ages {p.ages}.", f"{p.highlights[1]}.", "Print as many copies as your class needs."]
    return hook, lines, "Download now. Link on screen!"


def _angle_skill_focus(p: Product, day: date):
    hook = "Watch them learn while they play."
    lines = [f"{p.highlights[0]}.", f"{p.highlights[1]}.", f"All in {p.name}."]
    return hook, lines, "Tap the link and print today!"


def _angle_seasonal(p: Product, day: date):
    left = p.days_left_in_season(day)
    hook = "The season is almost here!" if left is None or left > 7 else "Last days to print in time!"
    lines = [f"{p.name}: {p.pages} pages.", f"{p.highlights[0]}."]
    return hook, lines, "Grab it before the holiday. Link on screen!"


PROMO_ANGLES: dict[str, tuple[str, PromoBuilder]] = {
    "what_you_get": ("Everything inside", _angle_what_you_get),
    "screen_free": ("Screen-free hour", _angle_screen_free),
    "busy_parent": ("Zero-prep for busy parents", _angle_busy_parent),
    "teacher_ready": ("Classroom ready", _angle_teacher_ready),
    "skill_focus": ("Skills they build", _angle_skill_focus),
    "seasonal": ("Seasonal countdown", _angle_seasonal),
}


def angles_for(product: Product, day: date) -> list[str]:
    """Angles that make sense for this product on this day."""
    keys = [k for k in PROMO_ANGLES if k != "seasonal"]
    if product.in_season(day):
        keys.insert(0, "seasonal")
    return keys


def build_promo(product: Product, angle: str, day: date) -> ReelScript:
    title, builder = PROMO_ANGLES[angle]
    hook, lines, cta = builder(product, day)
    # Drop optional middle lines until it fits the 15 second limit.
    script = None
    while True:
        script = ReelScript(
            kind="promo",
            key=angle,
            title=f"{product.name}: {title}",
            hook=hook,
            lines=tuple(lines),
            cta=cta,
            on_screen_text=(hook, *lines, product.gumroad_url),
            visual_notes=_promo_visuals(product),
            product_id=product.id,
            link=product.gumroad_url,
        )
        if script.est_seconds < MAX_REEL_SECONDS or len(lines) <= 1:
            break
        lines = lines[:-1]
    script.check_length()
    return script


def _promo_visuals(p: Product) -> tuple[str, ...]:
    notes = ["0-2s: hook text over the product cover, quick zoom in."]
    if p.preview_files:
        for i, f in enumerate(p.preview_files[:4], start=1):
            notes.append(f"Preview {i}: {f} (real page from the PDF).")
    else:
        notes.append(
            "MISSING PREVIEWS: export 3-4 real pages from the PDF before "
            "editing. Do not use stand-in images."
        )
    notes.append("Last 1.5s: end card with logo and the Gumroad link.")
    return tuple(notes)


# --------------------------------------------------------------------------
# Educational topics
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Topic:
    id: str
    title: str
    hook: str
    lines: tuple[str, ...]
    mixkit_search: tuple[str, ...]
    hashtags: tuple[str, ...]
    cta: str = "Follow for daily learning ideas!"


TOPICS: tuple[Topic, ...] = (
    Topic("letter_sounds_first", "Teach letter sounds first", "Stop teaching letter names first.",
          ("Start with sounds: say mmm, not em.", "Sounds help kids blend words sooner."),
          ("child reading book", "mother teaching child"), ("#phonics", "#learntoread")),
    Topic("sound_hunt", "Letter sound scavenger hunt", "Try this 5-minute letter game.",
          ("Pick a letter sound.", "Hunt the house for three things that start with it."),
          ("kids playing at home", "child running living room"), ("#preschoolactivities", "#phonicsfun")),
    Topic("name_tracing", "Name tracing trick", "Their name is the best first word.",
          ("Write it big in highlighter.", "Let them trace it with a crayon every morning."),
          ("child drawing crayons", "kid writing table"), ("#prewriting", "#preschoolathome")),
    Topic("pencil_grip", "Fix pencil grip with a crayon", "Struggling with pencil grip?",
          ("Snap crayons into short pieces.", "Tiny crayons force a natural pinch grip."),
          ("child coloring close up", "crayons on table"), ("#finemotorskills", "#prek")),
    Topic("counting_snacks", "Counting at snack time", "Snack time is math time.",
          ("Count crackers together before eating.", "Ask: if you eat one, how many are left?"),
          ("child eating snack", "family kitchen table"), ("#earlymath", "#learningthroughplay")),
    Topic("rhyme_car", "Rhyming game for the car", "Bored in the car? Play this.",
          ("Say a word like cat.", "Take turns naming words that rhyme with it."),
          ("family car trip", "child car seat smiling"), ("#rhyming", "#screenfreekids")),
    Topic("sight_word_jump", "Sight word jump", "Get the wiggles out and learn.",
          ("Tape sight words on the floor.", "Call one out and have them jump on it."),
          ("kids jumping indoors", "child playing floor"), ("#sightwords", "#kindergartenprep")),
    Topic("calm_down_coloring", "Coloring to calm down", "Coloring is not just busy work.",
          ("It slows breathing and builds focus.", "Try ten quiet minutes after school."),
          ("child coloring calm", "kid art quiet"), ("#coloringforkids", "#parentingtips")),
    Topic("shape_walk", "Shape walk outside", "Turn a walk into a lesson.",
          ("Spot circles, squares and triangles.", "Wheels, windows, roofs. Shapes are everywhere."),
          ("mother child walking park", "kids outdoors autumn"), ("#shapes", "#outdoorlearning")),
    Topic("routine_chart", "Picture routine chart", "Mornings take forever? Try this.",
          ("Make a picture chart: dress, eat, brush.", "Kids check each step themselves."),
          ("child getting dressed", "morning routine family"), ("#toddlerroutine", "#momhacks")),
    Topic("scissor_skills", "Safe scissor practice", "Ready for scissors? Start here.",
          ("Cut straws or play dough first.", "Then move to straight lines on paper."),
          ("child cutting paper", "kids crafts table"), ("#finemotor", "#preschoolcrafts")),
    Topic("read_aloud_questions", "Better read-aloud questions", "Ask this during story time.",
          ("Pause and ask: what happens next?", "Predicting builds real reading comprehension."),
          ("parent reading bedtime story", "child book bed"), ("#readaloud", "#raisingreaders")),
    Topic("sorting_laundry", "Sorting with laundry", "Laundry can teach sorting.",
          ("Sort socks by color, then by size.", "Then match the pairs together."),
          ("child helping laundry", "kids folding clothes"), ("#montessoriathome", "#toddleractivities")),
    Topic("beginning_sounds_mail", "Mailbox sound game", "Make a mailbox from a box.",
          ("Draw pictures on cards.", "Kids post each card in the slot for its first sound."),
          ("kids crafts cardboard", "child playing pretend"), ("#beginningsounds", "#preschoolteacher")),
    Topic("praise_effort", "Praise effort, not smart", "Say this instead of good job.",
          ("Try: you worked so hard on that.", "Effort praise helps kids keep trying."),
          ("mother hugging child", "happy child drawing"), ("#gentleparenting", "#parentingtips")),
)

TOPICS_BY_ID = {t.id: t for t in TOPICS}


def build_educational(topic: Topic) -> ReelScript:
    script = ReelScript(
        kind="educational",
        key=topic.id,
        title=topic.title,
        hook=topic.hook,
        lines=topic.lines,
        cta=topic.cta,
        on_screen_text=(topic.hook, *topic.lines),
        visual_notes=(
            "Clips: search Mixkit for "
            + "; ".join(f'"{q}"' for q in topic.mixkit_search)
            + ". Use free-license clips only and keep the clip page URL in the edit notes.",
            "0-2s: bold hook caption over the most active clip.",
            "End: brand logo and handle, no hard sell.",
        ),
    )
    script.check_length()
    return script
