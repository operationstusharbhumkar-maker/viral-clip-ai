from pathlib import Path
import yt_dlp

def download_video(url: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    template = str(out_dir / '%(id)s.%(ext)s')
    opts = {
        'format': 'bv*[height<=1080]+ba/b[height<=1080]/b',
        'merge_output_format': 'mp4',
        'outtmpl': template,
        'noplaylist': True,
        'quiet': False,
        'retries': 3,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = Path(ydl.prepare_filename(info))
        if path.suffix.lower() != '.mp4':
            mp4 = path.with_suffix('.mp4')
            if mp4.exists(): path = mp4
        if not path.exists():
            candidates = sorted(out_dir.glob(f"{info.get('id','*')}.*"), key=lambda p: p.stat().st_mtime, reverse=True)
            if candidates: path = candidates[0]
        if not path.exists(): raise FileNotFoundError('Downloaded video file was not found.')
        return path
