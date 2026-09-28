from pathlib import Path
import shutil
import subprocess
import imageio_ffmpeg

root = Path(__file__).resolve().parents[1]
assets = root / "output" / "library-reel"
assets.mkdir(parents=True, exist_ok=True)

source = Path(r"C:\Users\91966\.codex\generated_images\01a0ac46-7d63-7b40-8862-591040770c15\exec-082d9646-79d9-46b2-89bc-ee4c81b3448d.png")
image = assets / "library-scene.png"
shutil.copy2(source, image)

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
