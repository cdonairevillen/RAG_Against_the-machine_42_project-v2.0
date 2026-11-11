"""Film domain (Phase 9): a film as text the RAG can search.

Input: one folder per film under the films directory (default
data/raw/film/), named after the film ("Shrek (2001)"), holding the
video and, optionally, its subtitles (.srt). Other files are ignored.

Each film becomes one Markdown file, data/film/<folder>.md, with one
section per stretch of the film:

    # Shrek (2001)

    ## 00:12:30 - 00:13:05

    Scene: An ogre walks through a swamp at sunset...

    Dialogue:
    - "What are you doing in my swamp?"

The section header carries the timestamp, so the ordinary Markdown
chunker and the character offsets used by the evaluator keep working.

Steps (each cached under data/film/.work/<folder>/, so a re-run only
redoes what changed):
1. Dialogue: the .srt next to the video, else a text subtitle track
   inside it, else a Whisper transcription (faster-whisper, VAD on).
2. Shots: cuts found by comparing colour histograms of frames sampled
   a few times per second (OpenCV); one frame is saved per shot (and
   every MAX_GAP seconds in long shots).
3. Scenes: every saved frame is described by a small vision-language
   model (Qwen3-VL-2B or Florence-2).
4. Markdown: shots grouped into sections of at least SECTION_SECONDS,
   with their descriptions and the dialogue spoken inside them.

Heavy dependencies (faster-whisper, the VLM) are optional: `uv sync
--extra film`. Everything runs offline. While the film domain is on,
the web can play the clip of a source (/film/<id>/video, DEC-44).
"""
import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterator, Optional

FILMS_DIR = "data/raw/film"
OUTPUT_DIR = "data/film"
WORK_DIR = ".work"
VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v")
TEXT_SUBTITLE_CODECS = ("subrip", "srt", "ass", "ssa", "mov_text",
                        "webvtt", "text")

# Shot detection: frames sampled per second, histogram distance that
# counts as a cut, shortest shot, and the longest stretch without a
# saved frame.
SAMPLE_FPS = 4.0
CUT_THRESHOLD = 0.45
MIN_SHOT = 1.0
MAX_GAP = 20.0
FRAME_OFFSET = 0.5
FRAME_WIDTH = 640
# Sections of the Markdown file: consecutive shots are merged until a
# section lasts at least this long.
SECTION_SECONDS = 30.0
# Scene descriptions kept per section (one sentence each).
SCENES_PER_SECTION = 3

WHISPER_MODEL = "large-v3-turbo"
CAPTIONERS = {
    "qwen3-vl-2b": "Qwen/Qwen3-VL-2B-Instruct",
    "florence-2-large": "florence-community/Florence-2-large",
}
DEFAULT_CAPTIONER = "qwen3-vl-2b"
CAPTION_PROMPT = (
    "Describe this film frame in at most two sentences: who is visible "
    "(by appearance), where they are and what they are doing. Quote any "
    "readable text. Never name the film, the studio or the characters."
)
# Tested on Gulliver (FASE_9.md 9a): the models still named films now
# and then; a sentence that does so is dropped.
NAMING = re.compile(
    r"\b(scene|still|frame|image) from\b|\bfrom the (animated )?(film|movie)"
    r"|\b(Disney|Pixar|DreamWorks)\b|\*[^*]+\*", re.IGNORECASE)
MAX_SENTENCES = 2


@dataclass
class Line:
    """A line of dialogue (seconds from the start of the film)."""

    start: float
    end: float
    text: str


@dataclass
class Shot:
    """A shot and the frames saved from it (seconds)."""

    start: float
    end: float
    frames: list[float]


def stamp(seconds: float) -> str:
    """Seconds as hh:mm:ss."""
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def frame_name(seconds: float) -> str:
    """File name of a saved frame (milliseconds, sortable)."""
    return f"{int(round(seconds * 1000)):09d}.jpg"


# --- what the web shows -------------------------------------------------

# The generated summaries of a film live in their own file, one chunk
# per section (DEC-55): never packed with the film or with each other.
SUMMARIES_SUFFIX = ".summaries.md"
# A character profile has no header time: its clip is the first section
# of the film that names the character (film_enrich.render()).
FIRST_NAMED = re.compile(
    r"^First named in the film at (\d{2}):(\d{2}):(\d{2}) - "
    r"(\d{2}):(\d{2}):(\d{2})\.", re.M)
