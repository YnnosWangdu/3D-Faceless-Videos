"""Text-to-speech backends with word timings.

synth(text, out_wav, voice_cfg) -> {"duration": s, "words": [{"w","start","end"}], "backend": name}

Backends (voice.backend):
  auto        edge -> piper -> say -> espeak (first that works; never silently drops the voice)
  edge        Microsoft Edge neural voices, free, needs internet   (pip install edge-tts)
  elevenlabs  ELEVENLABS_API_KEY, exact word timings, premium quality
  openai      OPENAI_API_KEY, gpt-4o-mini-tts (timings estimated)
  piper       offline neural TTS, voice.model = path/to/voice.onnx (pip install piper-tts)
  say         macOS built-in
  espeak      espeak-ng (robotic, offline, last resort)
  silent      no audio, duration estimated from word count (layout previews / tests)
User-recorded audio: set "audio": "path/to/file.wav" on a beat instead.
"""
import asyncio
import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request

WPS = 2.6  # average narration speed, words per second


def clean(text):
    return re.sub(r"\s+", " ", text.replace("*", "")).strip()


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, **kw)


def to_wav(src, dst):
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-ac", "1", "-ar", "48000", dst])


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=nw=1:nk=1", path], capture_output=True, text=True).stdout
    return float(out.strip() or 0)


def speech_bounds(wav, total):
    """Find where speech starts/ends (trim leading/trailing silence) for timing estimates."""
    try:
        r = subprocess.run(["ffmpeg", "-v", "info", "-i", wav, "-af",
                            "silencedetect=noise=-38dB:d=0.12", "-f", "null", "-"],
                           capture_output=True, text=True).stderr
        starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r)]
        ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r)]
        a = ends[0] if starts and starts[0] < 0.02 and ends else 0.0
        b = starts[-1] if starts and (not ends or starts[-1] > ends[-1]) else total
        if b - a > 0.3:
            return a, b
    except Exception:
        pass
    return 0.0, total


def estimate_words(text, start, end):
    """Spread words over [start,end] proportionally to length (+ pause after punctuation)."""
    words = text.split()
    if not words:
        return []
    weights = [len(w) + 2 + (3 if w[-1] in ".!?" else 1.5 if w[-1] in ",;:" else 0) for w in words]
    tot = sum(weights)
    out, t = [], start
    for w, wt in zip(words, weights):
        d = (end - start) * wt / tot
        out.append({"w": w, "start": round(t, 3), "end": round(t + d * 0.92, 3)})
        t += d
    return out


# ------------------------------------------------------------------ backends
def _edge(text, wav, v):
    import edge_tts

    voice = v.get("voice", "en-US-AndrewMultilingualNeural")
    words, audio = [], bytearray()

    async def go():
        kw = dict(rate=v.get("rate", "+0%"), pitch=v.get("pitch", "+0Hz"))
        try:
            com = edge_tts.Communicate(text, voice, boundary="WordBoundary", **kw)
        except TypeError:
            com = edge_tts.Communicate(text, voice, **kw)
        async for ch in com.stream():
            if ch["type"] == "audio":
                audio.extend(ch["data"])
            elif ch["type"] == "WordBoundary":
                s = ch["offset"] / 1e7
                words.append({"w": ch["text"], "start": round(s, 3),
                              "end": round(s + ch["duration"] / 1e7, 3)})

    asyncio.run(go())
    if not audio:
        raise RuntimeError("edge-tts returned no audio")
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(audio)
    to_wav(f.name, wav)
    os.unlink(f.name)
    return words or None


def _elevenlabs(text, wav, v):
    key = os.environ["ELEVENLABS_API_KEY"]
    vid = v.get("voice", "JBFqnCBsd6RMkjVDRZzb")
    body = {"text": text, "model_id": v.get("model", "eleven_multilingual_v2")}
    if v.get("settings"):
        body["voice_settings"] = v["settings"]
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/with-timestamps?output_format=mp3_44100_128",
        data=json.dumps(body).encode(), headers={"xi-api-key": key, "Content-Type": "application/json"})
    res = json.load(urllib.request.urlopen(req, timeout=120))
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(base64.b64decode(res["audio_base64"]))
    to_wav(f.name, wav)
    os.unlink(f.name)
    al = res.get("alignment") or {}
    chars = al.get("characters") or []
    st, en = al.get("character_start_times_seconds") or [], al.get("character_end_times_seconds") or []
    words, cur, cs, ce = [], "", None, None
    for c, s, e in zip(chars, st, en):
        if c.isspace():
            if cur:
                words.append({"w": cur, "start": cs, "end": ce})
            cur, cs = "", None
            continue
        if cs is None:
            cs = s
        cur += c
        ce = e
    if cur:
        words.append({"w": cur, "start": cs, "end": ce})
    return words or None


