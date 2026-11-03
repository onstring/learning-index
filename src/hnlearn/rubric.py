"""The labelling rubric: clef questions, taxonomy, keep rule, prompts.

Single source of truth. The evaluation in ``analysis/eval`` used the same wording.
"""

from __future__ import annotations

from typing import Any

from hnlearn import config, text

# (name, instructions, true description, false description)
BOOLS: tuple[tuple[str, str, str, str], ...] = (
    ("free_to_access",
     "Can a student read the whole resource online for free, without paying, subscribing or "
     "creating a paid account?",
     "free to read in full online (free course, free online book, open docs, blog post, free PDF)",
     "paywalled, a landing page for a paid book or course, requires purchase, or a product "
     "you buy"),
    ("is_learning_material",
     "Does the resource teach or explain a subject or skill (tutorial, course, guide, explainer, "
     "lecture notes, textbook, reference documentation, interactive lesson)? A single well-written "
     "blog post that explains a topic counts. A news report, opinion piece, product page, company "
     "homepage, personal homepage, tool, dataset or discussion thread does not.",
     "teaches or explains a subject: tutorial, course, guide, explainer, textbook, reference docs",
     "news, opinion, product or company page, tool, personal homepage, discussion, announcement"),
    ("is_evergreen",
     "Would the resource still be worth reading years later, regardless of current events?",
     "timeless material a student could learn from in any year",
     "tied to a news event, a release, a current controversy, a deal or a date"),
    ("is_video",
     "Is the resource primarily video (a video, lecture recording, video course or channel)?",
     "primarily video content",
     "primarily text, code or interactive content"),
    ("is_code_repo",
     "Is the resource primarily a source-code repository or software download rather than "
     "written teaching material?",
     "source-code repository, package, or software download",
     "written or interactive teaching material (even if it contains code samples)"),
    ("is_paid_book",
     "Is the resource a page about a printed or paid book (publisher page, book landing page, "
     "shop listing) rather than the free text itself?",
     "page selling or describing a book you must buy",
     "the free full text is online, or it is not a book at all"),
)

COMPOSITE = (
    "is_free_learning_resource",
    "Is this a free online learning resource that a curious student could use to learn or "
    "understand a subject: a tutorial, course, guide, explainer, free online book, reference "
    "documentation or a single explanatory blog post? It must be free to read in full, not "
    "primarily video, not a code repository, not a page for a paid book, and not tied to a "
    "news event.",
    "free online learning resource: tutorial, course, guide, explainer, free book, reference, "
    "explanatory blog post",
    "news, opinion, product, company page, paid book, video, code repository, tool, dataset, "
    "discussion thread",
)

# order matters for clef ties: most common first
TOPICS: dict[str, str] = {
    "programming": "a programming language, coding practice, software craft, testing, tooling",
    "computer_science": "algorithms, data structures, compilers, theory of computation, "
                        "CS curricula",
    "systems": "operating systems, networking, distributed systems, performance, security, "
               "low level",
    "web": "web development, HTML, CSS, JavaScript frameworks, browsers, HTTP, web design",
    "data": "databases, SQL, data engineering, data analysis, statistics in practice",
    "ml_ai": "machine learning, deep learning, AI, LLMs",
    "mathematics": "mathematics, pure or applied, including statistics theory and probability",
    "science": "physics, chemistry, biology, astronomy, earth science, medicine",
    "hardware": "electronics, embedded systems, computer architecture, making, robotics",
    "design": "visual design, UX, typography, graphics, game design, art",
    "writing": "writing, communication, language learning, speaking, teaching",
    "business": "economics, finance, investing, startups, management, product, marketing",
    "humanities": "history, philosophy, law, politics, psychology, society",
    "self_improvement": "how to learn, careers, productivity, health, thinking, decision making",
    "other": "none of the above",
}

TOPIC_LABELS: dict[str, str] = {
    "programming": "Programming", "computer_science": "Computer science", "systems": "Systems",
    "web": "Web development", "data": "Data and databases", "ml_ai": "Machine learning and AI",
    "mathematics": "Mathematics", "science": "Science", "hardware": "Hardware and electronics",
    "design": "Design", "writing": "Writing and communication",
    "business": "Business and economics",
    "humanities": "Humanities", "self_improvement": "Learning and self-improvement",
    "other": "Other",
}

TYPES: dict[str, str] = {
    "course": "structured course or curriculum with lessons or modules",
    "tutorial": "step-by-step guide or how-to for a specific skill",
    "free_book": "a complete book or textbook readable online for free",
    "reference": "reference documentation, manual, cheat sheet, specification",
    "explainer": "a single article or blog post that explains a concept",
    "interactive": "interactive lessons, visualisations, exercises, playground",
    "collection": "a curated list or index of other resources",
    "other": "none of the above or not a learning resource",
}

