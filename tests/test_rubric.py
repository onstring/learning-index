from hnlearn import rubric


def test_clef_questions_shape():
    q = rubric.clef_questions()
    assert set(q) >= {"is_free_learning_resource", "topic", "resource_type", "difficulty",
                      "free_to_access", "is_paid_book"}
    assert q["topic"]["type"] == "choice" and set(q["topic"]["criteria"]) == set(rubric.TOPICS)
    assert q["difficulty"]["type"] == "score" and len(q["difficulty"]["criteria"]) == 3
    for name, spec in q.items():
        assert spec["instructions"], name
        if spec["type"] == "noul":
            assert set(spec["criteria"]) == {"true", "false"}


def test_keep_rule_uses_threshold():
    assert rubric.keep(0.7, threshold=0.7)
    assert not rubric.keep(0.69, threshold=0.7)


def test_state_text_includes_context_and_omits_missing():
    cand = {"nurl": "teachyourselfcs.com", "host": "teachyourselfcs.com", "ppl": 5, "yrs": 3,
            "y0": 2019, "y1": 2021, "story_title": "Teach Yourself CS", "story_score": 250,
            "evidence": [{"author": "alice", "date": "2019-01-01",
                          "excerpt": "I highly recommend it"}]}
    fetched = {"status": 200, "title": "Teach Yourself CS", "description": None,
               "snippet": "Study all nine subjects"}
    s = rubric.state_text(cand, fetched)
    assert "URL: https://teachyourselfcs.com" in s
    assert "Page title: Teach Yourself CS" in s
    assert "Page description" not in s
    assert "Page text: Study all nine subjects" in s
    assert "Recommended by 5 distinct" in s and "2019-2021" in s
    assert "HN comment 1: I highly recommend it" in s


def test_state_text_reports_failed_fetch():
    cand = {"nurl": "a.com", "host": "a.com", "ppl": 3, "yrs": 1, "y0": 2020, "y1": 2020,
            "story_title": None, "story_score": None, "evidence": []}
    s = rubric.state_text(cand, {"status": 403, "title": None, "description": None,
                                 "snippet": None})
    assert "Fetch status: 403" in s
    s = rubric.state_text(cand, None)
    assert "Fetch status" not in s


def test_state_text_drops_bot_check_pages():
    cand = {"nurl": "a.com", "host": "a.com", "ppl": 3, "yrs": 1, "y0": 2020, "y1": 2020,
            "story_title": "Real Name", "story_score": 5, "evidence": []}
    s = rubric.state_text(cand, {"status": 200, "title": "Just a moment...",
                                 "description": "x", "snippet": "Enable JavaScript and cookies"})
    assert "Just a moment" not in s and "Page text" not in s
    assert "bot-check" in s and "Hacker News story title: Real Name" in s


def test_blurb_schema_and_prompt():
    schema = rubric.blurb_schema()
    assert schema["required"] == ["title", "blurb"]
    assert "Hacker News" in rubric.blurb_system()


def test_rubric_markdown_lists_topics():
    md = rubric.markdown()
    assert "`programming`" in md and "## Topics" in md