def _openai(text, wav, v):
    key = os.environ["OPENAI_API_KEY"]
    body = {"model": v.get("model", "gpt-4o-mini-tts"), "voice": v.get("voice", "onyx"),
            "input": text, "response_format": "wav"}
    if v.get("instructions"):
        body["instructions"] = v["instructions"]
    req = urllib.request.Request("https://api.openai.com/v1/audio/speech", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    data = urllib.request.urlopen(req, timeout=120).read()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(data)
    to_wav(f.name, wav)
    os.unlink(f.name)
    return None


def _piper(text, wav, v):
    model = v.get("model") or os.environ.get("PIPER_MODEL")
    if not model:
        raise RuntimeError("piper needs voice.model (path to .onnx) or PIPER_MODEL")
    exe = shutil.which("piper") or "piper"
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        pass
    run([exe, "--model", model, "--output_file", f.name], input=text.encode())
    to_wav(f.name, wav)
    os.unlink(f.name)
    return None


def _say(text, wav, v):
    if not shutil.which("say"):
        raise RuntimeError("say not available")
    with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as f:
        pass
    cmd = ["say", "-o", f.name]
    if v.get("voice") and "Neural" not in v.get("voice", ""):
        cmd += ["-v", v["voice"]]
    run(cmd + [text])
    to_wav(f.name, wav)
    os.unlink(f.name)
    return None


def _espeak(text, wav, v):
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        raise RuntimeError("espeak not available")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        pass
    run([exe, "-v", v.get("espeak_voice", "en-us"), "-s", "165", "-w", f.name, text])
    to_wav(f.name, wav)
    os.unlink(f.name)
    return None


def _silent(text, wav, v):
    d = max(1.0, len(text.split()) / WPS + 0.2)
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
         "-t", f"{d:.3f}", wav])
    return estimate_words(text, 0.1, d - 0.1)


BACKENDS = {"edge": _edge, "elevenlabs": _elevenlabs, "openai": _openai, "piper": _piper,
            "say": _say, "espeak": _espeak, "silent": _silent}
AUTO = ["edge", "piper", "say", "espeak"]


def available():
    out = {}
    try:
        import edge_tts  # noqa: F401
        out["edge"] = "installed (needs internet)"
    except Exception:
        out["edge"] = None
    out["elevenlabs"] = "key set" if os.environ.get("ELEVENLABS_API_KEY") else None
    out["openai"] = "key set" if os.environ.get("OPENAI_API_KEY") else None
    out["piper"] = shutil.which("piper") and (os.environ.get("PIPER_MODEL") or "installed (set voice.model)")
    out["say"] = shutil.which("say")
    out["espeak"] = shutil.which("espeak-ng") or shutil.which("espeak")
    out["silent"] = "always"
    return out


def synth(text, wav, v=None):
    v = v or {}
    text = clean(text)
    want = v.get("backend", "auto")
    order = AUTO if want == "auto" else [want]
    errs = []
    for name in order:
        try:
            words = BACKENDS[name](text, wav, v)
            d = duration(wav)
            if not words:
                a, b = speech_bounds(wav, d)
                words = estimate_words(text, a, b)
            return {"duration": d, "words": words, "backend": name}
        except Exception as e:  # try the next backend
            errs.append(f"{name}: {e}")
    raise RuntimeError("all TTS backends failed (use voice.backend='silent' for a voiceless preview):\n  "
                       + "\n  ".join(errs))


def from_file(src, text, wav):
    """User-supplied recording for a beat."""
    to_wav(src, wav)
    d = duration(wav)
    a, b = speech_bounds(wav, d)
    return {"duration": d, "words": estimate_words(clean(text), a, b) if text else [], "backend": "file"}


def whisper_align(wav, text):
    """Optional: exact word timings with faster-whisper (pip install faster-whisper)."""
    from faster_whisper import WhisperModel
    m = WhisperModel(os.environ.get("FV_WHISPER_MODEL", "base.en"), compute_type="int8")
    segs, _ = m.transcribe(wav, word_timestamps=True, initial_prompt=clean(text))
    return [{"w": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)}
            for s in segs for w in (s.words or [])]
