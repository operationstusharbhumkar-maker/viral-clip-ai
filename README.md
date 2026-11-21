# Viral Clip AI — Connected SaaS V3

This version connects the SaaS account/subscription layer to the real local AI video pipeline.

## Flow
YouTube URL → yt-dlp download → Whisper transcription → highlight scoring → 3 x 25–45s clips → 9:16 FFmpeg output → My Clips.

The first 3 generated clips are free. The current project keeps Pro users unblocked; Razorpay payment wiring can be added next.

## Windows setup
1. Install Python and FFmpeg. Make sure `ffmpeg` works in CMD.
2. Open CMD:

```cmd
cd C:\viral-clip-ai-saas-connected\backend
python -m venv .venv
.venv\Scripts\activate
python -m pip install -U pip
pip install -r requirements.txt
python -m uvicorn app:app --reload
```

3. Open http://127.0.0.1:8000

If Python 3.14 gives a package-specific install problem, use Python 3.12 for the venv; the application code itself is standard Python/FastAPI.

## Notes
- Whisper is local CPU inference, so transcription can be slow on an 8 GB machine.
- Generated files are stored under `backend/output/<user_id>/<job_id>/`.
- SQLite is for local development. Production should use PostgreSQL + object storage + a background worker/queue.
- The highlight engine is transcript-based heuristic scoring in this version; it is not yet a multimodal vision model.
