import os
import sys, time, numpy as np, torch
sys.path.insert(0, os.environ.get(
    "POSE_CONSENSUS_PYTHON", "../3-interactor/pose-consensus/python"))
import silhouette as S
from silhouette import Camera, soft_silhouette, _hard_coverage, _iou_mask, tau_for_bleed, influence_pad, _morton_order, _work_items
from depth_term import soft_depth
import anny
from anny.models.model_data import TopologyConfig

m = anny.Anny(topology=TopologyConfig(base_mesh='makehuman', remove_unattached_vertices=False))
dev, dt = 'cuda', torch.float32
verts = m()['vertices'][0].detach().to(dev, dt)
faces = torch.as_tensor(m.faces.cpu().numpy().astype(np.int64)).to(dev)
W = H = 1024; fx = (W/2)/np.tan(np.radians(40.)/2)
c = verts.mean(0); r = float((verts-c).norm(dim=1).max())*3.0
eye = c + torch.tensor([0.,1.,0.25],device=dev,dtype=dt)*r
fwd=(c-eye); fwd=fwd/fwd.norm(); up=torch.tensor([0.,0.,1.],device=dev,dtype=dt)
s=torch.cross(fwd,up,dim=0); s=s/s.norm(); u=torch.cross(s,fwd,dim=0)
V=torch.eye(4,device=dev,dtype=dt); V[0,:3],V[1,:3],V[2,:3]=s,-u,fwd; V[:3,3]=-(V[:3,:3]@eye)
cam=Camera(width=W,height=H,fx=fx,fy=fx,cx=W/2,cy=H/2,view=V)
tau=tau_for_bleed(0.5,faces.shape[0]); pad=influence_pad(tau,faces.shape[0])
tri=cam.project(verts)[faces]; tri_o=tri[_morton_order(tri)]
hard=_hard_coverage(verts,faces,cam)

print(f"{'max_faces':>9} {'budget':>9} {'items':>7} {'pairs':>10} {'s/img':>8} {'GPU-h/800k':>11} {'IoU':>7}")
for max_faces, budget in ((4096,1.18e8),(1024,1.18e8),(256,1.18e8),(64,1.18e8),(16,1.18e8),(4,1.18e8),(64,8e6),(16,2e6)):
    items=_work_items(tri_o,pad,H,W,budget=budget,max_faces=max_faces)
    pairs=sum((i1-i0)*(y1-y0)*(x1-x0) for i0,i1,y0,y1,x0,x1 in items)
    S.ELEM_BUDGET_TEST=(budget,max_faces)
    def run():
        d,w=soft_depth(verts,faces,cam,cull=True,_items=(budget,max_faces))
        sil=soft_silhouette(verts,faces,cam,cull=True,_items=(budget,max_faces))
        return d,w,sil
    try:
        d,w,sil=run(); torch.cuda.synchronize()
        t0=time.time()
        for _ in range(3): d,w,sil=run()
        torch.cuda.synchronize(); el=(time.time()-t0)/3
        print(f"{max_faces:>9} {budget:>9.1e} {len(items):>7} {pairs:>10.2e} {el:>8.3f} {800000*el/3600:>11.0f} {_iou_mask(sil>0.5,hard):>7.4f}")
    except TypeError as e:
        print("  need _items plumbing:", e); break
