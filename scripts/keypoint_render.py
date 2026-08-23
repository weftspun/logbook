"""Sample corpus renders: Mitsuba depth, keypoints coloured by See-Through layer in OKHSL.

WHAT IT WRITES, AND WHY IT IS ONE FILE. A PNG per view to look at, and one Lottie holding
everything else: 104 joints and 103 bones as vectors carrying their float positions, names,
parents and visibility, plus each view's depth pass embedded as a data-URI asset. Lottie takes
rasters the way SVG does, so the container never forces a choice between vectors and pixels.
Earlier revisions wrote OpenEXR, then a 32-bit PSB and a sidecar SVG; both are gone.

THE DEPTH STAYS EXACT, WHICH TOOK GETTING WRONG FIRST. A PNG channel is 8 bits and depth is a
32-bit float in metres, so the IEEE pattern is split across RGBA rather than scaled into a
range. That is lossless by construction and asserted on every write by decoding the bytes back
and comparing; a single flipped bit fails it. Scaling into 16-bit grey would have quantised this
render's 0.813 m span at 0.012 mm a step -- about a sixtieth of a credit card -- trading an
exact measurement for a smaller file.

ONLY DEPTH IS STORED. The matte is `depth > 0` and the shading is a ramp between the near and
far planes, so both are derivable and neither is written, for the same reason a parquet here
carries no derivable column.

WHAT THE COLOUR MEANS, which is the whole design:

    HUE            which See-Through layer the joint drives
    hue +/- 6 deg  which joint within that layer
    LIGHTNESS      position along the chain inside the layer
    SHAPE          visibility: filled if unoccluded, hollow if the surface is in front

RETRACTED: the first version spaced all 104 hues by the golden angle, to make neighbours
maximally distinct. That is the wrong objective here. It scatters the five finger joints of
one hand across the entire wheel, so nothing about the picture says they are one garment
region. Related layers should read as related.

WHY OKHSL AND NOT HSL. HSL lightness is not perceptual. At a fixed L an HSL sweep makes
yellows glare and blues sink, so a reader sees brightness differences that encode nothing and
misses the lightness differences that encode chain position. OKHSL holds perceived lightness
constant across hue, which is the only reason lightness is free to carry a second variable.

RETRACTED: IT IS 8 TAGS AND 16 WITHOUT A BONE, NOT 9 AND 15. This docstring said 9 until a
run printed 8, and the code could never have produced 9: `tag_for` has eight distinct return
values, so the count was wrong when written rather than having drifted. Measured on this
desk -- driven: bottomwear, footwear, handwear, head, irides, legwear, neck, topwear.

TAG ORDER IS ANATOMICAL, head to foot, so adjacent tags sit 15 degrees apart and the head
group, the leg group and so on each occupy a contiguous arc.

THE GAP THIS MAKES VISIBLE. ANNY drives 8 of See-Through's 24 tags. The other 16 have no bone
in the skeleton at all, and the legend lists them greyed rather than omitting them, because a
missing category that is simply absent from the picture reads as a category that does not
exist. This is the same finding RFD 0121 records: hair and garments are not modelled.
"""
import json
import os
import sys

import numpy as np
import torch
import drjit as dr
from PIL import Image, ImageDraw
# ColorAll rather than Color: coloraide keeps OKHSL out of the default registry, so
# `Color('okhsl', ...)` raises `not a registered color space` on 8.11.1. The whole
# colour scheme above is OKHSL, so this import is load-bearing rather than stylistic.
from coloraide.everything import ColorAll as Color

sys.path.insert(0, os.environ.get(
    "POSE_CONSENSUS_PYTHON", "../3-interactor/pose-consensus/python"))
import mitsuba as mi
mi.set_variant('cuda_ad_rgb')

from silhouette import Camera
import anny
from anny.models.model_data import TopologyConfig

OUT = os.environ.get("LOGBOOK_OUT", ".")
dev, dt = 'cuda', torch.float32
W = H = 1024
FOV = 40.0
SEED = 0

