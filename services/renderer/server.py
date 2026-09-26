"""Local stand-in for HeyGen's /v3/videos API.

Same request/response shape as HeyGen, so n8n can switch to the real API
by changing RENDER_BASE_URL and the API key. No lip sync: it renders the
avatar image (or a plain background) with an audio waveform over it.
"""
import json
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
        if self.path != "/v3/videos":
            return self.send_json(404, {"error": {"code": "not_found", "message": self.path}})
        if not self.authorised():
            return
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except json.JSONDecodeError:
            return self.send_json(400, {"error": {"code": "bad_json", "message": "body is not valid JSON"}})
        missing = [f for f in ("avatar_id", "audio_url") if not req.get(f)]
        if missing:
            return self.send_json(400, {"error": {"code": "invalid_parameter",
                                                  "message": f"missing: {', '.join(missing)}"}})
        job_id = uuid.uuid4().hex
        with lock:
            jobs[job_id] = {"id": job_id, "status": "waiting", "title": req.get("title", ""),
                            "created_at": int(time.time())}
        threading.Thread(target=render, args=(job_id, req), daemon=True).start()
        self.send_json(200, {"data": {"video_id": job_id, "status": "waiting", "output_format": "mp4"}})

    def do_GET(self):
        if self.path.startswith("/v3/videos/"):
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
