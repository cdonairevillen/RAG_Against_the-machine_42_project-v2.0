"""Film domain (Phase 9): the parts that need no video or GPU."""
from src.rag.sources.film import (
    Line, Shot, clip_of, film_id, frame_name, parse_srt, render, stamp,
    tidy_caption,
)

SRT = """1
00:00:47,960 --> 00:00:52,840
<i>Once upon a time
there was a lovely princess.</i>

2
00:01:02,067 --> 00:01:05,616
{\\an8}What are you doing
in my swamp?

3
00:01:10,000 --> 00:01:11,000

"""


def test_parse_srt_cleans_markup_and_joins_lines() -> None:
    lines = parse_srt(SRT)
    assert [ln.text for ln in lines] == [
        "Once upon a time there was a lovely princess.",
        "What are you doing in my swamp?",
    ]
    assert lines[0].start == 47.96
    assert round(lines[1].end, 3) == 65.616


def test_stamp_and_frame_name() -> None:
    assert stamp(3725.9) == "01:02:05"
    assert frame_name(12.3456) == "000012346.jpg"


def test_film_id_is_url_safe() -> None:
    assert film_id("Shrek 2 (2004)") == "shrek-2-2004"


def test_clip_of_spans_every_section_of_a_chunk() -> None:
    text = ("## 00:12:30 - 00:13:05\n\nScene: x\n\n"
            "## 00:13:05 - 00:13:40\n\nDialogue:\n- \"y\"\n")
    assert clip_of(text) == (750.0, 820.0)
    assert clip_of("no header here") is None


def test_tidy_caption_drops_film_names_and_cut_sentences() -> None:
    text = ("This is a scene from the animated film *Some Film*. "
            "A green ogre stands in a swamp. He holds a torch. "
            "Behind him a donkey")
    assert tidy_caption(text) == ("A green ogre stands in a swamp. "
                                  "He holds a torch.")


def test_render_groups_shots_into_timed_sections() -> None:
    shots = [Shot(0.0, 20.0, [1.0]), Shot(20.0, 40.0, [21.0]),
             Shot(40.0, 50.0, [41.0])]
    captions = {frame_name(1.0): "A swamp.", frame_name(21.0): "A door.",
                frame_name(41.0): "A castle."}
    lines = [Line(5.0, 6.0, "Hello."), Line(45.0, 46.0, "Bye.")]
    text = render("Test (2000)", shots, lines, captions, "srt")
    assert text.startswith("# Test (2000)\n")
    assert "## 00:00:00 - 00:00:40" in text
    assert "Scene: A swamp. A door." in text
    assert "## 00:00:40 - 00:00:50" in text
    assert '- "Bye."' in text


def test_enrichment_windows_names_and_render() -> None:
    from src.rag.sources.film import transcript_sections
    from src.rag.sources.film_enrich import (
        characters, enrich_film, parse_summary, render, windows,
    )

    secs = [(float(i * 60), float(i * 60 + 60), f"## part {i}")
            for i in range(7)]
    assert [(w[0], w[1]) for w in windows(secs)] == [
        (0.0, 180.0), (180.0, 360.0), (360.0, 420.0)]

    names, summary = parse_summary(
        "**SUMMARY:** Donkey is sold.\nThe guards  take him.\n\n"
        "CHARACTERS: Lord Farquaad, Donkey, unnamed guard, Princess, "
        "Woman in Green Dress, Farquaad, Shrek, none",
        '- "By order of Lord Farquaad!" - "A talking donkey."')
    assert names == ["Lord Farquaad", "Donkey"]
    assert summary == "Donkey is sold. The guards take him."

    people = characters([
        {"characters": ["Lord Farquaad"]}, {"characters": ["Donkey"]},
        {"characters": ["Farquaad", "Donkey"]}, {"characters": ["Fiona"]},
    ])
    assert people["farquaad"]["first"] == 0
    assert people["donkey"]["windows"] == [1, 2]
    assert "fiona" not in people  # named in a single window

    secs = [(a, b, t + " Shrek!") for a, b, t in secs]
    replies = iter(["SUMMARY: A.\nCHARACTERS: Shrek", "SUMMARY: B.\n"
                    "CHARACTERS: Shrek", "SUMMARY: C.\nCHARACTERS: none",
                    "Shrek is an ogre."])
    result = enrich_film("T (2000)", secs, lambda s, u, n: next(replies))
    scenes, people_text = render(result)
    assert "## 00:00:00 - 00:03:00 (scene summary)" in scenes
    assert "## Character: Shrek" in people_text
    assert "First mentioned in the scene 00:00:00 - 00:03:00." \
        in people_text
    assert clip_of(scenes) == (0.0, 420.0)
    # Summary headers are never read back as transcript.
    film = "## 00:00:00 - 00:01:00\n\nDialogue:\n- \"x\"\n\n" + scenes
    assert len(transcript_sections(film)) == 1