# Transcript sections and, with the suffix, the generated scene
# summaries (film_enrich.py), so the web plays the clip of both.
SECTION_HEADER = re.compile(
    r"^## (\d{2}):(\d{2}):(\d{2}) - (\d{2}):(\d{2}):(\d{2})"
    r"(?: \(scene summary\))?\s*$", re.M)


def film_id(title: str) -> str:
    """URL-safe id of a film ("Shrek 2 (2004)" -> "shrek-2-2004"): the
    web asks for a video by this id, never by its path."""
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def title_of(file_path: str) -> str:
    """Film title of a chunk's file (data/film/<Title>.md, or its
    generated summaries, <Title>.summaries.md)."""
    name = os.path.basename(file_path)
    if name.endswith(SUMMARIES_SUFFIX):
        return name[:-len(SUMMARIES_SUFFIX)]
    return os.path.splitext(name)[0]


def is_summary(file_path: str) -> bool:
    """Whether a chunk comes from a film's generated summaries."""
    return file_path.endswith(SUMMARIES_SUFFIX)


def clip_of(text: str) -> Optional[tuple[float, float]]:
    """(start, end) seconds spanned by the sections of a chunk's text,
    or None if it holds no section header."""
    found = SECTION_HEADER.findall(text) or FIRST_NAMED.findall(text)
    if not found:
        return None
    first, last = found[0], found[-1]
    start = int(first[0]) * 3600 + int(first[1]) * 60 + int(first[2])
    end = int(last[3]) * 3600 + int(last[4]) * 60 + int(last[5])
    return float(start), float(max(end, start))


def videos(films_dir: str = FILMS_DIR) -> dict[str, str]:
    """Video path of every film, by film_id()."""
    return {film_id(title): video for title, video in find_films(films_dir)}


# --- input -------------------------------------------------------------

def find_films(films_dir: str = FILMS_DIR) -> list[tuple[str, str]]:
    """(title, video path) of every film folder, sorted by title.

    The title is the folder name. A folder without a video is skipped;
    with several, the largest is the film.
    """
    films: list[tuple[str, str]] = []
    if not os.path.isdir(films_dir):
        return films
    for name in sorted(os.listdir(films_dir)):
        folder = os.path.join(films_dir, name)
        if not os.path.isdir(folder):
            continue
        videos = [os.path.join(folder, f) for f in os.listdir(folder)
                  if f.lower().endswith(VIDEO_EXTENSIONS)]
        if videos:
            films.append((name, max(videos, key=os.path.getsize)))
    return films


def subtitle_file(video: str) -> Optional[str]:
    """The .srt next to the video: same name first, else the only one."""
    folder = os.path.dirname(video)
    same = os.path.splitext(video)[0] + ".srt"
    if os.path.isfile(same):
        return same
    srts = sorted(f for f in os.listdir(folder) if f.lower().endswith(".srt"))
    return os.path.join(folder, srts[0]) if len(srts) == 1 else None


# --- dialogue ----------------------------------------------------------

TAGS = re.compile(r"<[^>]+>|\{[^}]*\}")
SRT_TIME = re.compile(
    r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)"
)


def clean_line(text: str) -> str:
    """Subtitle text without markup, on one line."""
    text = TAGS.sub("", text.replace("\\N", " "))
    return " ".join(text.split())


def srt_seconds(h: str, m: str, s: str, frac: str) -> float:
    return float(int(h) * 3600 + int(m) * 60 + int(s)
                 + int(frac) / 10 ** len(frac))


def parse_srt(text: str) -> list[Line]:
    """Lines of a SubRip file (blocks: index, times, text)."""
    lines = []
    for block in re.split(r"\r?\n\s*\r?\n", text.strip()):
        rows = block.strip().splitlines()
        for i, row in enumerate(rows):
            match = SRT_TIME.search(row)
            if match:
                g = match.groups()
                body = clean_line(" ".join(rows[i + 1:]))
                if body:
                    lines.append(Line(srt_seconds(*g[:4]),
                                      srt_seconds(*g[4:]), body))
                break
    return lines


