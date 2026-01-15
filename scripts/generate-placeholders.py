#!/usr/bin/env python3
"""
Generate simple placeholder GIF animations for each state.
Run this once to create default assets.
"""

import math
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Install pillow: pip install pillow")
    exit(1)

OUTPUT_DIR = Path(__file__).parent.parent / 'themes' / 'default' / 'characters'
SIZE = 150
FRAMES = 8


def create_gif(name: str, draw_func, frames: int = FRAMES):
    """Create an animated GIF."""
    images = []
    for i in range(frames):
        img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw_func(draw, i, frames)
        images.append(img)

    path = OUTPUT_DIR / f'{name}.gif'
    images[0].save(
        path,
        save_all=True,
        append_images=images[1:],
        duration=100,
        loop=0,
        transparency=0,
        disposal=2
    )
    print(f"Created {path}")


def draw_idle(draw, frame, total):
    """Idle: gentle breathing circle."""
    cx, cy = SIZE // 2, SIZE // 2
    pulse = 5 * math.sin(2 * math.pi * frame / total)
    r = 50 + pulse
    # Body
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill='#6366f1')
    # Eyes
    ey = cy - 10
    draw.ellipse([cx - 20, ey - 8, cx - 8, ey + 8], fill='white')
    draw.ellipse([cx + 8, ey - 8, cx + 20, ey + 8], fill='white')
    draw.ellipse([cx - 16, ey - 4, cx - 12, ey + 4], fill='black')
    draw.ellipse([cx + 12, ey - 4, cx + 16, ey + 4], fill='black')
    # Smile
    draw.arc([cx - 15, cy, cx + 15, cy + 20], 0, 180, fill='white', width=3)


def draw_greeting(draw, frame, total):
    """Greeting: waving arm."""
    cx, cy = SIZE // 2, SIZE // 2
    r = 50
    # Body
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill='#22c55e')
    # Eyes (happy)
    ey = cy - 10
    draw.arc(
        [cx - 22, ey - 10, cx - 8, ey + 10], 0, 180, fill='black', width=3)
    draw.arc(
        [cx + 8, ey - 10, cx + 22, ey + 10], 0, 180, fill='black', width=3)
    # Big smile
    draw.arc(
        [cx - 25, cy - 5, cx + 25, cy + 30], 0, 180, fill='white', width=4)
    # Waving hand
    wave = 20 * math.sin(4 * math.pi * frame / total)
    hx = cx + r + 10
    hy = cy - 30 + wave
    draw.ellipse([hx - 15, hy - 15, hx + 15, hy + 15], fill='#22c55e')


def draw_working(draw, frame, total):
    """Working: spinning gear effect."""
    cx, cy = SIZE // 2, SIZE // 2
    r = 50
    # Body
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill='#f59e0b')
    # Focused eyes
    ey = cy - 10
    draw.ellipse([cx - 20, ey - 6, cx - 8, ey + 6], fill='white')
    draw.ellipse([cx + 8, ey - 6, cx + 20, ey + 6], fill='white')
    draw.ellipse([cx - 16, ey - 3, cx - 12, ey + 3], fill='black')
    draw.ellipse([cx + 12, ey - 3, cx + 16, ey + 3], fill='black')
    # Determined mouth
    draw.line([cx - 10, cy + 15, cx + 10, cy + 15], fill='white', width=3)
    # Spinning dots around
    angle = (frame / total) * 2 * math.pi
    for i in range(4):
        a = angle + i * math.pi / 2
        dx = int(70 * math.cos(a))
        dy = int(70 * math.sin(a))
        draw.ellipse([cx + dx - 8, cy + dy - 8, cx + dx + 8, cy + dy + 8],
                     fill='#fbbf24')


def draw_success(draw, frame, total):
    """Success: thumbs up bounce."""
    cx, cy = SIZE // 2, SIZE // 2
    bounce = -10 * abs(math.sin(2 * math.pi * frame / total))
    cy += int(bounce)
    r = 50
    # Body
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill='#10b981')
    # Happy eyes
    ey = cy - 10
    draw.arc(
        [cx - 22, ey - 10, cx - 8, ey + 10], 0, 180, fill='black', width=3)
    draw.arc(
        [cx + 8, ey - 10, cx + 22, ey + 10], 0, 180, fill='black', width=3)
    # Big open smile
    draw.chord([cx - 25, cy, cx + 25, cy + 35], 0, 180, fill='white')
    # Sparkles
    if frame % 2 == 0:
        for sx, sy in [(30, 30), (120, 40), (40, 110), (110, 100)]:
            draw.line([sx - 5, sy, sx + 5, sy], fill='#fde047', width=2)
            draw.line([sx, sy - 5, sx, sy + 5], fill='#fde047', width=2)