# See-Through's 24 tags, from seethrough-torch/training/configs/finetune_layerdiff_iter2.yaml,
# reordered head to foot so related layers land on neighbouring hues.
TAG_ORDER = [
    'head', 'face', 'eyebrow', 'eyelash', 'eyewhite', 'irides', 'nose', 'mouth',
    'ears', 'earwear', 'eyewear', 'headwear', 'front hair', 'back hair',
    'neck', 'neckwear',
    'topwear', 'handwear',
    'bottomwear', 'legwear', 'footwear',
    'tail', 'wings', 'objects',
]
BASE_HUE = {t: 360.0 * i / len(TAG_ORDER) for i, t in enumerate(TAG_ORDER)}


def tag_for(name):
    """Which See-Through layer a bone drives. A claim about the body, so it is data."""
    n = name.lower()
    if n.startswith('eye'):
        return 'irides'
    if n == 'head':
        return 'head'
    if n.startswith('neck'):
        return 'neck'
    if n.startswith('spine') or n.startswith('clavicle') or n.startswith('shoulder') \
            or n.startswith('upperarm') or n.startswith('lowerarm'):
        return 'topwear'
    if n.startswith('wrist') or n.startswith('finger') or n.startswith('metacarpal'):
        return 'handwear'
    if n.startswith('foot') or n.startswith('toe'):
        return 'footwear'
    if n.startswith('lowerleg'):
        return 'legwear'
    if n.startswith('pelvis') or n.startswith('upperleg') or n == 'root':
        return 'bottomwear'
    raise KeyError("no See-Through tag for bone %r" % name)


m = anny.Anny(topology=TopologyConfig(base_mesh='makehuman', remove_unattached_vertices=False))
out = m()
verts = out['vertices'][0].detach().to(dev, dt)
joints = out['bone_poses'][0].detach().to(dev, dt)[:, :3, 3]
faces = torch.as_tensor(m.faces.cpu().numpy().astype(np.int64)).to(dev)
labels = list(m.bone_labels)
parents = list(m.bone_parents)
N = len(labels)
assert N == joints.shape[0] == 104, (N, joints.shape)

tags = [tag_for(n) for n in labels]
groups = {}
for i, t in enumerate(tags):
    groups.setdefault(t, []).append(i)

COLS = [None] * N
HUE = [0.0] * N
LIT = [0.0] * N
for t, idx in groups.items():
    k = len(idx)
    for j, i in enumerate(idx):
        f = 0.5 if k == 1 else j / (k - 1)
        HUE[i] = (BASE_HUE[t] + (f - 0.5) * 12.0) % 360.0     # +/- 6 degrees inside the layer
        LIT[i] = 0.50 + 0.24 * f
        c = Color('okhsl', [HUE[i], 0.95, LIT[i]]).convert('srgb')
        COLS[i] = tuple(int(round(255 * min(max(v, 0.0), 1.0))) for v in c[:3])

distinct = len({tuple(c) for c in COLS})
print("%d bones -> %d See-Through layers; %d distinct sRGB triples"
      % (N, len(groups), distinct))
if distinct < N:
    print("WARNING: %d colours collided after 8-bit quantisation" % (N - distinct))
missing = [t for t in TAG_ORDER if t not in groups]
print("layers ANNY drives  : %s" % ', '.join(sorted(groups)))
print("layers with NO bone : %s" % ', '.join(missing))


def camera(az_deg, elev=0.25, dist=3.0):
    c = verts.mean(0)
    a = np.radians(az_deg)
    off = torch.tensor([float(np.sin(a)), float(np.cos(a)), elev], device=dev, dtype=dt)
    eye = c + off / off.norm() * float((verts - c).norm(dim=1).max()) * dist
    fwd = (c - eye); fwd = fwd / fwd.norm()
    up = torch.tensor([0., 0., 1.], device=dev, dtype=dt)
    s = torch.cross(fwd, up, dim=0); s = s / s.norm(); u = torch.cross(s, fwd, dim=0)
    view = torch.eye(4, device=dev, dtype=dt)
    view[0, :3], view[1, :3], view[2, :3] = s, -u, fwd
    view[:3, 3] = -(view[:3, :3] @ eye)
    fx = (W / 2) / np.tan(np.radians(FOV) / 2)
    return Camera(width=W, height=H, fx=fx, fy=fx, cx=W / 2, cy=H / 2, view=view), eye, c, up


