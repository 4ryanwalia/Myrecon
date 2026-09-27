"""Build the eight-second library reel from the checked-in scene and audio."""

import argparse
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
assets = root / "output" / "library-reel"
assets.mkdir(parents=True, exist_ok=True)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, help="Optional replacement scene image")
args = parser.parse_args()
image = assets / "library-scene.png"
if args.source and args.source.resolve() != image.resolve():
    shutil.copy2(args.source, image)
if not image.is_file():
    parser.error(f"scene image missing: {image}")

try:
    import imageio_ffmpeg
except ImportError:
    parser.error("install imageio-ffmpeg with: python -m pip install imageio-ffmpeg")

ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
out = assets / "myrecon-library-reel.mp4"

filter_complex = (
    "[0:v]scale=1216:2160,crop=1080:1920:x='68+10*sin(t*1.1)':y='120+8*cos(t*0.9)',"
    "zoompan=z='1.0+0.00035*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=200:s=1080x1920:fps=25,"
    "eq=brightness='0.006*sin(t*2.3)':contrast=1.01,format=yuv420p[v];"
    "[1:a]adelay=0|0,volume=0.92[a1];"
    "[2:a]adelay=2550|2550,volume=0.92[a2];"
    "[3:a]adelay=5200|5200,volume=1.08[a3];"
    "[4:a]adelay=7050|7050,volume=0.88[a4];"
    "anoisesrc=color=pink:amplitude=0.006:duration=8[room];"
    "[a1][a2][a3][a4][room]amix=inputs=5:duration=longest:dropout_transition=0,"
    "highpass=f=90,lowpass=f=9000,alimiter=limit=0.9[a]"
)

cmd = [
    ffmpeg, "-y", "-loop", "1", "-i", str(image),
    "-i", str(assets / "kabir-1.wav"),
    "-i", str(assets / "meera-1.wav"),
    "-i", str(assets / "kabir-2.wav"),
    "-i", str(assets / "meera-2.wav"),
    "-filter_complex", filter_complex,
    "-map", "[v]", "-map", "[a]", "-t", "8",
    "-c:v", "libx264", "-preset", "medium", "-crf", "20",
    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out),
]
subprocess.run(cmd, check=True)
print(out)
