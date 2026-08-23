"""T01, projected from the viewpoints Pixal3D's sequence chooses rather than from an axis.

WHY NOT front OR side. The first two sheets picked a world axis by hand, and the choice decided
the answer: a front view flattened the stride, because mean foot separation is 0.356 m along the
travel axis against 0.230 m across it -- about five stacked soda cans against three and a half.
Swapping to the side view fixed that one case and left the same objection standing, since the
next dataset may travel along a different axis.

`sphere_hammersley_sequence` removes the choice. It is the camera generator TRELLIS.2 and
Pixal3D use, ported exactly in `render_view.py`, and it is parameterised by an integer: view i
of n is a yaw and a pitch, well spread over the sphere and reproducible from the index alone.
The twenty poses therefore get twenty different viewpoints, none of them argued for.

The projection is orthographic onto the plane facing each camera, with world Y up. No renderer,
no GPU, no install, which is what the task allows.
"""
import math
import pathlib
import sys

import pyarrow.parquet as pq
from PIL import Image, ImageDraw

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[0]))
CORPUS = r"C:\weftspun-keypoint\6-datasource\anny-render-corpus"
sys.path.insert(0, CORPUS)
from render_view import sphere_hammersley  # noqa: E402  the point of the exercise

SRC, OUT = sys.argv[1], sys.argv[2]

BONES = [
    ("root", "spine05"), ("spine05", "spine04"), ("spine04", "spine03"),
    ("spine03", "spine02"), ("spine02", "neck01"), ("neck01", "head"),
    ("spine02", "clavicle.L"), ("clavicle.L", "upperarm01.L"),
    ("upperarm01.L", "lowerarm01.L"), ("lowerarm01.L", "wrist.L"),
    ("spine02", "clavicle.R"), ("clavicle.R", "upperarm01.R"),
    ("upperarm01.R", "lowerarm01.R"), ("lowerarm01.R", "wrist.R"),
    ("root", "upperleg01.L"), ("upperleg01.L", "lowerleg01.L"), ("lowerleg01.L", "foot.L"),
    ("root", "upperleg01.R"), ("upperleg01.R", "lowerleg01.R"), ("lowerleg01.R", "foot.R"),
]
CELL, COLS, PAD = 200, 5, 16

rows = pq.read_table(SRC).to_pydict()
by_clip = {}
for i in range(len(rows["x"])):
    by_clip.setdefault(rows["clip_name"][i], {}).setdefault(rows["frame_index"][i], {})[
        rows["anny_bone"][i]] = (rows["x"][i], rows["y"][i], rows["z"][i])

clips = sorted(by_clip)
n = len(clips)
sheet = Image.new("RGB", (COLS * CELL, ((n + COLS - 1) // COLS) * (CELL + 26) + PAD), (18, 18, 20))
d = ImageDraw.Draw(sheet)
cameras = []

for k, clip in enumerate(clips):
    yaw, pitch = sphere_hammersley(k, n)
    cameras.append((clip, yaw, pitch))
    # Orthographic basis facing (yaw, pitch), world Y up.
    fx, fy, fz = math.cos(pitch) * math.sin(yaw), math.sin(pitch), math.cos(pitch) * math.cos(yaw)
    rx, rz = math.cos(yaw), -math.sin(yaw)          # right, horizontal so the horizon stays level
    # up = forward x right. Written the other way round first, and every figure collapsed to a
    # diagonal line -- the basis was degenerate, not the data. Checked against the identity
    # case: forward (0,0,1) and right (1,0,0) must give up (0,1,0).
    ux, uy, uz = fy * rz, fz * rx - fx * rz, -fy * rx

    frames = sorted(by_clip[clip])
    joints = by_clip[clip][frames[len(frames) // 2]]
    flat = {b: (p[0] * rx + p[2] * rz, p[0] * ux + p[1] * uy + p[2] * uz) for b, p in joints.items()}
    xs = [p[0] for p in flat.values()]
    ys = [p[1] for p in flat.values()]
    cx, lo, hi = (min(xs) + max(xs)) / 2, min(ys), max(ys)
    scale = (CELL - 52) / max(hi - lo, 1e-6)

    ox, oy = (k % COLS) * CELL, (k // COLS) * (CELL + 26) + PAD

    def px(b):
        x, y = flat[b]
        return (ox + CELL / 2 + (x - cx) * scale, oy + CELL - 30 - (y - lo) * scale)

    for a, b in BONES:
        if a in flat and b in flat:
            d.line([px(a), px(b)], fill=(150, 190, 235), width=2)
    for b in flat:
        x, y = px(b)
        d.ellipse([x - 2.5, y - 2.5, x + 2.5, y + 2.5], fill=(240, 200, 120))
    d.text((ox + 6, oy + CELL - 22), clip[:26], fill=(190, 190, 195))
    d.text((ox + 6, oy + CELL - 10),
           "view %d  yaw %.0f°  pitch %.0f°" % (k, math.degrees(yaw), math.degrees(pitch)),
           fill=(130, 130, 138))

sheet.save(OUT)
print("  %d poses, one Hammersley viewpoint each -> %s" % (n, OUT))
for clip, yaw, pitch in cameras[:3]:
    print("    %-18s yaw %7.2f  pitch %7.2f" % (clip, math.degrees(yaw), math.degrees(pitch)))
print("    ... %d cameras, reproducible from the index alone" % n)