def embedded_subtitles(video: str) -> list[Line]:
    """Lines of the first text subtitle track inside the video, if any.

    Image subtitles (DVD, Blu-ray PGS) are not text: they are skipped,
    and the film falls back to Whisper.
    """
    import av

    lines: list[Line] = []
    with av.open(video) as container:
        streams = [s for s in container.streams.subtitles
                   if s.codec_context.name in TEXT_SUBTITLE_CODECS]
        if not streams:
            return lines
        stream = streams[0]
        base = stream.time_base or 0
        for packet in container.demux(stream):
            if packet.pts is None:
                continue
            start = float(packet.pts * base)
            end = start + float((packet.duration or 0) * base)
            for subtitle in packet.decode():
                for rect in getattr(subtitle, "rects", subtitle):
                    raw = getattr(rect, "text", "") or ""
                    ass = getattr(rect, "ass", b"") or b""
                    if isinstance(ass, bytes):
                        ass = ass.decode("utf-8", "ignore")
                    if ass and not raw:
                        # Dialogue: Layer,Start,End,Style,...,Text
                        raw = ass.split(",", 8)[-1]
                    body = clean_line(raw)
                    if body:
                        lines.append(Line(start, max(end, start), body))
    return lines


def cuda_dlls() -> None:
    """Let CTranslate2 (faster-whisper) find the CUDA libraries that
    torch already ships (Windows only; elsewhere the loader finds them).
    """
    if os.name != "nt":
        return
    import torch

    os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__),
                                      "lib"))


def transcribe(video: str, model_name: str = WHISPER_MODEL) -> list[Line]:
    """Whisper transcription of the film's audio (VAD filter on)."""
    cuda_dlls()
    import torch
    from faster_whisper import WhisperModel

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = WhisperModel(model_name, device=device,
                         compute_type="float16" if device == "cuda"
                         else "int8")
    segments, _ = model.transcribe(video, vad_filter=True, beam_size=5)
    lines = [Line(s.start, s.end, clean_line(s.text)) for s in segments
             if clean_line(s.text)]
    del model
    return lines


def dialogue(video: str, whisper_model: str = WHISPER_MODEL
             ) -> tuple[str, list[Line]]:
    """The film's dialogue and where it came from ('srt', 'embedded'
    or 'whisper:<model>')."""
    srt = subtitle_file(video)
    if srt:
        with open(srt, encoding="utf-8-sig", errors="replace") as fh:
            lines = parse_srt(fh.read())
        if lines:
            return "srt", lines
    lines = embedded_subtitles(video)
    if lines:
        return "embedded", lines
    return f"whisper:{whisper_model}", transcribe(video, whisper_model)


# --- shots -------------------------------------------------------------

def frame_histogram(image: Any) -> Any:
    """Normalised hue-saturation histogram of a BGR image."""
    import cv2

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
    return cv2.normalize(hist, hist).flatten()


def detect_shots(video: str, frames_dir: str) -> list[Shot]:
    """Cut the film into shots and save frames to describe.

    Frames are sampled SAMPLE_FPS times per second and compared with
    the previous sample (Bhattacharyya distance of colour histograms);
    a distance above CUT_THRESHOLD starts a new shot. One frame is saved
    FRAME_OFFSET seconds into each shot (past the cut's blur), and one
    more every MAX_GAP seconds in long shots.
    """
    import av
    import cv2

    os.makedirs(frames_dir, exist_ok=True)
    shots: list[Shot] = []
    current: Optional[Shot] = None
    previous = None
    next_sample = 0.0
    last_saved = -MAX_GAP
    time = 0.0
    with av.open(video) as container:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        ratio = stream.codec_context.height / stream.codec_context.width
        for frame in container.decode(stream):
            if frame.time is None or frame.time < next_sample:
                continue
            time = float(frame.time)
            next_sample = time + 1.0 / SAMPLE_FPS
            small = frame.to_ndarray(width=128, height=72, format="bgr24")
            hist = frame_histogram(small)
            cut = previous is not None and cv2.compareHist(
                previous, hist, cv2.HISTCMP_BHATTACHARYYA) > CUT_THRESHOLD
            previous = hist
            if current is None or (cut and time - current.start >= MIN_SHOT):
                if current is not None:
                    current.end = time
                    shots.append(current)
                current = Shot(time, time, [])
            due_first = not current.frames and \
                time - current.start >= FRAME_OFFSET
            due_gap = current.frames and time - last_saved >= MAX_GAP
            if due_first or due_gap:
                frame.to_image(
                    width=FRAME_WIDTH, height=int(FRAME_WIDTH * ratio) // 2 * 2
                ).save(os.path.join(frames_dir, frame_name(time)),
                       quality=90)
                current.frames.append(time)
                last_saved = time
    if current is not None:
        current.end = time
        shots.append(current)
    return shots