mesh = mi.Mesh("body", vertex_count=verts.shape[0], face_count=faces.shape[0],
               has_vertex_normals=False, has_vertex_texcoords=False)
mp = mi.traverse(mesh)
mp['vertex_positions'] = mi.Float(verts.reshape(-1).cpu().numpy())
mp['faces'] = mi.UInt(faces.reshape(-1).to(torch.int32).cpu().numpy())
mp.update()


def render(cam, eye, target, up):
    """Planar camera-space z, and a hit mask.

    The `position` AOV rather than the `depth` AOV, because `depth` is the ray parameter t and
    every other depth here is planar z. Measured on this body they differ by a median 10.4 mm
    and up to 137 mm, about three golf balls, in a map that looks entirely plausible.
    """
    e, t_, u_ = eye.cpu().numpy(), target.cpu().numpy(), up.cpu().numpy()
    scene = mi.load_dict({
        'type': 'scene',
        'integrator': {'type': 'aov', 'aovs': 'pos:position,t:depth'},
        'sensor': {'type': 'perspective', 'fov': FOV, 'fov_axis': 'x',
                   'to_world': mi.ScalarTransform4f().look_at(
                       origin=[float(x) for x in e], target=[float(x) for x in t_],
                       up=[float(x) for x in u_]),
                   'film': {'type': 'hdrfilm', 'width': W, 'height': H,
                            'rfilter': {'type': 'box'}, 'pixel_format': 'rgba'},
                   'sampler': {'type': 'independent', 'sample_count': 1}},
        'body': mesh,
    })
    img = mi.render(scene, spp=1, seed=SEED)
    dr.eval(img); dr.sync_thread()
    a = np.array(img)
    pos = torch.as_tensor(np.ascontiguousarray(a[..., 0:3]), device=dev, dtype=dt)
    tray = torch.as_tensor(np.ascontiguousarray(a[..., 3]), device=dev, dtype=dt)
    z = (torch.cat([pos, torch.ones_like(pos[..., :1])], -1) @ cam.view.T)[..., 2]
    return z, tray > 0


def srgb_to_linear(u8):
    """sRGB 8-bit to linear float. EXR is a LINEAR format.

    Writing 8-bit sRGB values straight into float channels is the ordinary way to get an EXR
    whose colours are wrong in a way no viewer flags: mid grey lands at 0.5 instead of 0.214,
    and every hue shifts. The draw is not antialiased, so each pixel carries an exact palette
    colour and this mapping is exact rather than approximate.
    """
    c = u8.astype(np.float32) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4).astype(np.float32)