def test_enrichment_merges_names_and_finds_first_mention() -> None:
    from src.rag.sources.film_enrich import (
        characters, evidence_lines, parse_profile,
    )

    summaries = [{"characters": []}, {"characters": ["Puss"]},
                 {"characters": ["Puss In Boots", "Donkey"]},
                 {"characters": ["Donkey"]}]
    texts = ['- "A talking donkey."', "x", "y", "z"]
    people = characters(summaries, texts)
    assert set(people) == {"puss in boots", "donkey"}
    assert people["puss in boots"]["windows"] == [1, 2]
    # The code finds "donkey" in the first window's text, though the
    # model listed him from the third one.
    assert people["donkey"]["first"] == 0
    assert people["donkey"]["first_listed"] == 2

    groups = [(0.0, 180.0, '- "Hi, Donkey!"\n- "Bye."'),
              (180.0, 360.0, '- "donkey again"')]
    assert evidence_lines(["donkey"], groups) == [
        '- 00:00:00: "Hi, Donkey!"', '- 00:03:00: "donkey again"']

    assert parse_profile("**PROFILE:** A cat.\n") == "A cat."
    assert parse_profile("PROFILE: Lillian is not mentioned in the "
                         "summaries.") == ""


def test_enrichment_aliases_join_suffixes_and_count_mentions() -> None:
    from src.rag.sources.film_enrich import characters

    summaries = [{"characters": ["Cat"]}, {"characters": ["Godmother"]},
                 {"characters": ["Fairy Godmother", "Puss In Boots"]},
                 {"characters": ["Puss In Boots"]}]
    texts = ["Look! A little cat.", '- "Puss... in Boots!"', "", ""]
    people = characters(summaries, texts)
    assert set(people) == {"fairy godmother", "puss in boots"}
    assert people["fairy godmother"]["aliases"] == ["fairy godmother",
                                                    "godmother"]
    # "Cat" is a common noun; "Puss... in Boots!" still counts.
    assert people["puss in boots"]["windows"] == [1, 2, 3]


def test_valid_sources_add_scene_summary_and_profile() -> None:
    from src.rag.sources.film import valid_sources

    text = ("## 00:00:00 - 00:00:30\n\nDialogue:\n- \"Hi, Donkey!\"\n\n"
            "## 00:00:30 - 00:01:00\n\nDialogue:\n- \"Bye.\"\n")
    extra = ("## 00:00:00 - 00:03:00 (scene summary)\n\nThey meet.\n\n"
             "## Character: Donkey\n\nA talking donkey.\n")
    first = text.index("Hi, Donkey!")
    scenes, people = extra.split("## Character")
    people = "## Character" + people
    found = valid_sources(text, ("f.md", first, first + 11), ["Donkey"],
                          [("f.summaries.md", scenes),
                           ("f.characters.md", people)])
    assert found == [["f.md", first, first + 11],
                     ["f.summaries.md", 0, len(scenes)],
                     ["f.characters.md", 0, len(people)]]


def test_summaries_file_title_clip_and_chunks() -> None:
    from src.config import SourceConfig
    from src.rag.ingestion.chunkers import chunk_markdown_sections
    from src.rag.sources.film import is_summary
    from src.rag.sources.film import title_of
    from src.rag.sources.film_enrich import render

    data = {"windows": [{"start": 0.0, "end": 180.0,
                         "characters": ["Donkey"], "summary": "They meet."}],
            "characters": {"donkey": {
                "name": "Donkey", "aliases": ["donkey"], "windows": [0],
                "first": 0, "first_listed": 0, "first_section": [30.0, 60.0],
                "profile": "A talking donkey."},
                "fiona": {
                "name": "Fiona", "aliases": ["fiona"], "windows": [0],
                "first": 0, "first_listed": 0, "first_section": None,
                "profile": "A princess."}}}
    scenes, people = render(data)
    assert "## Character:" not in scenes and "scene summary" not in people
    # The profile plays the first section that names him, not a window.
    assert clip_of(people.split("## Character: Fiona")[0]) == (30.0, 60.0)
    # One chunk per profile: never packed with another one.
    chunks = chunk_markdown_sections("Shrek (2001).characters.md", people)
    assert [c.text.split("\n", 1)[0] for c in chunks] == [
        "## Character: Donkey", "## Character: Fiona"]
    assert is_summary("data/film/Shrek (2001).summaries.md")
    assert is_summary("data/film/Shrek (2001).characters.md")
    assert not is_summary("data/film/Shrek (2001).md")
    assert film_id("Shrek (2001)") == "shrek-2001"
    for name in ("Shrek (2001).summaries.md", "Shrek (2001).characters.md",
                 "Shrek (2001).md"):
        assert title_of(f"data/film/{name}") == "Shrek (2001)"
    source = SourceConfig(root="r", include=[".md"],
                          default_chunker="markdown_headers_packed",
                          chunkers={".characters.md": "markdown_sections"})
    assert source.chunker_for("a/X.characters.md") == "markdown_sections"
    assert source.chunker_for("a/X.summaries.md") == "markdown_headers_packed"
    assert source.chunker_for("a/X.md") == "markdown_headers_packed"
