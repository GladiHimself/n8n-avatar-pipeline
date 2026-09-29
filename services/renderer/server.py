"""Local media service for the avatar pipeline.

/v3/videos  - stand-in for HeyGen's API (same request/response shape), so n8n
              can switch to the real API by changing RENDER_BASE_URL and the
              key. No lip sync: avatar image (or plain background) + waveform.
/v1/edits   - post-production: burned-in captions, intro/outro cards and an
              optional music bed. Same async job shape (submit -> poll -> url).
"""
import json
import shutil
import tempfile
import textwrap
import os
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API_KEY = os.environ.get("RENDERER_API_KEY", "")
AVATAR_DIR = "/avatars"
AUDIO_ROOT = "/files"
OUT_DIR = "/renders"
PORT = 8080
MUSIC_DIR = "/music"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
BG = "0x1f2937"
SIZES = {
    "9:16": {"720p": (720, 1280), "1080p": (1080, 1920)},
    "16:9": {"720p": (1280, 720), "1080p": (1920, 1080)},
    "1:1": {"720p": (720, 720), "1080p": (1080, 1080)},
}

jobs = {}
lock = threading.Lock()


def update(job_id, **fields):
    with lock:
        jobs[job_id].update(fields)


def render(job_id, req):
    update(job_id, status="processing")
    started = time.time()
    try:
        avatar_id = req["avatar_id"]
        if avatar_id == "fail":
            raise RuntimeError("simulated render failure (avatar_id=fail)")

        audio = os.path.realpath(req["audio_url"])
        if not audio.startswith(AUDIO_ROOT + "/") or not os.path.isfile(audio):
            raise RuntimeError(f"audio not found under {AUDIO_ROOT}: {req['audio_url']}")

        w, h = SIZES.get(req.get("aspect_ratio", "9:16"), SIZES["9:16"]).get(
            req.get("resolution", "720p"), (720, 1280))
        image = os.path.join(AVATAR_DIR, f"{avatar_id}.png")
        wave_h = h // 6
        wave = f"[1:a]showwaves=s={w}x{wave_h}:mode=cline:scale=sqrt:draw=full:colors=white[wave]"

        if os.path.isfile(image):
            inputs = ["-loop", "1", "-i", image]
            bg = (f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
                  f"crop={w}:{h},format=yuv420p[bg]")
        else:
            inputs = ["-f", "lavfi", "-i", f"color=c=0x1f2937:s={w}x{h}"]
            bg = "[0:v]format=yuv420p[bg]"

        out = os.path.join(OUT_DIR, f"{job_id}.mp4")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-i", audio,
               "-filter_complex",
               f"{bg};{wave};[bg][wave]overlay=0:{h - wave_h - h // 10}:shortest=1,format=yuv420p[v]",
               "-map", "[v]", "-map", "1:a", "-r", "25",
               "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
               "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", out]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip()[-500:] or "ffmpeg failed")

        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", out], capture_output=True, text=True)
        update(job_id, status="completed",
               video_url=f"http://renderer:{PORT}/renders/{job_id}.mp4",
               duration=round(float(probe.stdout.strip() or 0), 2),
               render_seconds=round(time.time() - started, 1))
    except Exception as exc:  # report every failure through the status API
        update(job_id, status="failed", failure_code="render_error",
               failure_message=str(exc))


def srt_time(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def ffmpeg(args, timeout=600):
    result = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args],
                            capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip()[-500:] or "ffmpeg failed")


def probe(path, entries):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-show_entries", entries, "-of", "default=nw=1:nk=1", path],
                         capture_output=True, text=True).stdout.split()
    return out


def card(path, text, seconds, w, h, workdir, name):
    """A plain background card with centred, wrapped text and silent audio."""
    txt = os.path.join(workdir, f"{name}.txt")
    with open(txt, "w", encoding="utf-8") as f:
        f.write("\n".join(textwrap.wrap(text.strip(), width=18)) or " ")
    size = w // 13
    draw = (f"drawtext=fontfile={FONT}:textfile={txt}:fontcolor=white:fontsize={size}:"
            f"line_spacing={size // 3}:text_align=C:x=(w-text_w)/2:y=(h-text_h)/2")
    ffmpeg(["-f", "lavfi", "-i", f"color=c={BG}:s={w}x{h}:r=25:d={seconds}",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-vf", f"{draw},format=yuv420p", "-t", str(seconds),
            "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-b:a", "128k",
            "-shortest", path])