def write_lottie(path, views, cols, labels, parents, fps=2):
    """The viewpoints as one Lottie animation, with no in-between frames invented.

    WHY HOLD KEYFRAMES AND NOT INTERPOLATION, which is the whole correctness argument. Lottie
    tweens between keyframes by default, and a tween between two camera viewpoints is a lie:
    projected joints do not travel in straight 2D lines while a camera swings around a body, so
    a linear in-between puts every joint somewhere the geometry never was. Each keyframe is
    therefore marked `h: 1` -- hold -- so every displayed frame is a rendered viewpoint and
    nothing between them is asserted. Smooth motion is bought by rendering more viewpoints, not
    by inventing them.

    WHY THE ERROR IS BOUNDED BY ROUNDING ALONE. These coordinates are not traced from pixels;
    they come from the same camera projection the labels do, so there is no vectorisation step
    to be inaccurate. The only loss is the decimal places written, and the check below measures
    exactly that rather than trusting it.

    NO BORDERS, same as the SVG: joints are fill-only ellipses, and a bone's stroke is the bone
    itself rather than an outline around a shape.
    """
    import base64
    import io
    import json

    import numpy as np
    from PIL import Image as PILImage

    def depth_png(depth):
        """float32 metres -> lossless RGBA8 PNG, one byte per octet of the IEEE pattern.

        A PNG channel is 8 bits and depth is a 32-bit float, so the float is split across RGBA
        rather than scaled into a range. That is lossless by construction and measured to be:
        decoded back the array is bit-identical, and flipping one bit makes the check fail.
        Scaling into 16-bit grey would have quantised 0.813 m at 0.012 mm a step, and thrown
        away the exactness for a smaller file.
        """
        bits = depth.astype(np.float32).view(np.uint32)
        rgba = np.stack([(bits >> s) & 0xFF for s in (0, 8, 16, 24)], -1).astype(np.uint8)
        buf = io.BytesIO()
        PILImage.fromarray(rgba, "RGBA").save(buf, "PNG", compress_level=9, optimize=True)
        raw = buf.getvalue()
        back = np.asarray(PILImage.open(io.BytesIO(raw)).convert("RGBA")).astype(np.uint32)
        rec = (back[..., 0] | (back[..., 1] << 8) | (back[..., 2] << 16)
               | (back[..., 3] << 24)).astype(np.uint32).view(np.float32)
        assert np.array_equal(rec, depth.astype(np.float32)), "depth did not survive the PNG"
        return "data:image/png;base64," + base64.b64encode(raw).decode("ascii"), len(raw)

    n = len(views)
    layers = []
    ind = 1

    def held(frames):
        """Lottie keyframes that do not tween."""
        return [{"t": i, "s": v, "h": 1} for i, v in enumerate(frames)] + [{"t": n}]

    for i, par in enumerate(parents):          # bones first, so joints paint over them
        if par < 0:
            continue
        r, g, b = cols[i]
        verts = [[[round(float(v["jp"][par][0]), 4), round(float(v["jp"][par][1]), 4)],
                  [round(float(v["jp"][i][0]), 4), round(float(v["jp"][i][1]), 4)]] for v in views]
        shapes = [{"ty": "sh", "ind": 0, "nm": "bone",
                   "ks": {"a": 1, "k": [{"t": k, "h": 1,
                                         "s": [{"i": [[0, 0], [0, 0]], "o": [[0, 0], [0, 0]],
                                                "v": vv, "c": False}]}
                                        for k, vv in enumerate(verts)] + [{"t": n}]}},
                  {"ty": "st", "nm": "stroke", "lc": 2, "lj": 1, "w": {"a": 0, "k": 2},
                   "c": {"a": 0, "k": [r / 255, g / 255, b / 255, 1]}, "o": {"a": 0, "k": 100}},
                  {"ty": "tr", "p": {"a": 0, "k": [0, 0]}, "a": {"a": 0, "k": [0, 0]},
                   "s": {"a": 0, "k": [100, 100]}, "r": {"a": 0, "k": 0},
                   "o": {"a": 0, "k": 100}}]
        layers.append({"ddd": 0, "ind": ind, "ty": 4, "nm": "bone_%d" % i, "sr": 1, "ao": 0,
                       "ks": {"o": {"a": 0, "k": 100}, "r": {"a": 0, "k": 0},
                              "p": {"a": 0, "k": [0, 0, 0]}, "a": {"a": 0, "k": [0, 0, 0]},
                              "s": {"a": 0, "k": [100, 100, 100]}},
                       "shapes": [{"ty": "gr", "nm": "g", "it": shapes}],
                       "ip": 0, "op": n, "st": 0, "bm": 0})
        ind += 1

    for i in range(len(labels)):
        r, g, b = cols[i]
        pos = held([[round(float(v["jp"][i][0]), 4), round(float(v["jp"][i][1]), 4)]
                    for v in views])
        # Visibility rides on fill opacity, because a hollow marker would need a stroke.
        opa = held([100 if v["seen"][i] else 35 for v in views])
        shapes = [{"ty": "el", "nm": "dot", "p": {"a": 1, "k": pos},
                   "s": {"a": 0, "k": [10, 10]}},
                  {"ty": "fl", "nm": "fill", "c": {"a": 0, "k": [r / 255, g / 255, b / 255, 1]},
                   "o": {"a": 1, "k": opa}},
                  {"ty": "tr", "p": {"a": 0, "k": [0, 0]}, "a": {"a": 0, "k": [0, 0]},
                   "s": {"a": 0, "k": [100, 100]}, "r": {"a": 0, "k": 0},
                   "o": {"a": 0, "k": 100}}]
        layers.append({"ddd": 0, "ind": ind, "ty": 4, "nm": "joint_%d_%s" % (i, labels[i]),
                       "sr": 1, "ao": 0,
                       "ks": {"o": {"a": 0, "k": 100}, "r": {"a": 0, "k": 0},
                              "p": {"a": 0, "k": [0, 0, 0]}, "a": {"a": 0, "k": [0, 0, 0]},
                              "s": {"a": 0, "k": [100, 100, 100]}},
                       "shapes": [{"ty": "gr", "nm": "g", "it": shapes}],
                       "ip": 0, "op": n, "st": 0, "bm": 0})
        ind += 1

    # THE DEPTH RIDES INSIDE THE ANIMATION, because Lottie embeds rasters the way SVG does:
    # an asset with a data URI and an `ty: 2` image layer pointing at it. One raster per view,
    # held to that view's frame so it changes with the vectors above it.
    #
    # ONLY DEPTH IS EMBEDDED. The matte is `depth > 0` and the shaded body is a ramp between the
    # near and far planes, so both are derivable and neither is stored -- the same reason a
    # parquet here carries no derivable column.
    assets, png_bytes = [], 0
    for k, v in enumerate(views):
        uri, nbytes = depth_png(v["depth"])
        png_bytes += nbytes
        assets.append({"id": "depth_%d" % k, "w": W, "h": H, "u": "", "p": uri, "e": 1})
        layers.append({"ddd": 0, "ind": ind + k, "ty": 2, "nm": "depth_%s" % v["tag"],
                       "refId": "depth_%d" % k, "sr": 1, "ao": 0,
                       "ks": {"o": {"a": 0, "k": 100}, "r": {"a": 0, "k": 0},
                              "p": {"a": 0, "k": [W / 2, H / 2, 0]},
                              "a": {"a": 0, "k": [W / 2, H / 2, 0]},
                              "s": {"a": 0, "k": [100, 100, 100]}},
                       "ip": k, "op": k + 1, "st": 0, "bm": 0})

    doc = {"v": "5.7.4", "fr": fps, "ip": 0, "op": n, "w": W, "h": H, "ddd": 0,
           "nm": "anny-keypoints-multiview", "assets": assets, "layers": layers,
           "meta": {"views": [v["tag"] for v in views],
                    "hold": "every keyframe is h=1; no frame between viewpoints is interpolated",
                    "source": "camera projection, not traced from pixels",
                    "depth_encoding": "float32 metres, IEEE bits across RGBA8, lossless",
                    "derivable_not_stored": ["matte = depth > 0", "shading = ramp(depth)"]}}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)

    # THE ERROR, MEASURED. Read it back and compare every joint against the float it came from.
    got = json.load(open(path, encoding="utf-8"))
    worst = 0.0
    for lay in got["layers"]:
        if not lay["nm"].startswith("joint_"):
            continue
        i = int(lay["nm"].split("_")[1])
        for k, kf in enumerate(lay["shapes"][0]["it"][0]["p"]["k"][:-1]):
            src = views[k]["jp"][i]
            worst = max(worst, abs(kf["s"][0] - float(src[0])), abs(kf["s"][1] - float(src[1])))
    # And the embedded depth, decoded from the file rather than from the array it came from.
    for k, v in enumerate(views):
        uri = [a for a in got["assets"] if a["id"] == "depth_%d" % k][0]["p"]
        raw = base64.b64decode(uri.split(",", 1)[1])
        back = np.asarray(PILImage.open(io.BytesIO(raw)).convert("RGBA")).astype(np.uint32)
        rec = (back[..., 0] | (back[..., 1] << 8) | (back[..., 2] << 16)
               | (back[..., 3] << 24)).astype(np.uint32).view(np.float32)
        assert np.array_equal(rec, v["depth"]), "embedded depth for %s is not exact" % v["tag"]

    n_layers = len(got["layers"])
    return n_layers, worst, png_bytes


