#!/usr/bin/env python3
"""Extract lane geometry from a screenshot of a commit graph.

Plan step 21, spec 6.3.1. The visual suite compares gitg and gitrl-z on
*geometry*, not pixels: the two show different commit sets, so a pixel diff
would compare nothing meaningful, but lane spacing, dot radius, row height and
lane colours are readable from two different graphs.

What this measures, and why each one:

    lane_spacing   centre-to-centre distance between adjacent lane columns
    dot_radius     radius of a commit dot
    row_height     vertical distance between adjacent commit rows
    lane_colours   the RGB the renderer actually used, per lane

The first three are the properties FR-102 delegates to vendored code. If the
vendored renderers really are gitg's, every one of them matches exactly; if a
patch or a CSS divergence perturbs the look, they do not. The lane colours are
recorded but not compared, because gitrl-z changes the palette.

A lane line is two pixels wide and a dot is ten, so an opening of the mask of
lane colours removes the lines and keeps the dots. A label is wider than a dot
and is dropped by its size. This method comes from gitrl-f. The method before
it looked for the widest run of lane colour on each scanline, and took the
pointed label of the checked-out branch for dots: it read a row height of
21 px where the rows are 23 px apart.

    measure.py <image.png> [--json]
"""

import json
import sys
from collections import Counter

try:
    from PIL import Image, ImageFilter
except ImportError:
    print("python3-pil is required", file=sys.stderr)
    raise SystemExit(2)


DOT_MAX = 14
DOT_MIN = 7
MERGE = 3
OPENING = 5
PALETTE = [
    (196, 160, 0),
    (78, 154, 6),
    (206, 92, 0),
    (32, 74, 135),
    (108, 53, 102),
    (164, 0, 0),
    (138, 226, 52),
    (252, 175, 62),
    (114, 159, 207),
    (252, 233, 79),
    (136, 138, 133),
    (173, 127, 168),
    (233, 185, 110),
    (239, 41, 41),
]
TOLERANCE = 30


def cluster(values):
    """Sorted centres of values that lie within MERGE of each other."""
    groups = []

    for value in sorted(values):
        if groups and value - groups[-1][-1] <= MERGE:
            groups[-1].append(value)
        else:
            groups.append([value])

    return [sum(group) / len(group) for group in groups]


def components(mask, width, height):
    """Bounding boxes of the four connected regions of a mask."""
    seen = bytearray(width * height)
    boxes = []

    for start in range(width * height):
        if not mask[start] or seen[start]:
            continue

        seen[start] = 1
        stack = [start]
        left, top, right, bottom = width, height, -1, -1

        while stack:
            index = stack.pop()
            x, y = index % width, index // width
            left, top = min(left, x), min(top, y)
            right, bottom = max(right, x), max(bottom, y)

            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < width and 0 <= ny < height:
                    neighbour = ny * width + nx

                    if mask[neighbour] and not seen[neighbour]:
                        seen[neighbour] = 1
                        stack.append(neighbour)

        boxes.append((left, top, right, bottom))

    return boxes


def find_dots(image):
    """Dots as (centre x, centre y, centre colour, horizontal diameter)."""
    width, height = image.size
    pixels = list(image.getdata())
    slots = [palette_index(pixel) for pixel in pixels]
    mask = Image.new("L", image.size)
    mask.putdata([0 if slot is None else 255 for slot in slots])
    opened = mask.filter(ImageFilter.MinFilter(OPENING)).filter(ImageFilter.MaxFilter(OPENING))
    kept = [value > 0 for value in opened.getdata()]
    dots = []

    for left, top, right, bottom in components(kept, width, height):
        box_width, box_height = right - left + 1, bottom - top + 1

        if not (DOT_MIN <= box_width <= DOT_MAX and DOT_MIN <= box_height <= DOT_MAX):
            continue

        cx, cy = (left + right) // 2, (top + bottom) // 2
        inside = [slots[y * width + x] for y in range(top, bottom + 1) for x in range(left, right + 1)]
        slot = Counter(s for s in inside if s is not None).most_common(1)[0][0]
        widest = max(run(slots, width, cx, y, slot) for y in range(top, bottom + 1))

        if widest > DOT_MAX:
            continue

        dots.append((cx, cy, image.getpixel((cx, cy)), run(slots, width, cx, cy, slot)))

    return dots


def load(path):
    return Image.open(path).convert("RGB")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2

    result = measure(sys.argv[1])

    if "--json" in sys.argv:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for key in sorted(result):
            print("{}: {}".format(key, result[key]))

    return 0


def measure(path):
    image = load(path)
    dots = find_dots(image)

    if len(dots) < 2:
        raise SystemExit("found fewer than two commit dots; is this a graph?")

    rows = cluster([y for _, y, _, _ in dots])
    lanes = cluster([x for x, _, _, _ in dots])
    row_gaps = [round(b - a) for a, b in zip(rows, rows[1:])]
    lane_gaps = [round(b - a) for a, b in zip(lanes, lanes[1:])]
    lane_colours = []

    for lane in lanes:
        samples = [colour for x, _, colour, _ in dots if abs(x - lane) <= MERGE]
        lane_colours.append(Counter(samples).most_common(1)[0][0])

    return {
        "dots": len(dots),
        "row_height": Counter(row_gaps).most_common(1)[0][0] if row_gaps else None,
        "lane_spacing": Counter(lane_gaps).most_common(1)[0][0] if lane_gaps else None,
        "lane_count": len(lanes),
        "dot_radius": Counter(d for _, _, _, d in dots).most_common(1)[0][0] / 2.0,
        "lane_colours": ["#%02x%02x%02x" % c for c in lane_colours],
    }


def palette_index(pixel):
    """The palette slot a pixel is drawn in, or None."""
    best = None
    best_distance = TOLERANCE + 1

    for index, colour in enumerate(PALETTE):
        distance = sum(abs(a - b) for a, b in zip(pixel, colour))

        if distance < best_distance:
            best, best_distance = index, distance

    return best


def run(slots, width, x, y, slot):
    """Length of the horizontal run of one palette slot through a pixel."""
    x0 = x1 = x

    while x0 > 0 and slots[y * width + x0 - 1] == slot:
        x0 -= 1

    while x1 < width - 1 and slots[y * width + x1 + 1] == slot:
        x1 += 1

    return x1 - x0 + 1 if slots[y * width + x] == slot else 0


if __name__ == "__main__":
    sys.exit(main())
