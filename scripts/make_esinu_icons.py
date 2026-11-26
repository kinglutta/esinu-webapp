"""Generate simple ESINU PNG icons without any third-party image libraries."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "static" / "icons"

START = (0x46, 0xD6, 0xA0)  # #46d6a0
END = (0x1F, 0x9F, 0x78)  # #1f9f78
DARK = (0x06, 0x11, 0x0C)  # #06110c
GOLD = (0xF2, 0xC1, 0x4E)  # #f2c14e


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def _lerp(a: int, b: int, t: float) -> int:
    return round(a + (b - a) * t)


def _gradient(x: int, y: int, size: int) -> tuple[int, int, int]:
    t = (x + y) / max(1, 2 * (size - 1))
    return tuple(_lerp(START[i], END[i], t) for i in range(3))  # type: ignore[return-value]


def _inside_rounded(x: int, y: int, size: int, radius: float) -> bool:
    cx = min(max(x, radius), size - radius)
    cy = min(max(y, radius), size - radius)
    return (x - cx) ** 2 + (y - cy) ** 2 <= radius**2


def _inside_circle(x: int, y: int, size: int) -> bool:
    c = (size - 1) / 2
    return (x - c) ** 2 + (y - c) ** 2 <= c**2


def _bar_specs(maskable: bool) -> list[tuple[float, float, float, float]]:
    if maskable:
        # Keep artwork well inside the safe zone for circular maskable icons.
        return [
            (0.35, 0.32, 0.34, 0.075),
            (0.475, 0.32, 0.28, 0.075),
            (0.60, 0.32, 0.34, 0.075),
        ]
    return [
        (0.30, 0.28, 0.46, 0.095),
        (0.4525, 0.28, 0.38, 0.095),
        (0.605, 0.28, 0.46, 0.095),
    ]


def _pixel(
    x: int,
    y: int,
    size: int,
    *,
    round_icon: bool,
    maskable: bool,
    foreground: bool,
) -> tuple[int, int, int, int]:
    if foreground:
        for yp, xp, width, height in _bar_specs(True):
            if (
                xp * size <= x < (xp + width) * size
                and yp * size <= y < (yp + height) * size
            ):
                return (*DARK, 255)
        dot_x, dot_y, dot_r = 0.70 * size, 0.32 * size, 0.07 * size
        if (x - dot_x) ** 2 + (y - dot_y) ** 2 <= dot_r**2:
            return (*GOLD, 255)
        return (0, 0, 0, 0)

    if round_icon and not _inside_circle(x, y, size):
        return (0, 0, 0, 0)
    if not round_icon and not maskable and not _inside_rounded(x, y, size, size * 0.22):
        return (0, 0, 0, 0)

    r, g, b = _gradient(x, y, size)

    for yp, xp, width, height in _bar_specs(maskable):
        if (
            xp * size <= x < (xp + width) * size
            and yp * size <= y < (yp + height) * size
        ):
            return (*DARK, 255)

    dot_x = 0.70 * size if maskable else 0.76 * size
    dot_y = 0.32 * size if maskable else 0.24 * size
    dot_r = 0.07 * size
    if (x - dot_x) ** 2 + (y - dot_y) ** 2 <= dot_r**2:
        return (*GOLD, 255)

    return (r, g, b, 255)


def _png(
    size: int,
    *,
    round_icon: bool = False,
    maskable: bool = False,
    foreground: bool = False,
) -> bytes:
    rows = bytearray()
    for y in range(size):
        rows.append(0)  # PNG filter type: None
        for x in range(size):
            rows.extend(
                _pixel(
                    x,
                    y,
                    size,
                    round_icon=round_icon,
                    maskable=maskable,
                    foreground=foreground,
                )
            )

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + _chunk(b"IEND", b"")
    )


def _write(path: Path, size: int, **kwargs: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_png(size, **kwargs))
    print(f"{path.relative_to(ROOT)} ({size}px)")


def main() -> None:
    targets: list[tuple[Path, int, dict[str, bool]]] = [
        (ICON_DIR / "icon-192.png", 192, {}),
        (ICON_DIR / "icon-512.png", 512, {}),
        (ICON_DIR / "icon-maskable-512.png", 512, {"maskable": True}),
        (ICON_DIR / "apple-touch-icon.png", 180, {}),
    ]

    android_res = ROOT / "esinu-mobile" / "android" / "app" / "src" / "main" / "res"
    densities = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
    foreground_sizes = {
        "mdpi": 108,
        "hdpi": 162,
        "xhdpi": 216,
        "xxhdpi": 324,
        "xxxhdpi": 432,
    }
    for density, size in densities.items():
        base = android_res / f"mipmap-{density}"
        targets.append((base / "ic_launcher.png", size, {}))
        targets.append((base / "ic_launcher_round.png", size, {"round_icon": True}))
        targets.append(
            (
                base / "ic_launcher_foreground.png",
                foreground_sizes[density],
                {"foreground": True},
            )
        )

    ios_icons = (
        ROOT
        / "esinu-mobile"
        / "ios"
        / "App"
        / "App"
        / "Assets.xcassets"
        / "AppIcon.appiconset"
    )
    targets.append((ios_icons / "AppIcon-512@2x.png", 1024, {}))

    for path, size, kwargs in targets:
        _write(path, size, **kwargs)


if __name__ == "__main__":
    main()
