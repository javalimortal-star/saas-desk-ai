from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CAPTURE_DIR = ROOT / "docs" / "demo-frames"
OUTPUT = ROOT / "docs" / "demo.gif"
FRAME_NAMES = [
    "01-public-form.png",
    "02-protocol.png",
    "03-login.png",
    "04-dashboard.png",
    "05-assisted-analysis.png",
    "06-resolution.png",
    "07-swagger.png",
]


def main():
    frames = [Image.open(CAPTURE_DIR / name).convert("RGB") for name in FRAME_NAMES]
    target_size = frames[0].size
    if any(frame.size != target_size for frame in frames):
        frames = [frame.resize(target_size, Image.Resampling.LANCZOS) for frame in frames]
    frames[0].save(
        OUTPUT,
        save_all=True,
        append_images=frames[1:],
        duration=[2200, 1800, 2200, 2600, 3000, 2600, 2600],
        loop=0,
        optimize=True,
    )


if __name__ == "__main__":
    main()
