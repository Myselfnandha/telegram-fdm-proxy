import os
from PIL import Image, ImageDraw

def generate_icons():
    assets_dir = os.path.join(os.path.dirname(__file__), "assets")
    os.makedirs(assets_dir, exist_ok=True)
    
    # 256x256 icon
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Rounded gradient-like blue background circle
    draw.ellipse([8, 8, size - 8, size - 8], fill="#0088cc")
    
    # Inner subtle glow
    draw.ellipse([14, 14, size - 14, size - 14], outline="#29b6f6", width=4)
    
    # Paper plane shape
    cx, cy = size // 2, size // 2
    s = size * 0.35
    
    plane_points = [
        (cx - s * 0.9, cy + s * 0.15),
        (cx + s * 0.95, cy - s * 0.1),
        (cx - s * 0.3, cy - s * 0.8),
    ]
    draw.polygon(plane_points, fill="#ffffff")
    
    # Inner fold shadow
    fold_points = [
        (cx + s * 0.95, cy - s * 0.1),
        (cx - s * 0.1, cy + s * 0.45),
        (cx - s * 0.3, cy - s * 0.1),
    ]
    draw.polygon(fold_points, fill="#b3e5fc")
    
    # Bottom right download badge circle
    badge_r = 46
    bx, by = size - 56, size - 56
    draw.ellipse([bx - badge_r, by - badge_r, bx + badge_r, by + badge_r], fill="#10b981", outline="#ffffff", width=4)
    
    # Download arrow in badge
    # Stem
    draw.rectangle([bx - 6, by - 24, bx + 6, by + 10], fill="#ffffff")
    # Head
    draw.polygon([(bx - 20, by + 8), (bx + 20, by + 8), (bx, by + 28)], fill="#ffffff")
    
    png_path = os.path.join(assets_dir, "tg-fdm-proxy.png")
    img.save(png_path, format="PNG")
    print(f"Generated PNG icon: {png_path}")

    # Generate SVG
    svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#00a8ec"/>
      <stop offset="100%" stop-color="#0077b5"/>
    </linearGradient>
    <linearGradient id="badge" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#34d399"/>
      <stop offset="100%" stop-color="#059669"/>
    </linearGradient>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-opacity="0.25"/>
    </filter>
  </defs>
  
  <!-- Base Circle -->
  <circle cx="128" cy="128" r="120" fill="url(#bg)" filter="url(#shadow)"/>
  <circle cx="128" cy="128" r="114" fill="none" stroke="#67e8f9" stroke-width="3" stroke-opacity="0.4"/>
  
  <!-- Paper Plane -->
  <path d="M 50 142 L 210 115 L 102 56 Z" fill="#ffffff"/>
  <path d="M 210 115 L 120 168 L 102 119 Z" fill="#b3e5fc"/>
  
  <!-- Download Badge -->
  <circle cx="196" cy="196" r="46" fill="url(#badge)" stroke="#ffffff" stroke-width="4" filter="url(#shadow)"/>
  <path d="M 190 172 L 202 172 L 202 206 L 190 206 Z" fill="#ffffff"/>
  <path d="M 176 204 L 216 204 L 196 226 Z" fill="#ffffff"/>
</svg>"""
    svg_path = os.path.join(assets_dir, "tg-fdm-proxy.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg_content)
    print(f"Generated SVG icon: {svg_path}")

if __name__ == "__main__":
    generate_icons()
