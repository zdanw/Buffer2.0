"""Generate simple demo product placeholder images for documentation screenshots."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "docs" / "demo"

# RGB tuples — soft lifestyle product palette
ASSETS = {
    "lamp.jpg": (245, 240, 232),       # warm cream
    "pillow.jpg": (220, 228, 236),     # cool linen
    "candle.jpg": (248, 236, 224),     # soft amber
    "scene-nursery.jpg": (235, 228, 220),
    "scene-living.jpg": (228, 232, 238),
}


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def write_solid_jpeg(path: Path, rgb: tuple[int, int, int], width: int = 800, height: int = 800) -> None:
    """Write a minimal JPEG (solid color) without external dependencies."""
    # JPEG is complex; write PNG instead but keep .jpg extension — browsers accept it.
    # Use .png extension for correctness.
    write_solid_png(path.with_suffix(".png"), rgb, width, height)
    if path.suffix.lower() == ".jpg" and path.with_suffix(".png").exists():
        path.with_suffix(".png").rename(path)


def write_solid_png(path: Path, rgb: tuple[int, int, int], width: int = 800, height: int = 800) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    r, g, b = rgb
    raw = b"".join(
        b"\x00" + bytes([r, g, b]) * width
        for _ in range(height)
    )
    compressed = zlib.compress(raw, 9)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", compressed)
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, color in ASSETS.items():
        out = OUT / name.replace(".jpg", ".png")
        write_solid_png(out, color)
        print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
