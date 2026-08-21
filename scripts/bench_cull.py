import os
import sys, time, numpy as np, torch
sys.path.insert(0, os.environ.get(
    "POSE_CONSENSUS_PYTHON", "../3-interactor/pose-consensus/python"))
from silhouette import (Camera, soft_silhouette, _hard_coverage, _iou_mask,
                        tau_for_bleed, influence_pad, _morton_order, _work_items)
from depth_term import soft_depth
import anny
from anny.models.model_data import TopologyConfig

m = anny.Anny(topology=TopologyConfig(base_mesh='makehuman', remove_unattached_vertices=False))
dev, dt = 'cuda', torch.float32
verts = m()['vertices'][0].detach().to(dev, dt)
faces = torch.as_tensor(m.faces.cpu().numpy().astype(np.int64)).to(dev)

W = H = 1024
fx = (W / 2) / np.tan(np.radians(40.) / 2)
c = verts.mean(0); r = float((verts - c).norm(dim=1).max()) * 3.0
eye = c + torch.tensor([0., 1., 0.25], device=dev, dtype=dt) * r
fwd = (c - eye); fwd = fwd / fwd.norm(); up = torch.tensor([0., 0., 1.], device=dev, dtype=dt)
s = torch.cross(fwd, up, dim=0); s = s / s.norm(); u = torch.cross(s, fwd, dim=0)
V = torch.eye(4, device=dev, dtype=dt); V[0, :3], V[1, :3], V[2, :3] = s, -u, fwd
V[:3, 3] = -(V[:3, :3] @ eye)
cam = Camera(width=W, height=H, fx=fx, fy=fx, cx=W / 2, cy=H / 2, view=V)

tau = tau_for_bleed(0.5, faces.shape[0]); pad = influence_pad(tau, faces.shape[0])
tri = cam.project(verts)[faces]
items = _work_items(tri[_morton_order(tri)], pad, H, W)
cost = sum((i1 - i0) * (y1 - y0) * (x1 - x0) for i0, i1, y0, y1, x0, x1 in items)
print(f"tau {tau:.4f} px   pad {pad:.2f} px")
print(f"work items {len(items)}   face-pixel pairs {cost:.3e}"
      f"   vs unculled {faces.shape[0] * H * W:.3e}   ({faces.shape[0] * H * W / cost:.0f}x less)")

hard = _hard_coverage(verts, faces, cam)
for label, cull in (("culled", True), ("reference", False)):
    torch.cuda.reset_peak_memory_stats()
    d, w = soft_depth(verts, faces, cam, cull=cull)
    sil = soft_silhouette(verts, faces, cam, cull=cull)
    torch.cuda.synchronize()
    n = 3 if cull else 1
    t0 = time.time()
    for _ in range(n):
        d, w = soft_depth(verts, faces, cam, cull=cull)
        sil = soft_silhouette(verts, faces, cam, cull=cull)
    torch.cuda.synchronize(); el = (time.time() - t0) / n
    print(f"{label:10s} {el:8.3f} s/img   peak {torch.cuda.max_memory_allocated()/2**30:5.2f} GiB"
          f"   IoU {_iou_mask(sil > 0.5, hard):.4f}"
          f"   depth {float(d[hard].min()):.3f}..{float(d[hard].max()):.3f} m"
          f"   -> 800k = {800000 * el / 3600:.0f} GPU-h")