def draw_error(draw, frame, total):
    """Error: worried shake."""
    cx, cy = SIZE // 2, SIZE // 2
    shake = 5 * math.sin(8 * math.pi * frame / total)
    cx += int(shake)
    r = 50
    # Body
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill='#ef4444')
    # Worried eyes
    ey = cy - 15
    draw.ellipse([cx - 22, ey - 10, cx - 8, ey + 10], fill='white')
    draw.ellipse([cx + 8, ey - 10, cx + 22, ey + 10], fill='white')
    draw.ellipse([cx - 17, ey - 5, cx - 13, ey + 5], fill='black')
    draw.ellipse([cx + 13, ey - 5, cx + 17, ey + 5], fill='black')
    # Eyebrows (worried)
    draw.line([cx - 25, ey - 18, cx - 8, ey - 12], fill='black', width=3)
    draw.line([cx + 8, ey - 12, cx + 25, ey - 18], fill='black', width=3)
    # Wavy mouth
    draw.arc(
        [cx - 15, cy + 10, cx + 15, cy + 30], 180, 360, fill='white', width=3)


def draw_celebrating(draw, frame, total):
    """Celebrating: party with confetti."""
    cx, cy = SIZE // 2, SIZE // 2
    jump = -15 * abs(math.sin(2 * math.pi * frame / total))
    cy += int(jump)
    r = 50
    # Body
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill='#8b5cf6')
    # Party eyes (^ ^)
    ey = cy - 10
    draw.line([cx - 22, ey, cx - 15, ey - 10], fill='black', width=3)
    draw.line([cx - 15, ey - 10, cx - 8, ey], fill='black', width=3)
    draw.line([cx + 8, ey, cx + 15, ey - 10], fill='black', width=3)
    draw.line([cx + 15, ey - 10, cx + 22, ey], fill='black', width=3)
    # Open mouth (yay!)
    draw.chord([cx - 20, cy + 5, cx + 20, cy + 35], 0, 180, fill='#fecaca')
    # Confetti
    colors = ['#fde047', '#fb7185', '#38bdf8', '#4ade80']
    for i in range(6):
        fx = 20 + (i * 25) + int(10 * math.sin(frame + i))
        fy = 20 + ((frame * 10 + i * 20) % 130)
        c = colors[i % len(colors)]
        draw.rectangle([fx, fy, fx + 8, fy + 8], fill=c)


def draw_sleeping(draw, frame, total):
    """Sleeping: zzz animation."""
    cx, cy = SIZE // 2, SIZE // 2 + 10
    r = 50
    # Body (slightly squished)
    draw.ellipse([cx - r - 5, cy - r + 10, cx + r + 5, cy + r], fill='#64748b')
    # Closed eyes
    ey = cy - 10
    draw.arc([cx - 22, ey - 5, cx - 8, ey + 10], 0, 180, fill='black', width=3)
    draw.arc([cx + 8, ey - 5, cx + 22, ey + 10], 0, 180, fill='black', width=3)
    # Sleeping mouth
    draw.ellipse([cx - 5, cy + 15, cx + 5, cy + 25], fill='#475569')
    # Zzz
    z_offset = (frame * 3) % 30
    for i, (zx, zy) in enumerate([(85, 40), (100, 25), (115, 10)]):
        zy += z_offset - i * 5
        alpha = max(0, 255 - z_offset * 8 - i * 30)
        if alpha > 50:
            draw.text((zx, zy), "z", fill='#94a3b8')


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    create_gif('idle', draw_idle)
    create_gif('greeting', draw_greeting)
    create_gif('working', draw_working)
    create_gif('success', draw_success)
    create_gif('error', draw_error)
    create_gif('celebrating', draw_celebrating)
    create_gif('sleeping', draw_sleeping)

    print(f"\nPlaceholder GIFs created in {OUTPUT_DIR}")
    print("Replace with your own character GIFs for custom mascots!")


if __name__ == '__main__':
    main()