# --- scene descriptions ------------------------------------------------

class Captioner:
    """Describes frames with a small vision-language model."""

    def __init__(self, name: str = DEFAULT_CAPTIONER,
                 batch_size: int = 8) -> None:
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        if name not in CAPTIONERS:
            raise ValueError(f"Unknown captioner '{name}' "
                             f"(choose from {', '.join(CAPTIONERS)})")
        self.name = name
        self.batch_size = batch_size
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if self.device == "cuda" else torch.float32
        model_id = CAPTIONERS[name]
        self.processor = AutoProcessor.from_pretrained(model_id)
        if name.startswith("qwen"):
            self.processor.tokenizer.padding_side = "left"
        model = AutoModelForImageTextToText.from_pretrained(model_id,
                                                            dtype=dtype)
        self.model = model.to(self.device).eval()  # type: ignore[arg-type]
        self.dtype = dtype

    def describe(self, images: list[Any]) -> list[str]:
        """One description per image (greedy decoding)."""
        out: list[str] = []
        for i in range(0, len(images), self.batch_size):
            batch = images[i:i + self.batch_size]
            if self.name.startswith("qwen"):
                out.extend(self.describe_qwen(batch))
            else:
                out.extend(self.describe_florence(batch))
        return out

    def describe_qwen(self, images: list[Any]) -> list[str]:
        import torch

        messages = [[{"role": "user", "content": [
            {"type": "image"}, {"type": "text", "text": CAPTION_PROMPT},
        ]}] for _ in images]
        texts = [self.processor.apply_chat_template(
            m, tokenize=False, add_generation_prompt=True) for m in messages]
        inputs = self.processor(text=texts, images=images, padding=True,
                                return_tensors="pt").to(self.device)
        with torch.inference_mode():
            ids = self.model.generate(**inputs, max_new_tokens=96,
                                      do_sample=False)
        ids = ids[:, inputs["input_ids"].shape[1]:]
        return [clean_line(t) for t in self.processor.batch_decode(
            ids, skip_special_tokens=True)]

    def describe_florence(self, images: list[Any]) -> list[str]:
        import torch

        task = "<MORE_DETAILED_CAPTION>"
        inputs = self.processor(text=[task] * len(images), images=images,
                                return_tensors="pt").to(self.device,
                                                        self.dtype)
        with torch.inference_mode():
            ids = self.model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=80, do_sample=False, num_beams=3,
            )
        return [clean_line(t) for t in self.processor.batch_decode(
            ids, skip_special_tokens=True)]

    def close(self) -> None:
        """Free the GPU memory."""
        import torch

        del self.model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


SENTENCE = re.compile(r"(?<=[.!?])\s+")


def tidy_caption(text: str) -> str:
    """A description without the sentences that name a film, cut at
    its last complete sentence and to MAX_SENTENCES."""
    sentences = [s for s in SENTENCE.split(clean_line(text)) if s]
    if sentences and not sentences[-1].endswith((".", "!", "?", '"')):
        sentences = sentences[:-1]
    kept = [s for s in sentences if not NAMING.search(s)]
    return " ".join(kept[:MAX_SENTENCES])


def describe_frames(frames_dir: str, times: list[float],
                    captioner: Captioner,
                    done: dict[str, str]) -> dict[str, str]:
    """Descriptions keyed by frame name; frames already in `done` are
    kept (a re-run only describes the new ones)."""
    from PIL import Image

    todo = [t for t in times if frame_name(t) not in done]
    result = dict(done)
    for i in range(0, len(todo), 64):
        chunk = todo[i:i + 64]
        images = [Image.open(os.path.join(frames_dir, frame_name(t)))
                  .convert("RGB") for t in chunk]
        for t, text in zip(chunk, captioner.describe(images)):
            result[frame_name(t)] = tidy_caption(text)
        print(f"  described {min(i + 64, len(todo))}/{len(todo)} frames")
    return result


