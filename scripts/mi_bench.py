"""Mitsuba 3 as the corpus depth renderer, measured against the torch soft renderer.

THE TRAP THIS SCRIPT AVOIDS. Mitsuba's `depth` AOV is the ray parameter t -- distance from
the pinhole to the hit point -- and every other depth in this pipeline is planar camera-space
z. They agree only at the principal point and diverge toward the corners by 1/cos(angle),
which at a 40 degree field of view is 6% at the edge. That is a wrong depth map that looks
entirely plausible.

So this asks for the world POSITION AOV and transforms it by the same view matrix the torch
path uses. The comparison against soft_depth is then a real check rather than a coincidence.
"""
import os, sys, time
import numpy as np
import torch

sys.path.insert(0, os.environ.get(
    "POSE_CONSENSUS_PYTHON", "../3-interactor/pose-consensus/python"))
import mitsuba as mi
mi.set_variant('cuda_ad_rgb')
print("mitsuba", mi.__version__, "variant", mi.variant())

from silhouette import Camera, _hard_coverage
from depth_term import soft_depth
import anny
from anny.models.model_data import TopologyConfig

dev, dt = 'cuda', torch.float32
m = anny.Anny(topology=TopologyConfig(base_mesh='makehuman', remove_unattached_vertices=False))
verts = m()['vertices'][0].detach().to(dev, dt)
faces = torch.as_tensor(m.faces.cpu().numpy().astype(np.int64)).to(dev)
V, F = verts.shape[0], faces.shape[0]
W = H = 1024
FOV = 40.0

c = verts.mean(0); r = float((verts - c).norm(dim=1).max()) * 3.0
eye = c + torch.tensor([0., 1., 0.25], device=dev, dtype=dt) / \
      torch.tensor([0., 1., 0.25], device=dev, dtype=dt).norm() * r
fwd = (c - eye); fwd = fwd / fwd.norm()
up = torch.tensor([0., 0., 1.], device=dev, dtype=dt)
s = torch.cross(fwd, up, dim=0); s = s / s.norm(); u = torch.cross(s, fwd, dim=0)
view = torch.eye(4, device=dev, dtype=dt)
view[0, :3], view[1, :3], view[2, :3] = s, -u, fwd
view[:3, 3] = -(view[:3, :3] @ eye)
fx = (W / 2) / np.tan(np.radians(FOV) / 2)
cam = Camera(width=W, height=H, fx=fx, fy=fx, cx=W / 2, cy=H / 2, view=view)

mesh = mi.Mesh("body", vertex_count=V, face_count=F,
               has_vertex_normals=False, has_vertex_texcoords=False)
mp = mi.traverse(mesh)
mp['vertex_positions'] = mi.Float(verts.reshape(-1).cpu().numpy())
mp['faces'] = mi.UInt(faces.reshape(-1).to(torch.int32).cpu().numpy())
mp.update()

e, t_, u_ = eye.cpu().numpy(), c.cpu().numpy(), up.cpu().numpy()
scene = mi.load_dict({
    'type': 'scene',
    'integrator': {'type': 'aov', 'aovs': 'pos:position'},
    'sensor': {
        'type': 'perspective', 'fov': FOV, 'fov_axis': 'x',
        'to_world': mi.ScalarTransform4f().look_at(
            origin=[float(e[0]), float(e[1]), float(e[2])],
            target=[float(t_[0]), float(t_[1]), float(t_[2])],
            up=[float(u_[0]), float(u_[1]), float(u_[2])]),
        'film': {'type': 'hdrfilm', 'width': W, 'height': H,
                 'rfilter': {'type': 'box'}, 'pixel_format': 'rgba'},
        'sampler': {'type': 'independent', 'sample_count': 1},
    },
    'body': mesh,
})
params = mi.traverse(scene)
vkey = [k for k in params.keys() if k.endswith('vertex_positions')][0]
print("vertex key:", vkey)


def render_depth():
    img = mi.render(scene, spp=1)
    a = np.array(img)
    return a


a = render_depth()
print("aov image shape", a.shape)


def to_planar_z(a):
    pos = torch.as_tensor(np.ascontiguousarray(a[..., -3:]), device=dev, dtype=dt)
    hom = torch.cat([pos, torch.ones_like(pos[..., :1])], -1)
    return (hom @ view.T)[..., 2]


z_mi = to_planar_z(a)
d_soft, w_soft = soft_depth(verts, faces, cam, max_faces=64)
hard = _hard_coverage(verts, faces, cam)
hit = z_mi > 0
print(f"mitsuba hit px {int(hit.sum())}   torch hard coverage {int(hard.sum())}")
both = hit & hard
print(f"depth agreement over {int(both.sum())} shared px: "
      f"median |mitsuba - soft| {float((z_mi[both] - d_soft[both]).abs().median()):.5f} m")
print(f"mitsuba z {float(z_mi[hit].min()):.4f} .. {float(z_mi[hit].max()):.4f} m")

# timing: geometry changes every frame in the real corpus, so the vertex push counts
torch.cuda.synchronize()
N = 20
t0 = time.time()
for i in range(N):
    jitter = verts + (0.001 * i)
    params[vkey] = mi.Float(jitter.reshape(-1).cpu().numpy())
    params.update()
    img = mi.render(scene, spp=1)
    mi.util.convert_to_bitmap(img)
torch.cuda.synchronize()
el = (time.time() - t0) / N
print(f"mitsuba {el*1000:.1f} ms/img incl. vertex update -> 800k = {800000*el/3600:.1f} GPU-hours")

t0 = time.time()
for i in range(N):
    img = mi.render(scene, spp=1)
torch.cuda.synchronize()
el2 = (time.time() - t0) / N
print(f"mitsuba {el2*1000:.1f} ms/img render only     -> 800k = {800000*el2/3600:.1f} GPU-hours")
print(f"torch soft baseline 3451 ms/img              -> 800k = 767 GPU-hours")
