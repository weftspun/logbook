# Logbook: the soft renderer's three constants, and Mitsuba

Apparatus: `scripts/bench1024.py`, `scripts/bench_cull.py`, `scripts/sweep.py`,
`scripts/mi_bench.py`, `scripts/mi_bench2.py`, `scripts/samples.py`,
`scripts/keypoint_render.py`. All measured on the local 4090, ANNY at 19,158 vertices and
27,420 faces, unless a line says otherwise.

Chasing why `soft_depth` returned depths of 2.0e5 to 4.5e8 for a body 1.7 m tall at 5 m.

## It was not `tau`

`soft_depth` evaluated the perspective-correct `1/inv` at pixels OUTSIDE each triangle, where
the barycentric weights go negative, `inv` crosses zero, and `clamp(min=1e-9)` returns 1e9.

    inside the triangles     z_px  2.873 .. 2.922      correct
    over all pixels          z_px  0.0 .. 1.000e+09
    true face depth range          2.701 .. 3.318

No `tau` suppresses it. The sigmoid is 0.5 ON the edge by construction, so a pixel just
outside contributes half of 1e9. Bounding `z_px` to the triangle's own corner depths fixes it
and changes nothing inside: a perspective-correct interpolation is a convex combination of the
corners, so the clamp is inactive on every correct pixel and every correct gradient.

Result: **2.73 .. 3.31 m** against a true vertex range of 2.69 .. 3.33.

## `tau` was wrong somewhere else, and by a factor of ln F

`soft_silhouette` accumulates `sigmoid(d / tau)` over EVERY face, so a background pixel gets a
small non-zero contribution from all of them and coverage bleeds out to about `tau * ln F`.

One square, refined in place, outline fixed, so face count is the only variable:

| faces | hard  | default tau | retracted tau = 1.0 |
| ----- | ----- | ----------- | ------------------- |
| 2     | 1,089 | IoU 0.972   | **IoU 0.996**       |
| 32    | 1,089 | 0.994       | 0.954               |
| 288   | 1,089 | 1.000       | 0.799               |
| 1,152 | 1,089 | 1.000       | 0.672               |
| 4,608 | 1,089 | 1.000       | 0.534               |

The old constant is at its BEST on the two-face quad every test used, and degrades
monotonically from there. `tau` is now a pixel bleed budget, `tau_for_bleed(px, n_faces)`. On
ANNY the silhouette went from **IoU 0.100 to 0.966**.

## And `chunk` was sized for 256x256

A constant with no reference to pixel count. Each `(chunk, P)` intermediate at 2048 faces:

    256x256      0.54 GB     fits
    1024x1024    8.6 GB      ten of these is 86 GB

At 1024x1024 the card sat at 24,041 MiB of 24,564 at 100% and never finished. It did not
raise: an allocator at its ceiling thrashes rather than failing, so the symptom is a render
that never returns.

**Retracted.** The first fix counted ten live intermediates and set a 1.5 GB budget. Peak was
2.39 GiB at 572 faces over 65,536 pixels, which is 68 bytes for each element, so 17 float32s
are live. The conservative budget then cost 8x in launch overhead: 9.21 s against 1.09 s.

## The common shape of all three

Every one was correct where it was measured and wrong elsewhere, and every control in both
files used `_quad`, which has two faces. The tests were not weak. They were run at one scale.

## Mitsuba 3 against the torch renderer

| renderer                                   | per image   | 800k images       |
| ------------------------------------------ | ----------- | ----------------- |
| `soft_depth` + `soft_silhouette`           | 3,451 ms    | 767 GPU-hours     |
| torch exact z-buffer                       | 225 ms      | 50 GPU-hours      |
| **Mitsuba 3, incl. vertex update and BVH** | **1.79 ms** | **0.4 GPU-hours** |

Mitsuba 3 is BSD-3-Clause, so it clears the licence bar that excludes nvdiffrast.

Agreement with an exact z-buffer over 102,520 shared pixels: **median 0.536 mm**, about
two thirds of a credit card's thickness.

**The trap, quantified rather than asserted.** Mitsuba's `depth` AOV is the ray parameter t,
and every other depth here is planar camera-space z. Using it directly would have been wrong
by a median of 10.4 mm and up to 137 mm, about three golf balls, in a map that looks entirely
plausible. Ask for the `position` AOV and transform by the same view matrix.

**Two measurements that flattered the first pass, both corrected.** The hit mask was `z > 0`,
but a miss returns world position (0,0,0), which the view matrix maps to a positive z, so all
1,048,576 pixels read as hits. And `mi.render` is lazy: `torch.cuda.synchronize()` does not
sync Dr.Jit, so the first "0.9 ms render only" timed the enqueue. `dr.sync_thread()` is
required.

Same seed returns a bit-identical image. A different seed changes every body pixel, because
`independent` jitters within the pixel. So the seed is what makes a corpus reproducible, which
is what the constructed-synthetic rule asks for.

## Still open

Joint visibility. Joint centres sit inside the body, so a strict depth test calls every joint
occluded and a loose tolerance passes every joint. At 20 mm one view reported 104 of 104
visible, which is not credible from any angle. It decides a supervised label and needs
deciding on its own terms.
