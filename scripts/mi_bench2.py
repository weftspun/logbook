"""Mitsuba 3 depth, verified against an exact z-buffer and timed with Dr.Jit actually synced.

Three defects in the first pass, each of which flattered the result:
  * the hit mask was `z > 0`, but a MISS returns world position (0,0,0), which the view matrix
    maps to a positive z. So every one of 1,048,576 pixels read as a hit.
  * `mi.render` is lazy and `torch.cuda.synchronize()` does not sync Dr.Jit. The "0.9 ms"
    render-only figure timed the enqueue, not the work.
  * the reference was `soft_depth`, which is a softmin BLEND of front and back surfaces, not
    the nearest one. It cannot referee an exact renderer; it disagreed by 39 mm and that
    disagreement was the softness, not an error.
"""
import os, sys, time
import numpy as np
import torch
import drjit as dr

sys.path.insert(0, os.environ.get(
    "POSE_CONSENSUS_PYTHON", "../3-interactor/pose-consensus/python"))
import mitsuba as mi
mi.set_variant('cuda_ad_rgb')

from silhouette import Camera, _morton_order, _work_items, _block_pixels
import anny
from anny.models.model_data import TopologyConfig

dev, dt = 'cuda', torch.float32
m = anny.Anny(topology=TopologyConfig(base_mesh='makehuman', remove_unattached_vertices=False))
verts = m()['vertices'][0].detach().to(dev, dt)
faces = torch.as_tensor(m.faces.cpu().numpy().astype(np.int64)).to(dev)
V, F = verts.shape[0], faces.shape[0]
W = H = 1024; FOV = 40.0

c = verts.mean(0)
off = torch.tensor([0., 1., 0.25], device=dev, dtype=dt)
eye = c + off / off.norm() * float((verts - c).norm(dim=1).max()) * 3.0
fwd = (c - eye); fwd = fwd / fwd.norm()
up = torch.tensor([0., 0., 1.], device=dev, dtype=dt)
s = torch.cross(fwd, up, dim=0); s = s / s.norm(); u = torch.cross(s, fwd, dim=0)
view = torch.eye(4, device=dev, dtype=dt)
view[0, :3], view[1, :3], view[2, :3] = s, -u, fwd
view[:3, 3] = -(view[:3, :3] @ eye)
fx = (W / 2) / np.tan(np.radians(FOV) / 2)
cam = Camera(width=W, height=H, fx=fx, fy=fx, cx=W / 2, cy=H / 2, view=view)


def exact_zbuffer(verts, faces, cam):
    """Nearest-surface depth by z-buffer. The reference: no softness, no rays, no tau."""
    tri2d = cam.project(verts)[faces]
    v_cam = (cam.view @ torch.cat([verts, torch.ones_like(verts[:, :1])], -1).T).T[:, :3]
    z_vert = v_cam[:, 2].clamp(min=1e-4)[faces]
    order = _morton_order(tri2d)
    tri2d, z_vert = tri2d[order], z_vert[order]
    zbuf = torch.full((cam.height * cam.width,), float('inf'), device=verts.device)
    for i0, i1, y0, y1, x0, x1 in _work_items(tri2d, 0.0, cam.height, cam.width, max_faces=256):
        px, idx = _block_pixels(y0, y1, x0, x1, cam.width, verts.device, verts.dtype)
        t = tri2d[i0:i1]; a, b, cc = t[:, 0], t[:, 1], t[:, 2]
        cr = lambda p, q: p[..., 0] * q[..., 1] - p[..., 1] * q[..., 0]
        area = cr(b - a, cc - a)[:, None]
        safe = torch.where(area.abs() < 1e-12, torch.full_like(area, 1e-12), area)
        P = px[None]
        wa = cr(cc[:, None] - b[:, None], P - b[:, None]) / safe
        wb = cr(a[:, None] - cc[:, None], P - cc[:, None]) / safe
        wc = 1.0 - wa - wb
        zc = z_vert[i0:i1]
        inv = wa / zc[:, 0, None] + wb / zc[:, 1, None] + wc / zc[:, 2, None]
        z = 1.0 / inv.clamp(min=1e-9)
        ok = (wa >= 0) & (wb >= 0) & (wc >= 0) & (z > 0)
        z = torch.where(ok, z, torch.full_like(z, float('inf')))
        zbuf.scatter_reduce_(0, idx, z.min(0).values, reduce='amin')
    return zbuf.reshape(cam.height, cam.width)


mesh = mi.Mesh("body", vertex_count=V, face_count=F,
               has_vertex_normals=False, has_vertex_texcoords=False)
