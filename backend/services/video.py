from pathlib import Path
import subprocess

def create_clip(input_path: Path, start: float, end: float, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration=max(1.0,end-start)
    vf='scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1'
    cmd=['ffmpeg','-y','-ss',str(start),'-i',str(input_path),'-t',str(duration),'-vf',vf,'-c:v','libx264','-preset','veryfast','-crf','23','-c:a','aac','-b:a','128k','-movflags','+faststart',str(output_path)]
    p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    if p.returncode!=0: raise RuntimeError(p.stderr[-4000:])
    return output_path
