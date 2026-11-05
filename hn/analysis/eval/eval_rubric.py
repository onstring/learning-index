"""Single source of truth for the labelling rubric.

Used by: the human gold labels, the clef-flash question schema, and the qwen prompt.
"""

# Boolean sub-questions. Each: (name, instructions, true description, false description).
# Keep rule = free_to_access AND is_learning_material AND is_evergreen
#             AND NOT is_video AND NOT is_code_repo AND NOT is_paid_book
BOOLS = [
    ("free_to_access",
     "Can a student read the whole resource online for free, without paying, subscribing or "
     "creating a paid account?",
     "free to read in full online (free course, free online book, open docs, blog post, free PDF)",
     "paywalled, a landing page for a paid book or course, requires purchase, or a product you buy"),
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
]

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

# Topic taxonomy. Order matters for clef ties: most common first.
TOPICS = {
    "programming": "a programming language, coding practice, software craft, testing, tooling",
    "computer_science": "algorithms, data structures, compilers, theory of computation, CS curricula",
    "systems": "operating systems, networking, distributed systems, performance, security, low level",
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

TYPES = {
    "course": "structured course or curriculum with lessons or modules",
    "tutorial": "step-by-step guide or how-to for a specific skill",
    "free_book": "a complete book or textbook readable online for free",
    "reference": "reference documentation, manual, cheat sheet, specification",
    "explainer": "a single article or blog post that explains a concept",
    "interactive": "interactive lessons, visualisations, exercises, playground",
    "collection": "a curated list or index of other resources",
    "other": "none of the above or not a learning resource",
}

DIFFICULTY = [
    "beginner: no prior background needed",
    "intermediate: assumes some programming, maths or domain background",
    "advanced: graduate, research or professional level",
]


def keep_from_bools(b: dict) -> bool:
    """Apply the keep rule to a dict of booleans."""
    return bool(b["free_to_access"] and b["is_learning_material"] and b["is_evergreen"]
                and not b["is_video"] and not b["is_code_repo"] and not b["is_paid_book"])


def state_text(item: dict) -> str:
    """Identical context text for both models and the human labeller."""
    lines = [f"URL: https://{item['nurl']}", f"Host: {item['host']}"]
    if item.get("page_title"):
        lines.append(f"Page title: {item['page_title']}")
    if item.get("page_desc"):
        lines.append(f"Page description: {item['page_desc']}")
    if item.get("http_status") not in (200, None):
        lines.append(f"Fetch status: {item['http_status']}")
    if item.get("story_title"):
        lines.append(f"Hacker News story title: {item['story_title']}")
    lines.append(f"Recommended by {item['ppl']} distinct HN commenters across {item['yrs']} "
                 f"year(s), {item['y0']}-{item['y1']}.")
    for i, ex in enumerate(item.get("excerpts") or [], 1):
        lines.append(f"HN comment {i}: {ex}")
    return "\n".join(lines)


def rubric_markdown() -> str:
    out = ["# Labelling rubric", "",
           "Keep = free_to_access AND is_learning_material AND is_evergreen AND NOT is_video "
           "AND NOT is_code_repo AND NOT is_paid_book.", "", "## Boolean questions", ""]
    for name, q, t, f in BOOLS:
        out += [f"**{name}**: {q}", f"- true: {t}", f"- false: {f}", ""]
    out += ["## Composite question (clef only, for comparison)", "", COMPOSITE[1], "",
            "## Topics", ""] + [f"- `{k}`: {v}" for k, v in TOPICS.items()]
    out += ["", "## Resource types", ""] + [f"- `{k}`: {v}" for k, v in TYPES.items()]
    out += ["", "## Difficulty", ""] + [f"- {i}: {d}" for i, d in enumerate(DIFFICULTY)]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    print(rubric_markdown())