TYPE_LABELS: dict[str, str] = {
    "course": "Course", "tutorial": "Tutorial", "free_book": "Free book", "reference": "Reference",
    "explainer": "Explainer", "interactive": "Interactive", "collection": "Collection",
    "other": "Other",
}

DIFFICULTY: tuple[str, ...] = (
    "beginner: no prior background needed",
    "intermediate: assumes some programming, maths or domain background",
    "advanced: graduate, research or professional level",
)
DIFFICULTY_LABELS: tuple[str, ...] = ("Beginner", "Intermediate", "Advanced")


def clef_questions() -> dict[str, dict[str, Any]]:
    """The question schema sent to clef-flash for every candidate."""
    q: dict[str, dict[str, Any]] = {}
    for name, instr, t, f in (*BOOLS, COMPOSITE):
        q[name] = {"type": "noul", "instructions": instr, "criteria": {"true": t, "false": f}}
    q["topic"] = {"type": "choice", "instructions": "Primary topic of the resource.",
                  "criteria": dict(TOPICS)}
    q["resource_type"] = {"type": "choice", "instructions": "What kind of resource is it?",
                          "criteria": dict(TYPES)}
    q["difficulty"] = {"type": "score", "instructions": "Difficulty for a curious student.",
                       "criteria": list(DIFFICULTY)}
    return q


def keep(composite_prob: float, threshold: float = config.KEEP_THRESHOLD,
         video_prob: float = 0.0) -> bool:
    """The keep rule: composite probability at or above the threshold, and not clearly video."""
    return composite_prob >= threshold and video_prob < config.VIDEO_EXCLUDE


def keep_row(clef: dict[str, Any], threshold: float = config.KEEP_THRESHOLD) -> bool:
    """Apply the keep rule to a classify output row."""
    return keep(clef[COMPOSITE[0]], threshold, clef.get("is_video", 0.0))


def state_text(cand: dict[str, Any], fetched: dict[str, Any] | None) -> str:
    """Context text for one candidate, identical for clef and for the blurb model."""
    lines = [f"URL: https://{cand['nurl']}", f"Host: {cand['host']}"]
    if fetched and text.is_challenge_page(fetched.get("title"), fetched.get("snippet")):
        lines.append("Fetch status: the site returned a bot-check page instead of content")
        fetched = None
    if fetched:
        if fetched.get("title"):
            lines.append(f"Page title: {fetched['title']}")
        if fetched.get("description"):
            lines.append(f"Page description: {fetched['description']}")
        if fetched.get("snippet"):
            lines.append(f"Page text: {fetched['snippet']}")
        if fetched.get("status") != 200:
            lines.append(f"Fetch status: {fetched.get('status')}")
    if cand.get("story_title"):
        lines.append(f"Hacker News story title: {cand['story_title']}")
    lines.append(f"Recommended by {cand['ppl']} distinct HN commenters across {cand['yrs']} "
                 f"year(s), {cand['y0']}-{cand['y1']}.")
    for i, ev in enumerate(cand.get("evidence") or [], 1):
        lines.append(f"HN comment {i}: {ev['excerpt']}")
    return "\n".join(lines)


def blurb_schema() -> dict[str, Any]:
    """JSON schema for the blurb model's structured output."""
    return {"type": "object",
            "properties": {"title": {"type": "string"}, "blurb": {"type": "string"}},
            "required": ["title", "blurb"]}


def blurb_system() -> str:
    """System prompt for the blurb model."""
    return (
        "You write catalogue entries for a site that lists free online learning resources for "
        "curious students. You receive the resource's URL, its page title and text where "
        "available, and Hacker News comments that recommended it. Output JSON only.\n"
        "title: the resource's own name, cleaned up: drop site-name suffixes, marketing taglines "
        "and separators. If the page title is missing, use the name the comments or the Hacker "
        "News story use. Never invent a name.\n"
        f"blurb: one neutral sentence, at most {config.BLURB_MAX_WORDS} words, saying what a "
        "student would learn from the resource. No marketing language. Do not mention Hacker "
        "News or the comments."
    )


def markdown() -> str:
    """Rubric rendered as Markdown, for documentation."""
    out = ["# Labelling rubric", "", f"Keep = `{COMPOSITE[0]}` probability at or above "
           f"{config.KEEP_THRESHOLD}.", "", "## Questions", ""]
    for name, q, t, f in (*BOOLS, COMPOSITE):
        out += [f"**{name}**: {q}", f"- true: {t}", f"- false: {f}", ""]
    out += ["## Topics", ""] + [f"- `{k}`: {v}" for k, v in TOPICS.items()]
    out += ["", "## Resource types", ""] + [f"- `{k}`: {v}" for k, v in TYPES.items()]
    out += ["", "## Difficulty", ""] + [f"- {i}: {d}" for i, d in enumerate(DIFFICULTY)]
    return "\n".join(out) + "\n"
