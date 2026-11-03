# Labelling rubric

Keep = free_to_access AND is_learning_material AND is_evergreen AND NOT is_video AND NOT is_code_repo AND NOT is_paid_book.

## Boolean questions

**free_to_access**: Can a student read the whole resource online for free, without paying, subscribing or creating a paid account?
- true: free to read in full online (free course, free online book, open docs, blog post, free PDF)
- false: paywalled, a landing page for a paid book or course, requires purchase, or a product you buy

**is_learning_material**: Does the resource teach or explain a subject or skill (tutorial, course, guide, explainer, lecture notes, textbook, reference documentation, interactive lesson)? A single well-written blog post that explains a topic counts. A news report, opinion piece, product page, company homepage, personal homepage, tool, dataset or discussion thread does not.
- true: teaches or explains a subject: tutorial, course, guide, explainer, textbook, reference docs
- false: news, opinion, product or company page, tool, personal homepage, discussion, announcement

**is_evergreen**: Would the resource still be worth reading years later, regardless of current events?
- true: timeless material a student could learn from in any year
- false: tied to a news event, a release, a current controversy, a deal or a date

**is_video**: Is the resource primarily video (a video, lecture recording, video course or channel)?
- true: primarily video content
- false: primarily text, code or interactive content

**is_code_repo**: Is the resource primarily a source-code repository or software download rather than written teaching material?
- true: source-code repository, package, or software download
- false: written or interactive teaching material (even if it contains code samples)

**is_paid_book**: Is the resource a page about a printed or paid book (publisher page, book landing page, shop listing) rather than the free text itself?
- true: page selling or describing a book you must buy
- false: the free full text is online, or it is not a book at all

## Composite question (clef only, for comparison)

Is this a free online learning resource that a curious student could use to learn or understand a subject: a tutorial, course, guide, explainer, free online book, reference documentation or a single explanatory blog post? It must be free to read in full, not primarily video, not a code repository, not a page for a paid book, and not tied to a news event.

## Topics

- `programming`: a programming language, coding practice, software craft, testing, tooling
- `computer_science`: algorithms, data structures, compilers, theory of computation, CS curricula
- `systems`: operating systems, networking, distributed systems, performance, security, low level
- `web`: web development, HTML, CSS, JavaScript frameworks, browsers, HTTP, web design
- `data`: databases, SQL, data engineering, data analysis, statistics in practice
- `ml_ai`: machine learning, deep learning, AI, LLMs
- `mathematics`: mathematics, pure or applied, including statistics theory and probability
- `science`: physics, chemistry, biology, astronomy, earth science, medicine
- `hardware`: electronics, embedded systems, computer architecture, making, robotics
- `design`: visual design, UX, typography, graphics, game design, art
- `writing`: writing, communication, language learning, speaking, teaching
- `business`: economics, finance, investing, startups, management, product, marketing
- `humanities`: history, philosophy, law, politics, psychology, society
- `self_improvement`: how to learn, careers, productivity, health, thinking, decision making
- `other`: none of the above

## Resource types

- `course`: structured course or curriculum with lessons or modules
- `tutorial`: step-by-step guide or how-to for a specific skill
- `free_book`: a complete book or textbook readable online for free
- `reference`: reference documentation, manual, cheat sheet, specification
- `explainer`: a single article or blog post that explains a concept
- `interactive`: interactive lessons, visualisations, exercises, playground
- `collection`: a curated list or index of other resources
- `other`: none of the above or not a learning resource

## Difficulty

- 0: beginner: no prior background needed
- 1: intermediate: assumes some programming, maths or domain background
- 2: advanced: graduate, research or professional level

