import os, sys, time, numpy as np, torch
sys.path.insert(0, os.environ.get(
    "POSE_CONSENSUS_PYTHON", "../3-interactor/pose-consensus/python"))
from PIL import Image, ImageDraw
from silhouette import (Camera, soft_silhouette, _hard_coverage, _iou_mask,
                        tau_for_bleed, influence_pad, _morton_order, _work_items)
from depth_term import soft_depth
import anny
from anny.models.model_data import TopologyConfig

OUT = os.environ.get("LOGBOOK_OUT", ".")
dev, dt = 'cuda', torch.float32
assert torch.cuda.is_available(), "GPU required"
print("device:", torch.cuda.get_device_name(0))

m = anny.Anny(topology=TopologyConfig(base_mesh='makehuman', remove_unattached_vertices=False))
out = m()
verts = out['vertices'][0].detach().to(dev, dt)
joints = out['bone_poses'][0].detach().to(dev, dt)[:, :3, 3]      # 104 joint centres
faces = torch.as_tensor(m.faces.cpu().numpy().astype(np.int64)).to(dev)
W = H = 1024


def camera(az_deg, elev=0.25, dist=3.0):
    fx = (W / 2) / np.tan(np.radians(40.) / 2)
    c = verts.mean(0); r = float((verts - c).norm(dim=1).max()) * dist
    a = np.radians(az_deg)
    off = torch.tensor([float(np.sin(a)), float(np.cos(a)), elev], device=dev, dtype=dt)
    eye = c + off / off.norm() * r
    fwd = (c - eye); fwd = fwd / fwd.norm()
    up = torch.tensor([0., 0., 1.], device=dev, dtype=dt)
    s = torch.cross(fwd, up, dim=0); s = s / s.norm(); u = torch.cross(s, fwd, dim=0)
    V = torch.eye(4, device=dev, dtype=dt); V[0, :3], V[1, :3], V[2, :3] = s, -u, fwd
    V[:3, 3] = -(V[:3, :3] @ eye)
    return Camera(width=W, height=H, fx=fx, fy=fx, cx=W / 2, cy=H / 2, view=V)


# ---- the throughput sweep: block size against work and wall time --------------------
cam = camera(0.0)
tau = tau_for_bleed(0.5, faces.shape[0]); pad = influence_pad(tau, faces.shape[0])
tri = cam.project(verts)[faces]; tri_o = tri[_morton_order(tri)]
hard = _hard_coverage(verts, faces, cam)
print(f"\n{'max_faces':>9} {'items':>6} {'pairs':>10} {'s/img':>8} {'GPU-h/800k':>11} {'IoU':>7} {'peak GiB':>9}")
best = None
for mf in (64,):
    items = _work_items(tri_o, pad, H, W, max_faces=mf)
    pairs = sum((i1 - i0) * (y1 - y0) * (x1 - x0) for i0, i1, y0, y1, x0, x1 in items)
    torch.cuda.reset_peak_memory_stats()

    def run():
        d, w = soft_depth(verts, faces, cam, max_faces=mf)
        s_ = soft_silhouette(verts, faces, cam, max_faces=mf)
        return d, w, s_
    d, w, sil = run(); torch.cuda.synchronize()
    t0 = time.time()
    for _ in range(3):
        d, w, sil = run()
    torch.cuda.synchronize(); el = (time.time() - t0) / 3
    iou = _iou_mask(sil > 0.5, hard)
    pk = torch.cuda.max_memory_allocated() / 2**30
    print(f"{mf:>9} {len(items):>6} {pairs:>10.2e} {el:>8.3f} {800000*el/3600:>11.0f} {iou:>7.4f} {pk:>9.2f}")
    if best is None or el < best[1]:
        best = (mf, el)
print(f"\nfastest: max_faces={best[0]} at {best[1]:.3f} s/img")

# ---- samples ------------------------------------------------------------------------
MF = best[0]
for tag, az in (("front", 0.0), ("three-quarter", 40.0), ("side", 90.0)):
    cam = camera(az)
    d, w = soft_depth(verts, faces, cam, max_faces=MF)
    sil = soft_silhouette(verts, faces, cam, max_faces=MF)
    body = (sil > 0.5)

    dn = d.clone()
    lo, hi = float(d[body].min()), float(d[body].max())
    dn = ((hi - dn) / (hi - lo)).clamp(0, 1)          # near is bright
    dn = torch.where(body, dn, torch.zeros_like(dn))
    Image.fromarray((dn.cpu().numpy() * 65535).astype(np.uint16)).save(
        os.path.join(OUT, f"anny-{tag}-depth16.png"))
    Image.fromarray((body.cpu().numpy() * 255).astype(np.uint8)).save(
        os.path.join(OUT, f"anny-{tag}-silhouette.png"))

    # keypoints on the depth, coloured by whether the body is in front of the joint
    jp = cam.project(joints).detach()
    jc = (cam.view @ torch.cat([joints, torch.ones_like(joints[:, :1])], -1).T).T[:, 2]
    rgb = np.repeat((dn.cpu().numpy() * 255).astype(np.uint8)[:, :, None], 3, 2)
    img = Image.fromarray(rgb); dr = ImageDraw.Draw(img)
    TOL = 0.10                                        # about the width of a fist
    dcpu, bcpu = d.cpu().numpy(), body.cpu().numpy()
    nvis = 0
    for (x, y), z in zip(jp.cpu().numpy(), jc.cpu().numpy()):
        xi, yi = int(round(x)), int(round(y))
        if not (0 <= xi < W and 0 <= yi < H and bcpu[yi, xi]):
            continue
        seen = z <= dcpu[yi, xi] + TOL
        nvis += bool(seen)
        col = (14, 200, 220) if seen else (255, 90, 30)
        dr.ellipse([x - 6, y - 6, x + 6, y + 6], outline=col, width=3)
    img.save(os.path.join(OUT, f"anny-{tag}-keypoints.png"))
    print(f"{tag:14s} depth {lo:.3f}..{hi:.3f} m   body {int(body.sum())} px   "
          f"{nvis} of {joints.shape[0]} joints on-body and in front")
print("\nwrote 9 PNGs to", OUT)