# --- Markdown ----------------------------------------------------------

Section = tuple[float, float, list[str], list[str]]


def sections(shots: list[Shot], lines: list[Line],
             captions: dict[str, str]) -> Iterator[Section]:
    """(start, end, descriptions, dialogue) of each section: shots
    merged until the section lasts SECTION_SECONDS. A line belongs to
    the section where it starts."""
    groups: list[list[Shot]] = []
    for shot in shots:
        if groups and groups[-1][-1].end - groups[-1][0].start \
                < SECTION_SECONDS:
            groups[-1].append(shot)
        else:
            groups.append([shot])
    for group in groups:
        start, end = group[0].start, group[-1].end
        # The longest shots describe the section best; their first
        # sentence only, in film order (FASE_9.md 9b: more text drowned
        # the dialogue in the search).
        longest = sorted(group, key=lambda s: s.end - s.start,
                         reverse=True)[:SCENES_PER_SECTION]
        seen: list[str] = []
        for shot in sorted(longest, key=lambda s: s.start):
            for t in shot.frames[:1]:
                text = SENTENCE.split(captions.get(frame_name(t), ""))[0]
                if text and text not in seen:
                    seen.append(text)
        said = [ln.text for ln in lines if start <= ln.start < end]
        yield start, end, seen, said


def render(title: str, shots: list[Shot], lines: list[Line],
           captions: dict[str, str], dialogue_source: str) -> str:
    """The film's Markdown file."""
    out = [f"# {title}", "",
           f"Film transcript: dialogue ({dialogue_source}) and scene "
           f"descriptions, by time.", ""]
    # Dialogue before the first shot (or after the last) still counts.
    if shots:
        shots[0].start = min(shots[0].start, *(ln.start for ln in lines)) \
            if lines else shots[0].start
        shots[-1].end = max(shots[-1].end, *(ln.end for ln in lines)) \
            if lines else shots[-1].end
    for start, end, seen, said in sections(shots, lines, captions):
        if not seen and not said:
            continue
        out += [f"## {stamp(start)} - {stamp(end)}", ""]
        if seen:
            out += [f"Scene: {' '.join(seen)}", ""]
        if said:
            out += ["Dialogue:"] + [f'- "{s}"' for s in said] + [""]
    return "\n".join(out)


# --- driver ------------------------------------------------------------

def load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)


def prepare(films_dir: str = FILMS_DIR, output_dir: str = OUTPUT_DIR,
            captioner_name: str = DEFAULT_CAPTIONER,
            whisper_model: str = WHISPER_MODEL,
            only: Optional[str] = None,
            scenes: bool = True) -> list[str]:
    """Build the Markdown file of every film (see the module docstring).

    Args:
        films_dir: One folder per film (video + optional .srt).
        output_dir: Where the .md files (the source root) go.
        captioner_name: Vision-language model for the scenes.
        whisper_model: Used only for films without text subtitles.
        only: Title of a single film to (re)build.
        scenes: False skips the scene descriptions (no GPU needed); the
            Markdown then holds the dialogue only.

    Returns:
        The Markdown files written.
    """
    written = []
    captioner: Optional[Captioner] = None
    for title, video in find_films(films_dir):
        if only and title != only:
            continue
        print(f"{title}: {video}")
        work = os.path.join(output_dir, WORK_DIR, title)
        frames_dir = os.path.join(work, "frames")
        os.makedirs(work, exist_ok=True)

        path = os.path.join(work, "dialogue.json")
        if os.path.isfile(path):
            data = load_json(path)
        else:
            source, lines = dialogue(video, whisper_model)
            data = {"source": source, "lines": [asdict(x) for x in lines]}
            save_json(path, data)
        lines = [Line(**x) for x in data["lines"]]
        print(f"  dialogue: {len(lines)} lines ({data['source']})")

        path = os.path.join(work, "shots.json")
        if os.path.isfile(path):
            shots = [Shot(**x) for x in load_json(path)]
        else:
            shots = detect_shots(video, frames_dir)
            save_json(path, [asdict(s) for s in shots])
        times = [t for s in shots for t in s.frames]
        print(f"  shots: {len(shots)}, frames: {len(times)}")

        path = os.path.join(work, f"captions-{captioner_name}.json")
        captions = load_json(path) if os.path.isfile(path) else {}
        if scenes and any(frame_name(t) not in captions for t in times):
            if captioner is None:
                captioner = Captioner(captioner_name)
            captions = describe_frames(frames_dir, times, captioner,
                                       captions)
            save_json(path, captions)

        out = os.path.join(output_dir, f"{title}.md")
        text = render(title, shots, lines, captions, data["source"])
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        written.append(out)
        if write_summaries(output_dir, title, work):
            written.append(summaries_path(output_dir, title))
        print(f"  wrote {out}")
    if captioner is not None:
        captioner.close()
    return written