# 20 mm, about thirteen stacked credit cards. THIS NUMBER IS NOT SETTLED: joint centres sit
# inside the body, so a strict test calls every joint occluded and a loose one passes every
# joint. It decides a supervised label, so it needs deciding on its own terms.
#
# MEASURED, AND THE NUMBERS SAY IT IS WRONG RATHER THAN MERELY UNSETTLED. At this tolerance
# the rest pose reports 14 of 104 joints unoccluded from the front, 42 from three-quarter and
# 53 from the side. A front view showing the FEWEST visible joints is backwards: the front is
# where a viewer sees most of a body. What the test actually measures is how deep each joint
# centre sits beneath the surface along the view ray, and that is largest for a torso seen
# face-on, so the count tracks body thickness rather than visibility.
#
# It is left as it is, and reported, because changing it would be picking a number to make an
# output look right. Deciding it needs a definition of what a visible joint is -- surface
# depth at the projected pixel, or the joint's own radius -- and that is RFD 107a's work, not
# a constant to nudge here.
TOL = 0.02
manifest = {"seed": SEED, "space": "okhsl", "s": 0.95,
            "encoding": {"hue": "see-through layer", "hue_jitter_deg": 12.0,
                         "lightness": "position along chain within layer",
                         "shape": "filled = unoccluded, hollow = occluded"},
            "occlusion_tol_m": TOL,
            "layers_driven": sorted(groups), "layers_without_bone": missing,
            "keypoints": []}