mp = mi.traverse(mesh)
mp['vertex_positions'] = mi.Float(verts.reshape(-1).cpu().numpy())
mp['faces'] = mi.UInt(faces.reshape(-1).to(torch.int32).cpu().numpy())
mp.update()

e, t_, u_ = eye.cpu().numpy(), c.cpu().numpy(), up.cpu().numpy()
scene = mi.load_dict({
    'type': 'scene',
    # `t:depth` is the ray parameter and is EXACTLY 0 on a miss, which is the hit mask.
    # `pos:position` is what becomes planar z. Both, because neither alone is enough.
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
params = mi.traverse(scene)
vkey = [k for k in params.keys() if k.endswith('vertex_positions')][0]

img = mi.render(scene, spp=1)
a = np.array(img)
print("aov channels:", a.shape)
pos = torch.as_tensor(np.ascontiguousarray(a[..., 0:3]), device=dev, dtype=dt)
tray = torch.as_tensor(np.ascontiguousarray(a[..., 3]), device=dev, dtype=dt)
hit = tray > 0
z_mi = ((torch.cat([pos, torch.ones_like(pos[..., :1])], -1)) @ view.T)[..., 2]

zb = exact_zbuffer(verts, faces, cam)
zhit = torch.isfinite(zb)
print(f"mitsuba hits {int(hit.sum())} px   z-buffer hits {int(zhit.sum())} px"
      f"   symmetric difference {int((hit ^ zhit).sum())} px")
both = hit & zhit
dif = (z_mi[both] - zb[both]).abs()
print(f"depth vs exact z-buffer over {int(both.sum())} px: "
      f"median {float(dif.median())*1000:.4f} mm   max {float(dif.max())*1000:.3f} mm")
print(f"planar z range {float(z_mi[hit].min()):.4f} .. {float(z_mi[hit].max()):.4f} m")

# the t-vs-z trap, quantified rather than asserted
dz = (tray[both] - z_mi[both]).abs()
print(f"if we had used the `depth` AOV directly: median error {float(dz.median())*1000:.1f} mm"
      f"   max {float(dz.max())*1000:.1f} mm")

# timing, with Dr.Jit actually synced
def timed(n, update):
    dr.sync_thread(); torch.cuda.synchronize()
    t0 = time.time()
    for i in range(n):
        if update:
            params[vkey] = mi.Float((verts + 0.0005 * i).reshape(-1).cpu().numpy())
            params.update()
        out = mi.render(scene, spp=1)
        dr.eval(out)
    dr.sync_thread(); torch.cuda.synchronize()
    return (time.time() - t0) / n

for label, upd in (("render only", False), ("incl. vertex update + BVH", True)):
    el = timed(30, upd)
    print(f"mitsuba {label:28s} {el*1000:7.2f} ms/img -> 800k = {800000*el/3600:6.1f} GPU-hours")

torch.cuda.synchronize(); t0 = time.time()
for _ in range(3): zb = exact_zbuffer(verts, faces, cam)
torch.cuda.synchronize(); el = (time.time() - t0) / 3
print(f"torch exact z-buffer         {el*1000:7.2f} ms/img -> 800k = {800000*el/3600:6.1f} GPU-hours")
print(f"torch soft_depth (baseline)   3451.00 ms/img -> 800k =  767.0 GPU-hours")

# ---- where the 216 mm lives, and whether a corpus render is reproducible -------------
import torch.nn.functional as Fn
inner = zhit.float()[None, None]
inner = (Fn.avg_pool2d(inner, 5, 1, 2) > 0.999)[0, 0] & both   # 2 px in from any edge
dif_in = (z_mi[inner] - zb[inner]).abs()
print(f"INTERIOR only ({int(inner.sum())} px): median {float(dif_in.median())*1000:.4f} mm"
      f"   max {float(dif_in.max())*1000:.3f} mm")
edge = both & ~inner
print(f"EDGE band     ({int(edge.sum())} px): median "
      f"{float((z_mi[edge]-zb[edge]).abs().median())*1000:.3f} mm   max "
      f"{float((z_mi[edge]-zb[edge]).abs().max())*1000:.3f} mm")

def render_seed(seed):
    out = mi.render(scene, spp=1, seed=seed)
    dr.eval(out); dr.sync_thread()
    return np.array(out)

a1, a2, a3 = render_seed(0), render_seed(0), render_seed(1)
print(f"same seed twice   : identical = {np.array_equal(a1, a2)}")
d13 = np.abs(a1[..., 3] - a3[..., 3])
print(f"seed 0 vs seed 1  : {int((d13 > 0).sum())} px differ, max {d13.max()*1000:.2f} mm")
