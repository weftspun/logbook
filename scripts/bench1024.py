import os
import sys, time, numpy as np, torch
sys.path.insert(0, os.environ.get(
    "POSE_CONSENSUS_PYTHON", "../3-interactor/pose-consensus/python"))
from silhouette import Camera, soft_silhouette, _hard_coverage, _iou_mask, tau_for_bleed, chunk_for
from depth_term import soft_depth
import anny
from anny.models.model_data import TopologyConfig

m = anny.Anny(topology=TopologyConfig(base_mesh='makehuman', remove_unattached_vertices=False))
dev, dt = 'cuda', torch.float32
verts = m()['vertices'][0].detach().to(dev, dt)
faces = torch.as_tensor(m.faces.cpu().numpy().astype(np.int64)).to(dev)

for W in (256, 512, 1024):
    H = W; fx = (W / 2) / np.tan(np.radians(40.) / 2)
    c = verts.mean(0); r = float((verts - c).norm(dim=1).max()) * 3.0
    eye = c + torch.tensor([0., 1., 0.25], device=dev, dtype=dt) * r
    fwd = (c - eye); fwd = fwd / fwd.norm(); up = torch.tensor([0., 0., 1.], device=dev, dtype=dt)
    s = torch.cross(fwd, up, dim=0); s = s / s.norm(); u = torch.cross(s, fwd, dim=0)
    V = torch.eye(4, device=dev, dtype=dt); V[0, :3], V[1, :3], V[2, :3] = s, -u, fwd
    V[:3, 3] = -(V[:3, :3] @ eye)
    cam = Camera(width=W, height=H, fx=fx, fy=fx, cx=W / 2, cy=H / 2, view=V)

    torch.cuda.reset_peak_memory_stats()
    d, w = soft_depth(verts, faces, cam); sil = soft_silhouette(verts, faces, cam)
    torch.cuda.synchronize()
    t0 = time.time()
    for _ in range(3):
        d, w = soft_depth(verts, faces, cam); sil = soft_silhouette(verts, faces, cam)
    torch.cuda.synchronize(); el = (time.time() - t0) / 3

    hard = _hard_coverage(verts, faces, cam)          # GPU float32, same device
    zc = (cam.view @ torch.cat([verts, torch.ones_like(verts[:, :1])], -1).T).T[:, 2]
    print(f"{W}x{W}  tau {tau_for_bleed(0.5, faces.shape[0]):.4f} px  chunk {chunk_for(W*H)} faces  peak {torch.cuda.max_memory_allocated()/2**30:.2f} GiB")
    print(f"   depth over body  {float(d[hard].min()):.4f} .. {float(d[hard].max()):.4f} m"
          f"   (true verts {float(zc.min()):.4f} .. {float(zc.max()):.4f})")
    print(f"   silhouette IoU   {_iou_mask(sil > 0.5, hard):.4f}"
          f"   ({int(hard.sum())} px hard, {int((sil > 0.5).sum())} px soft)")
    print(f"   per image        {el:.3f} s  -> 800k = {800000 * el / 3600:.0f} GPU-hours")
