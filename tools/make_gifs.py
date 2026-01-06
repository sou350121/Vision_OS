"""
make_gifs.py

Create a high-quality GIF preview from a video segment using palettegen/paletteuse.
Works on Windows without system ffmpeg by using imageio-ffmpeg.

Example:
  python tools/make_gifs.py --in docs/assets/demo1.mp4 --out docs/assets/demo1_10s.gif --seconds 10 --fps 15 --width 960
"""

from __future__ import annotations

import argparse
import os
import subprocess

import imageio_ffmpeg


def build_vf(fps: int, width: int) -> str:
    # Palette-based conversion produces much better quality than direct GIF encoding.
    # - fps: keeps motion reasonable without exploding file size
    # - scale: preserve aspect ratio (-1), use lanczos for crisp edges
    # - dither: bayer provides good detail for UI footage
    return (
        f"fps={fps},scale={width}:-1:flags=lanczos,"
        "split[s0][s1];"
        "[s0]palettegen=max_colors=256:reserve_transparent=0[p];"
        "[s1][p]paletteuse=dither=bayer:bayer_scale=5"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input video path")
    ap.add_argument("--out", dest="out", required=True, help="Output gif path")
    ap.add_argument("--start", type=float, default=0.0, help="Start time (seconds)")
    ap.add_argument("--seconds", type=float, default=10.0, help="Duration (seconds)")
    ap.add_argument("--fps", type=int, default=15, help="GIF fps")
    ap.add_argument("--width", type=int, default=960, help="GIF width (px), keep aspect ratio")
    args = ap.parse_args()

    if not os.path.exists(args.inp):
        raise SystemExit(f"Missing input: {args.inp}")

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    vf = build_vf(args.fps, args.width)

    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        str(args.start),
        "-t",
        str(args.seconds),
        "-i",
        args.inp,
        "-vf",
        vf,
        "-loop",
        "0",
        args.out,
    ]

    subprocess.check_call(cmd)
    size = os.path.getsize(args.out)
    print(f"WROTE {args.out} ({size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