# --- enrichment (film_enrich.py) ----------------------------------------

GENERATED = "\n# Generated summaries"


def summaries_path(output_dir: str, title: str) -> str:
    """The film's generated summaries file."""
    return os.path.join(output_dir, f"{title}{SUMMARIES_SUFFIX}")


def write_summaries(output_dir: str, title: str, work: str,
                    data: Optional[dict] = None) -> bool:
    """Write the film's summaries file from `data` or, by default, its
    newest cached enrichment. Returns False when there is none."""
    from src.rag.sources import film_enrich

    if data is None:
        path = film_enrich.newest_cache(work)
        if path is None:
            return False
        data = load_json(path)
    with open(summaries_path(output_dir, title), "w", encoding="utf-8",
              newline="\n") as fh:
        fh.write(film_enrich.render(data, data.get("model", "")))
    return True


def transcript_sections(text: str) -> list[tuple[float, float, str]]:
    """(start, end, text) of every transcript section of a film's
    Markdown file (generated summaries excluded)."""
    text = text.split(GENERATED, 1)[0]
    found = [m for m in SECTION_HEADER.finditer(text)
             if "(scene summary)" not in m.group(0)]
    out = []
    for i, match in enumerate(found):
        g = [int(x) for x in match.groups()]
        end_at = found[i + 1].start() if i + 1 < len(found) else len(text)
        out.append((float(g[0] * 3600 + g[1] * 60 + g[2]),
                    float(g[3] * 3600 + g[4] * 60 + g[5]),
                    text[match.start():end_at].strip()))
    return out


def enrich(output_dir: str = OUTPUT_DIR, only: Optional[str] = None,
           model: Optional[str] = None,
           provider: str = "local") -> list[str]:
    """Add the generated summaries (scene summaries and character
    profiles, film_enrich.py) to every film's Markdown file. Needs the
    files from prepare(); GPU-heavy (a local LLM), so the API should be
    stopped. Cached: a re-run only generates what is missing.

    Returns:
        The Markdown files rewritten.
    """
    from src.rag.sources import film_enrich

    model = model or film_enrich.DEFAULT_MODEL
    generate: Optional[film_enrich.Generate] = None
    written = []
    for name in sorted(os.listdir(output_dir)):
        title, ext = os.path.splitext(name)
        if ext != ".md" or name.endswith(SUMMARIES_SUFFIX) \
                or (only and title != only):
            continue
        path = os.path.join(output_dir, name)
        with open(path, encoding="utf-8", newline="") as fh:
            base = fh.read().split(GENERATED, 1)[0].rstrip("\n")
        work = os.path.join(output_dir, WORK_DIR, title)
        os.makedirs(work, exist_ok=True)
        cache = film_enrich.cache_path(work, model)
        cached = load_json(cache) if os.path.isfile(cache) else None
        if generate is None:
            generate = film_enrich.local_generator(model) \
                if provider == "local" \
                else film_enrich.api_generator(model, provider)
        print(f"{title}: enriching with {model} ({provider})")
        result = film_enrich.enrich_film(
            title, transcript_sections(base), generate, cached)
        result["model"] = model
        save_json(cache, result)
        # Earlier runs appended the summaries to the film's file.
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(base + "\n")
        write_summaries(output_dir, title, work, result)
        written.append(summaries_path(output_dir, title))
        print(f"  wrote {summaries_path(output_dir, title)}")
    return written


# --- benchmark ---------------------------------------------------------

BENCH_DIR = "bench/datasets/film"
BENCH_LANGUAGES = ("en", "es")