VIEWS = []
for tag, az in (("front", 0.0), ("three-quarter", 40.0), ("side", 90.0)):
    cam, eye, target, up = camera(az)
    z, hit = render(cam, eye, target, up)
    lo, hi = float(z[hit].min()), float(z[hit].max())
    shade = torch.where(hit, ((hi - z) / (hi - lo)).clamp(0, 1) * 0.55 + 0.10,
                        torch.zeros_like(z))
    rgb = np.repeat((shade.cpu().numpy() * 255).astype(np.uint8)[:, :, None], 3, 2)
    img = Image.fromarray(rgb)
    d = ImageDraw.Draw(img)

    jp = cam.project(joints).detach().cpu().numpy()
    jz = ((torch.cat([joints, torch.ones_like(joints[:, :1])], -1)
           @ cam.view.T)[:, 2]).cpu().numpy()
    zc, hc = z.cpu().numpy(), hit.cpu().numpy()

    # The overlay is drawn on its OWN transparent canvas, not onto the depth. That is what
    # makes it a separable EXR layer rather than something baked into the depth pixels.
    over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(over)

    for i, p in enumerate(parents):                    # sticks first, points on top
        if p < 0:
            continue
        od.line([tuple(jp[p]), tuple(jp[i])], fill=COLS[i] + (255,), width=2)
        d.line([tuple(jp[p]), tuple(jp[i])], fill=COLS[i], width=2)
    nvis = 0
    for i in range(N):
        x, y = float(jp[i][0]), float(jp[i][1])
        xi, yi = int(round(x)), int(round(y))
        on = 0 <= xi < W and 0 <= yi < H and hc[yi, xi]
        seen = bool(on and jz[i] <= zc[yi, xi] + TOL)
        nvis += seen
        box = [x - 5, y - 5, x + 5, y + 5]
        if seen:
            od.ellipse(box, fill=COLS[i] + (255,), outline=(12, 12, 14, 255), width=1)
            d.ellipse(box, fill=COLS[i], outline=(12, 12, 14), width=1)
        else:
            od.ellipse(box, outline=COLS[i] + (255,), width=2)
            d.ellipse(box, outline=COLS[i], width=2)
    img.save(os.path.join(OUT, "anny-%s-keypoints-okhsl.png" % tag))

    seen_flags = []
    for i in range(N):
        x, y = float(jp[i][0]), float(jp[i][1])
        xi, yi = int(round(x)), int(round(y))
        on = 0 <= xi < W and 0 <= yi < H and hc[yi, xi]
        seen_flags.append(bool(on and jz[i] <= zc[yi, xi] + TOL))
    VIEWS.append({"tag": tag, "jp": jp, "seen": seen_flags,
                  "depth": np.where(hc, zc, 0.0).astype(np.float32)})

    print("%-14s depth %.3f..%.3f m   body %d px   %d of %d joints unoccluded"
          % (tag, lo, hi, int(hit.sum()), nvis, N))