def edit(job_id, req):
    update(job_id, status="processing")
    started = time.time()
    workdir = tempfile.mkdtemp(prefix=f"edit-{job_id}-")
    try:
        src = os.path.realpath(req["video_path"])
        if not src.startswith(AUDIO_ROOT + "/video/") or not os.path.isfile(src):
            raise RuntimeError(f"video not found under {AUDIO_ROOT}/video: {req['video_path']}")
        w, h = (int(v) for v in probe(src, "stream=width,height")[:2])

        # 1. captions -> SRT -> burned into the main video
        cues = req.get("cues") or []
        srt = os.path.join(workdir, "captions.srt")
        with open(srt, "w", encoding="utf-8") as f:
            for i, cue in enumerate(cues, 1):
                f.write(f"{i}\n{srt_time(float(cue['start']))} --> {srt_time(float(cue['end']))}\n"
                        f"{str(cue['text']).strip()}\n\n")
        main = os.path.join(workdir, "main.mp4")
        style = ("FontName=DejaVu Sans,Bold=1,FontSize=16,PrimaryColour=&H00FFFFFF,"
                 "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,"
                 "Alignment=2,MarginV=110")
        vf = f"subtitles={srt}:force_style='{style}'" if cues else "null"
        ffmpeg(["-i", src, "-vf", f"{vf},format=yuv420p", "-r", "25",
                "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-b:a", "128k",
                "-ar", "44100", "-ac", "1", main])

        # 2. intro / outro cards
        intro = os.path.join(workdir, "intro.mp4")
        outro = os.path.join(workdir, "outro.mp4")
        card(intro, req.get("title") or " ", 1.5, w, h, workdir, "intro")
        card(outro, req.get("outro_text") or "Follow for more", 2, w, h, workdir, "outro")

        # 3. join, then lay the music bed (if any) under everything
        music = os.path.join(MUSIC_DIR, "bed.mp3")
        use_music = bool(req.get("music")) and os.path.isfile(music)
        inputs = ["-i", intro, "-i", main, "-i", outro]
        graph = ("[0:v][0:a][1:v][1:a][2:v][2:a]concat=n=3:v=1:a=1[v][voice]")
        if use_music:
            inputs += ["-stream_loop", "-1", "-i", music]
            graph += (";[3:a]aformat=sample_rates=44100:channel_layouts=mono,volume=0.12[bed]"
                      ";[voice][bed]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]")
        else:
            graph += ";[voice]anull[a]"
        out = os.path.join(OUT_DIR, f"edit-{job_id}.mp4")
        ffmpeg([*inputs, "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart", out])

        duration = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", out], capture_output=True, text=True).stdout.strip()
        update(job_id, status="completed",
               video_url=f"http://renderer:{PORT}/renders/edit-{job_id}.mp4",
               duration=round(float(duration or 0), 2), captions=len(cues),
               music="bed.mp3" if use_music else "none",
               render_seconds=round(time.time() - started, 1))
    except Exception as exc:
        update(job_id, status="failed", failure_code="edit_error", failure_message=str(exc))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


class Handler(BaseHTTPRequestHandler):
    def send_json(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authorised(self):
        if API_KEY and self.headers.get("X-Api-Key") != API_KEY:
            self.send_json(401, {"error": {"code": "unauthorized", "message": "bad or missing X-Api-Key"}})
            return False
        return True

    def do_POST(self):
        routes = {"/v3/videos": (render, ("avatar_id", "audio_url")),
                  "/v1/edits": (edit, ("video_path",))}
        if self.path not in routes:
            return self.send_json(404, {"error": {"code": "not_found", "message": self.path}})
        if not self.authorised():
            return
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except json.JSONDecodeError:
            return self.send_json(400, {"error": {"code": "bad_json", "message": "body is not valid JSON"}})
        worker, required = routes[self.path]
        missing = [f for f in required if not req.get(f)]
        if missing:
            return self.send_json(400, {"error": {"code": "invalid_parameter",
                                                  "message": f"missing: {', '.join(missing)}"}})
        job_id = uuid.uuid4().hex
        with lock:
            jobs[job_id] = {"id": job_id, "status": "waiting", "title": req.get("title", ""),
                            "created_at": int(time.time())}
        threading.Thread(target=worker, args=(job_id, req), daemon=True).start()
        self.send_json(200, {"data": {"video_id": job_id, "status": "waiting", "output_format": "mp4"}})

    def do_GET(self):
        if self.path.startswith(("/v3/videos/", "/v1/edits/")):
            if not self.authorised():
                return
            with lock:
                job = dict(jobs.get(self.path.rsplit("/", 1)[-1], {}))
            if not job:
                return self.send_json(404, {"error": {"code": "not_found", "message": "unknown video_id"}})
            return self.send_json(200, {"data": job})
        if self.path.startswith("/renders/"):
            path = os.path.join(OUT_DIR, os.path.basename(self.path))
            if not os.path.isfile(path):
                return self.send_json(404, {"error": {"code": "not_found", "message": "no such render"}})
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(os.path.getsize(path)))
            self.end_headers()
            with open(path, "rb") as f:
                while chunk := f.read(1 << 16):
                    self.wfile.write(chunk)
            return
        if self.path == "/health":
            return self.send_json(200, {"ok": True})
        self.send_json(404, {"error": {"code": "not_found", "message": self.path}})


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"renderer listening on :{PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
