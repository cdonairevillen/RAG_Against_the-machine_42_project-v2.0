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
