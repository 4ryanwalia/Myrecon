# Optional project tools

- `maigret_harness.py` and `maigret_web_import.py` are research/import
  helpers for reviewing public platform catalogues. They contact external
  services when run and write generated data under ignored `tools/out/`.
  Review output and platform evidence before changing a catalogue.
- `create_reel_audio.ps1` generates the four sample dialogue WAV files on
  Windows when the named System.Speech voices are available.
- `build_library_reel.py` rebuilds the eight-second synthetic reel from the
  checked-in `output/library-reel/` image and WAV files. Install
  `imageio-ffmpeg` first, then run `python tools/build_library_reel.py`.
  Pass `--source path/to/scene.png` to replace the scene image.

The reel and social artwork are illustrative assets. They do not show a live
product scan.