def build_bench(output_dir: str = OUTPUT_DIR,
                bench_dir: str = BENCH_DIR) -> int:
    """Write the film datasets (RagDataset, one per language) from
    bench_dir/questions.json, locating every evidence in its film's
    Markdown file (it must appear there exactly once).

    Returns:
        Number of questions per language.

    Raises:
        ValueError: If an evidence is missing or ambiguous.
    """
    from src.models import (
        AnsweredQuestion, MinimalSource, RagDataset, UnansweredQuestion,
    )
    from src.rag.sources.cv import locate

    questions = load_json(os.path.join(bench_dir, "questions.json"))[
        "questions"]
    texts: dict[str, str] = {}
    spans = {}
    for q in questions:
        path = f"{output_dir}/{q['film']}.md"
        if path not in texts:
            with open(path, encoding="utf-8", newline="") as fh:
                texts[path] = fh.read()
        spans[q["id"]] = (path, *locate(texts[path], q["evidence"],
                                        q["id"], path))
    for lang in BENCH_LANGUAGES:
        answered = [
            AnsweredQuestion(
                question_id=q["id"], question=q[lang], answer=q["answer"],
                sources=[MinimalSource(
                    file_path=spans[q["id"]][0],
                    first_character_index=spans[q["id"]][1],
                    last_character_index=spans[q["id"]][2],
                )],
            )
            for q in questions
        ]
        unanswered = [UnansweredQuestion(question_id=a.question_id,
                                         question=a.question)
                      for a in answered]
        name = f"dataset_{lang}_film.json"
        for folder, items in (("AnsweredQuestions", answered),
                              ("UnansweredQuestions", unanswered)):
            os.makedirs(os.path.join(bench_dir, folder), exist_ok=True)
            with open(os.path.join(bench_dir, folder, name), "w",
                      encoding="utf-8", newline="\n") as fh:
                fh.write(RagDataset(rag_questions=list(items))
                         .model_dump_json(indent=2))
    valid = {}
    for q in questions:
        extra = summaries_path(output_dir, q["film"])
        summary_text = ""
        if os.path.isfile(extra):
            with open(extra, encoding="utf-8", newline="") as fh:
                summary_text = fh.read()
        valid[q["id"]] = valid_sources(
            texts[spans[q["id"]][0]], spans[q["id"]],
            q.get("characters", []), extra.replace(os.sep, "/"),
            summary_text)
    save_json(os.path.join(bench_dir, VALID_SOURCES), valid)
    return len(questions)


# Every source that answers a question (FASE_9.md 9b, your decision): the
# evidence, the generated scene summary of its window and the profiles of
# the characters it is about ("characters" in questions.json). Used by
# the complementary "any valid source" recall of the film suite; the 42
# evaluator (one source per question, all required) is not changed.
VALID_SOURCES = "valid_sources.json"
ANY_HEADER = re.compile(r"^## .*$", re.M)
PROFILE_HEADER = re.compile(r"^## Character: (.+?)\s*$", re.M)


def valid_sources(text: str, evidence: tuple[str, int, int],
                  characters: list[str], summaries_file: str = "",
                  summaries: str = "") -> list[list[Any]]:
    """[file_path, first, last] of every valid source of a question: its
    evidence span in the film (`text`), and from the film's summaries
    file (`summaries`, at `summaries_file`) the scene summary whose
    window holds the evidence and the profiles of `characters` (matched
    by name key)."""
    from src.rag.sources.film_enrich import name_key

    path, first, last = evidence
    out: list[list[Any]] = [[path, first, last]]
    headers = list(ANY_HEADER.finditer(summaries))

    def section(match: re.Match) -> list[Any]:
        later = [h.start() for h in headers if h.start() > match.start()]
        return [summaries_file, match.start(),
                later[0] if later else len(summaries)]

    before = list(SECTION_HEADER.finditer(text[:first]))
    if before:
        g = [int(x) for x in before[-1].groups()]
        at = g[0] * 3600 + g[1] * 60 + g[2]
        for m in SECTION_HEADER.finditer(summaries):
            h = [int(x) for x in m.groups()]
            if h[0] * 3600 + h[1] * 60 + h[2] <= at \
                    < h[3] * 3600 + h[4] * 60 + h[5]:
                out.append(section(m))
    wanted = {name_key(c) for c in characters}
    for m in PROFILE_HEADER.finditer(summaries):
        if name_key(m.group(1)) in wanted:
            out.append(section(m))
    return out
