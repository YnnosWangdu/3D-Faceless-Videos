"""Word-timed captions -> ASS (burned in by ffmpeg/libass) and SRT (for upload).

Caption styles (captions.style):
  pop      short chunks, active word coloured + slightly enlarged (TikTok/Shorts look)
  karaoke  whole chunk visible, words light up as they are spoken
  clean    plain chunk, no highlight (documentary look)
  box      plain chunk on a translucent box
"""
import re


def ass_color(hex_, alpha=0):
    h = hex_.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ts(t):
    t = max(0.0, t)
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def srt_ts(t):
    t = max(0.0, t)
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def esc(s):
    return s.replace("\\", "").replace("{", "(").replace("}", ")")


def chunk_words(words, max_words, max_chars):
    """Split a beat's words into readable chunks, breaking after punctuation."""
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        n_chars = sum(len(x["w"]) + 1 for x in cur)
        if len(cur) >= max_words or n_chars >= max_chars or re.search(r"[.!?;:,]$", w["w"]):
            chunks.append(cur)
            cur = []
    if cur:
        if chunks and len(cur) == 1 and len(chunks[-1]) < max_words + 1:
            chunks[-1] += cur
        else:
            chunks.append(cur)
    return chunks


def build(beats_words, W, H, cfg, highlight="#FFE600"):
    """beats_words: list of word-lists (global timeline seconds), one list per beat."""
    portrait = H > W
    style = cfg.get("style", "pop")
    upper = cfg.get("uppercase", style == "pop")
    font = cfg.get("font", "Montserrat Black")
    size = int(cfg.get("size", 0) or (H * (0.042 if portrait else 0.055)))
    max_words = int(cfg.get("words_per_line", 3 if portrait else 6))
    max_chars = int(cfg.get("max_chars", 18 if portrait else 38))
    pos = cfg.get("position", "lower" if portrait else "bottom")
    margin_v = {"center": int(H * 0.5 - size / 2), "lower": int(H * 0.30), "bottom": int(H * 0.08),
                "top": int(H * 0.8)}.get(pos, int(H * 0.3))
    text_c = ass_color(cfg.get("color", "#FFFFFF"))
    hi_c = ass_color(cfg.get("highlight", highlight))
    outline_c = ass_color(cfg.get("outline_color", "#000000"))
    border_style, outline, shadow, back = 1, max(3, size // 12), max(1, size // 30), ass_color("#000000", 0x60)
    if style == "box":
        border_style, outline, shadow, back = 3, size // 5, 0, ass_color("#000000", 0x50)
        outline_c = back
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,{font},{size},{text_c},{hi_c},{outline_c},{back},-1,0,0,0,100,100,1,0,{border_style},{outline},{shadow},2,{int(W * 0.08)},{int(W * 0.08)},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines, srt = [], []
    for words in beats_words:
        chunks = chunk_words(words, max_words, max_chars)
        for ci, ch in enumerate(chunks):
            c0 = ch[0]["start"]
            nxt = chunks[ci + 1][0]["start"] if ci + 1 < len(chunks) else ch[-1]["end"] + 0.35
            c1 = max(ch[-1]["end"], min(nxt, ch[-1]["end"] + 0.35))
            disp = [(esc(w["w"].upper() if upper else w["w"])) for w in ch]
            srt.append((c0, c1, " ".join(w["w"] for w in ch)))
            if style in ("clean", "box"):
                lines.append(f"Dialogue: 0,{ts(c0)},{ts(c1)},Main,,0,0,0,,{' '.join(disp)}")
                continue
            for i, w in enumerate(ch):
                s = c0 if i == 0 else w["start"]
                e = ch[i + 1]["start"] if i + 1 < len(ch) else c1
                if e <= s:
                    continue
                parts = []
                for j, d in enumerate(disp):
                    if j == i:
                        pop = r"\fscx112\fscy112" if style == "pop" else ""
                        parts.append(f"{{\\c{hi_c}{pop}}}{d}{{\\r}}")
                    elif style == "karaoke" and j < i:
                        parts.append(f"{{\\c{hi_c}}}{d}{{\\r}}")
                    else:
                        parts.append(d)
                intro = r"{\fad(60,0)\t(0,90,\fscx100\fscy100)\fscx85\fscy85}" if i == 0 and style == "pop" else ""
                lines.append(f"Dialogue: 0,{ts(s)},{ts(e)},Main,,0,0,0,,{intro}{' '.join(parts)}")
    srt_txt = "".join(f"{i + 1}\n{srt_ts(a)} --> {srt_ts(b)}\n{t}\n\n" for i, (a, b, t) in enumerate(srt))
    return head + "\n".join(lines) + "\n", srt_txt
