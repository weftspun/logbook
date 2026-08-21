"""Sample corpus renders: Mitsuba depth, keypoints coloured by See-Through layer in OKHSL.

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

TAG ORDER IS ANATOMICAL, head to foot, so adjacent tags sit 15 degrees apart and the head
group, the leg group and so on each occupy a contiguous arc.

THE GAP THIS MAKES VISIBLE. ANNY drives 9 of See-Through's 24 tags. The other 15 have no bone
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
from coloraide import Color

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


def write_exr(path, z, hit, overlay):
    """Two layers in one EXR: depth as the default layer, skeleton as `skeleton.*`.

    The default layer carries Z AND A. Without the coverage channel, background has to be
    encoded in Z itself, and every sentinel for it is a number a reader can mistake for a
    depth -- 0 reads as the camera plane, a large value reads as a far surface. A separate
    alpha says "nothing here" in a way that cannot be confused with a measurement.

    Channel names without a prefix form the default layer; `skeleton.` prefixed channels form
    a second one. tev, DJV and Nuke all group them that way.
    """
    zc = z.detach().cpu().numpy().astype(np.float32)
    hc = hit.detach().cpu().numpy()
    ov = np.asarray(overlay, dtype=np.uint8)
    rgb = srgb_to_linear(ov[..., :3])
    alpha = (ov[..., 3].astype(np.float32) / 255.0)
    planes = np.concatenate([
        np.where(hc, zc, 0.0).astype(np.float32)[..., None],
        hc.astype(np.float32)[..., None],
        rgb * alpha[..., None],                       # premultiplied, as Mitsuba tags it
        alpha[..., None],
    ], axis=-1)
    names = ['Z', 'A', 'skeleton.R', 'skeleton.G', 'skeleton.B', 'skeleton.A']
    bmp = mi.Bitmap(planes, pixel_format=mi.Bitmap.PixelFormat.MultiChannel,
                    channel_names=names)
    bmp.write(path)
    back = mi.Bitmap(path)
    got = [c.name for c in back.struct_()]
    assert got == names, "EXR channels came back as %r" % got
    return got


# 20 mm, about thirteen stacked credit cards. THIS NUMBER IS NOT SETTLED: joint centres sit
# inside the body, so a strict test calls every joint occluded and a loose one passes every
# joint. It decides a supervised label, so it needs deciding on its own terms.
TOL = 0.02
manifest = {"seed": SEED, "space": "okhsl", "s": 0.95,
            "encoding": {"hue": "see-through layer", "hue_jitter_deg": 12.0,
                         "lightness": "position along chain within layer",
                         "shape": "filled = unoccluded, hollow = occluded"},
            "occlusion_tol_m": TOL,
            "layers_driven": sorted(groups), "layers_without_bone": missing,
            "keypoints": []}

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

    write_exr(os.path.join(OUT, "anny-%s.exr" % tag), z, hit, over)
    print("%-14s depth %.3f..%.3f m   body %d px   %d of %d joints unoccluded"
          % (tag, lo, hi, int(hit.sum()), nvis, N))

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