nlay, lottie_err, dbytes = write_lottie(os.path.join(OUT, "anny-keypoints-multiview.json"),
                                VIEWS, COLS, labels, parents)
print("lottie: %d views, %d layers, worst coordinate error %.2e px, "
      "%.1f MB of embedded depth, all bit-exact"
      % (len(VIEWS), nlay, lottie_err, dbytes / 1e6))

# Legend grouped by layer, including the layers with no bone, greyed.
ROWH, COLW, PAD = 20, 250, 12
rows = sum(1 + len(groups.get(t, [])) for t in TAG_ORDER) + len(TAG_ORDER)
percol = (rows + 2) // 3
leg = Image.new("RGB", (COLW * 3 + 2 * PAD, ROWH * percol + 40), (250, 249, 245))
ld = ImageDraw.Draw(leg)
ld.text((PAD, 8), "ANNY 104 keypoints grouped by See-Through layer (OKHSL, s=0.95)",
        fill=(20, 20, 24))
r = 0
for t in TAG_ORDER:
    cx, cy = PAD + COLW * (r // percol), 30 + ROWH * (r % percol)
    idx = groups.get(t, [])
    if idx:
        swatch = Color('okhsl', [BASE_HUE[t], 0.95, 0.62]).convert('srgb')
        sw = tuple(int(round(255 * min(max(v, 0.0), 1.0))) for v in swatch[:3])
        ld.rectangle([cx, cy + 3, cx + 14, cy + 15], fill=sw, outline=(50, 50, 54))
        ld.text((cx + 20, cy + 4), "%s  (%d)" % (t, len(idx)), fill=(20, 20, 24))
    else:
        ld.rectangle([cx, cy + 3, cx + 14, cy + 15], fill=(214, 212, 208),
                     outline=(150, 148, 144))
        ld.text((cx + 20, cy + 4), "%s  - no ANNY bone" % t, fill=(130, 128, 124))
    r += 1
    for i in idx:
        cx, cy = PAD + COLW * (r // percol), 30 + ROWH * (r % percol)
        ld.rectangle([cx + 14, cy + 4, cx + 26, cy + 14], fill=COLS[i],
                     outline=(60, 60, 64))
        ld.text((cx + 32, cy + 3), "%3d %s" % (i, labels[i]), fill=(40, 40, 44))
        r += 1
    r += 1

for i in range(N):
    manifest["keypoints"].append(
        {"index": i, "name": labels[i], "parent": int(parents[i]),
         "seethrough_layer": tags[i], "hue_deg": round(HUE[i], 3),
         "lightness": round(LIT[i], 4), "srgb": list(COLS[i])})

leg.save(os.path.join(OUT, "anny-keypoint-legend.png"))
with open(os.path.join(OUT, "anny-keypoint-colours.json"), "w") as fh:
    json.dump(manifest, fh, indent=1)
print("legend + json written to %s" % OUT)
