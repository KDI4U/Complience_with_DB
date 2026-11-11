"""
create_icons.py
Generates professional multi-size Windows icon (.ico) files:
1. epfo_icon.ico (Royal Blue & Gold theme for EPFO)
2. esic_icon.ico (Emerald Green & White Cross theme for ESIC)
3. compliance_hub.ico (Indigo & Cyan theme for Unified Hub)
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ICON_SIZES = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]


def create_epfo_icon(save_path: Path):
    """Creates a high-res professional EPFO icon."""
    size = (256, 256)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Outer Royal Blue Circle with drop shadow
    draw.ellipse([8, 8, 248, 248], fill="#1e3a8a", outline="#3b82f6", width=8)

    # Inner Gold Ring
    draw.ellipse([26, 26, 230, 230], outline="#f59e0b", width=5)

    # Inner Dark Slate background
    draw.ellipse([34, 34, 222, 222], fill="#0f172a")

    # Center Shield / Emblem (Hexagon/Shield shape)
    shield_pts = [(128, 55), (195, 85), (195, 145), (128, 205), (61, 145), (61, 85)]
    draw.polygon(shield_pts, fill="#2563eb", outline="#60a5fa", width=4)

    # Gold Ribbon / Banner across center
    draw.rectangle([55, 120, 201, 155], fill="#f59e0b", outline="#fbbf24", width=2)

    # Text: EPFO
    try:
        font = ImageFont.truetype("arialbd.ttf", 32)
        font_sub = ImageFont.truetype("arialbd.ttf", 18)
    except Exception:
        font = ImageFont.load_default()
        font_sub = font

    # Draw "EPFO" inside the banner
    draw.text((128, 137), "EPFO", font=font, fill="#0f172a", anchor="mm")
    # Draw "PF" above banner
    draw.text((128, 95), "PF", font=font, fill="#ffffff", anchor="mm")

    # Save multi-size ICO
    img.save(str(save_path), format="ICO", sizes=ICON_SIZES)
    print(f"[OK] Generated: {save_path.name}")


def create_esic_icon(save_path: Path):
    """Creates a high-res professional ESIC icon."""
    size = (256, 256)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Outer Emerald Green Circle
    draw.ellipse([8, 8, 248, 248], fill="#065f46", outline="#10b981", width=8)

    # Inner White / Mint Ring
    draw.ellipse([26, 26, 230, 230], outline="#34d399", width=5)

    # Inner Dark Teal background
    draw.ellipse([34, 34, 222, 222], fill="#064e3b")

    # Medical Cross in the center (White / Mint)
    # Vertical bar
    draw.rectangle([112, 58, 144, 185], fill="#ffffff", outline="#a7f3d0", width=2)
    # Horizontal bar
    draw.rectangle([65, 105, 191, 137], fill="#ffffff", outline="#a7f3d0", width=2)

    # Center Red / Amber health heart/badge
    draw.ellipse([110, 103, 146, 139], fill="#ef4444")

    # Bottom Banner for ESIC
    draw.rectangle([50, 175, 206, 215], fill="#10b981", outline="#34d399", width=2)

    try:
        font_txt = ImageFont.truetype("arialbd.ttf", 26)
    except Exception:
        font_txt = ImageFont.load_default()

    draw.text((128, 195), "ESIC", font=font_txt, fill="#ffffff", anchor="mm")

    img.save(str(save_path), format="ICO", sizes=ICON_SIZES)
    print(f"[OK] Generated: {save_path.name}")


if __name__ == "__main__":
    create_epfo_icon(BASE_DIR / "epfo_icon.ico")
    create_esic_icon(BASE_DIR / "esic_icon.ico")

