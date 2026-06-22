"""Generate Tauri desktop icons from the JuGuang logo assets.

Outputs next to this file:
  - tray-template.png / tray-template@2x.png for the macOS status bar
  - icon.iconset/* and icon.icns for macOS app icons
  - icon.ico and Square*Logo.png / StoreLogo.png for Windows
  - standard PNG sizes referenced by tauri.conf.json
"""

from __future__ import annotations

import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ICON_DIR = Path(__file__).resolve().parent
COLOR_SVG = ICON_DIR / "juguang-logo-color.svg"
BLACK_SVG = ICON_DIR / "juguang-logo-black.svg"

APP_PNG_SIZES = {
    "32x32.png": 32,
    "64x64.png": 64,
    "128x128.png": 128,
    "128x128@2x.png": 256,
    "512x512.png": 512,
    "icon.png": 512,
    "macos-icon-1024.png": 1024,
    "Square30x30Logo.png": 30,
    "Square44x44Logo.png": 44,
    "Square71x71Logo.png": 71,
    "Square89x89Logo.png": 89,
    "Square107x107Logo.png": 107,
    "Square142x142Logo.png": 142,
    "Square150x150Logo.png": 150,
    "Square284x284Logo.png": 284,
    "Square310x310Logo.png": 310,
    "StoreLogo.png": 50,
}

ICONSET_SIZES = {
    "icon_16x16.png": 16,
    "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32,
    "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128,
    "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256,
    "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512,
    "icon_512x512@2x.png": 1024,
}

ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def run(*cmd: object) -> None:
    subprocess.run([str(part) for part in cmd], check=True, stdout=subprocess.DEVNULL)


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"Missing required tool: {name}")


def render_svg(svg: Path, png: Path) -> None:
    run("sips", "-s", "format", "png", svg, "--out", png)


def resize_square(src: Path, dst: Path, size: int) -> None:
    run("sips", "-z", size, size, src, "--out", dst)


def write_ico(frame_dir: Path, out: Path) -> None:
    """Write an ICO that stores PNG-compressed frames."""

    images = [(size, (frame_dir / f"{size}.png").read_bytes()) for size in ICO_SIZES]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = []

    for size, data in images:
        width = 0 if size == 256 else size
        height = 0 if size == 256 else size
        entries.append(
            struct.pack("<BBBBHHII", width, height, 0, 0, 1, 32, len(data), offset)
        )
        offset += len(data)

    out.write_bytes(header + b"".join(entries) + b"".join(data for _, data in images))


def main() -> int:
    require_tool("sips")
    require_tool("iconutil")

    if not COLOR_SVG.exists() or not BLACK_SVG.exists():
        raise FileNotFoundError("Missing JuGuang SVG source files in the icons directory")

    with tempfile.TemporaryDirectory() as tmp_raw:
        tmp = Path(tmp_raw)
        color_500 = tmp / "juguang-color-500.png"
        color_1024 = tmp / "juguang-color-1024.png"
        black_500 = tmp / "juguang-black-500.png"

        render_svg(COLOR_SVG, color_500)
        resize_square(color_500, color_1024, 1024)
        render_svg(BLACK_SVG, black_500)

        for name, size in APP_PNG_SIZES.items():
            resize_square(color_1024, ICON_DIR / name, size)

        iconset_dir = ICON_DIR / "icon.iconset"
        iconset_dir.mkdir(exist_ok=True)
        for name, size in ICONSET_SIZES.items():
            resize_square(color_1024, iconset_dir / name, size)
        run("iconutil", "-c", "icns", iconset_dir, "-o", ICON_DIR / "icon.icns")

        tray_crop = tmp / "tray-crop.png"
        run("sips", "-c", 250, 440, black_500, "--out", tray_crop)
        run("sips", "-z", 22, 39, tray_crop, "--out", ICON_DIR / "tray-template.png")
        run(
            "sips",
            "-z",
            44,
            77,
            tray_crop,
            "--out",
            ICON_DIR / "tray-template@2x.png",
        )

        ico_dir = tmp / "ico"
        ico_dir.mkdir()
        for size in ICO_SIZES:
            resize_square(color_1024, ico_dir / f"{size}.png", size)
        write_ico(ico_dir, ICON_DIR / "icon.ico")

    print("Generated JuGuang Tauri icons.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
