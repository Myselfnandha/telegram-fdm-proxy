#!/usr/bin/env python3
import os
from PIL import Image, ImageDraw

def render_crisp_telegram_icon(size: int = 256, connected: bool = True) -> Image.Image:
    """
    Renders a pixel-perfect, anti-aliased Telegram-style icon using 4x supersampling.
    """
    # Render at 4x resolution for perfect anti-aliasing
    scale = 4
    canvas_size = size * scale
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = 8 * scale
    # Main Circle background (Telegram Blue or Neutral Gray)
    bg_color = "#24A1DE" if connected else "#5A6578"  # Official Telegram Blue
    draw.ellipse(
        [margin, margin, canvas_size - margin, canvas_size - margin],
        fill=bg_color
    )

    # Telegram Paper Plane coordinates (normalized to circle size)
    # Accurate Telegram plane geometric proportions
    cx, cy = canvas_size / 2, canvas_size / 2
    r = (canvas_size - 2 * margin) / 2
    
    # Official Telegram Paper Plane geometry
    # Tail Left: (-0.45 * r, +0.10 * r)
    # Nose Right: (+0.52 * r, -0.05 * r)
    # Wing Top: (-0.18 * r, -0.48 * r)
    # Fold Bottom: (+0.05 * r, +0.32 * r)
    # Fold Mid: (-0.12 * r, +0.14 * r)
    
    p_tail = (cx - 0.44 * r, cy + 0.08 * r)
    p_nose = (cx + 0.48 * r, cy - 0.06 * r)
    p_top  = (cx - 0.18 * r, cy - 0.46 * r)
    p_bottom = (cx + 0.02 * r, cy + 0.32 * r)
    p_mid  = (cx - 0.14 * r, cy + 0.10 * r)

    # 1. Main body / upper wing (pure white)
    draw.polygon([p_tail, p_nose, p_top], fill="#FFFFFF")

    # 2. Lower right fold (subtle shadow)
    shadow_color = "#B8E1F5" if connected else "#9AA6B8"
    draw.polygon([p_nose, p_bottom, p_mid], fill=shadow_color)

    # 3. Main bottom wing (pure white)
    draw.polygon([p_tail, p_nose, p_mid], fill="#E6F4FB" if connected else "#BAC4D2")

    # Small download lightning badge in bottom right (optional for tray, crisp)
    badge_r = 0.28 * r
    bx, by = cx + 0.58 * r, cy + 0.58 * r
    draw.ellipse([bx - badge_r, by - badge_r, bx + badge_r, by + badge_r], fill="#10B981", outline="#FFFFFF", width=3*scale)
    # Arrow
    stem_w = 3 * scale
    draw.rectangle([bx - stem_w, by - 0.14 * r, bx + stem_w, by + 0.04 * r], fill="#FFFFFF")
    draw.polygon([(bx - 0.12 * r, by + 0.02 * r), (bx + 0.12 * r, by + 0.02 * r), (bx, by + 0.16 * r)], fill="#FFFFFF")

    # Downsample with high-quality Lanczos resampling
    final_img = img.resize((size, size), Image.Resampling.LANCZOS)
    return final_img

def update_assets():
    assets_dir = os.path.join(os.path.dirname(__file__), "assets")
    os.makedirs(assets_dir, exist_ok=True)
    
    icon_256 = render_crisp_telegram_icon(256, connected=True)
    icon_256.save(os.path.join(assets_dir, "tg-fdm-proxy.png"), "PNG")
    
    icon_64 = render_crisp_telegram_icon(64, connected=True)
    icon_64.save(os.path.join(assets_dir, "tray_icon.png"), "PNG")
    
    print(f"Rendered crisp antialiased icons into {assets_dir}")

if __name__ == "__main__":
    update_assets()
