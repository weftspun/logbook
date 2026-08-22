# Logbook: what an edge NPU takes, and what the ANNY forward will not export

Apparatus: `rf-detr-cpp/scripts/gate_onnx_device.py` (macOS, no accelerator),
`rf-detr-cpp/scripts/gate_dfc_parse.py` and `deploy/hailo-dfc/` (Hailo Dataflow Compiler
5.3.0 on a Fly machine, since the wheel is `linux_x86_64` only),
`rf-detr-cpp/scripts/fold_static_tile.py`. ANNY measurements use `anny` 0.6.0 from PyPI on
the Mac. Every throughput figure divides by 40 TOPS INT4 at an ASSUMED 30% utilisation; the
DFC profiler was not run, so treat those as a ranking and not a budget.

Question: can the wholebody chain deploy to an 8 GB, 20 TOPS INT8 / 40 INT4 USB part.

## The chain partitions by kind, not by size

`lbfgs_polish.py` line 16 builds the model `.to(dtype=torch.float64)`. The part carries INT8
activations. Three of the six stages in RFD 107a are descent loops and mesh operations, and
no quantity of devices changes that.

Measured shares at 1272, backbone against decoder:

    backbone      1399.3 ms   95.0% of wall
    transformer     68.6 ms    4.7%

Everything the compiler refuses sits in the 4.7%.

## Two documented facts turned out to be the blockers

Neither was written with a compiler in mind. `rf-detr-cpp/docs/decisions/backbone-windowing.md`
records that windowing happens once, at the embeddings stage, by expanding the batch
dimension. `0002-position-embed-bicubic.md` records the antialias resize of the position
embeddings. DFC 5.3.0 refuses both.

    num_windows=2   868 nodes   REJECTED
    num_windows=1   825 nodes   PARSE OK

Same model, same resolution, same folds applied to both. `Tile` count falls to 0 and the
embeddings concat is absent from the graph entirely.

Cost of losing windowing, measured at 576: **1.35x wall-clock**, 238.4 ms against 175.9 ms.

## Retracted: 0.83x, from MAC counting

A first pass counted MACs from the ONNX graph and reported `num_windows=1` as CHEAPER, at
0.83x. That number is wrong. Shape inference left 51 nodes of the `num_windows=1` graph
unresolved and the counter skipped them silently. Simplifying at a fixed input shape first
resolves them, and the corrected count is 107.9 GMAC against 76.5, a ratio of 1.37x that
agrees with wall-clock. A MAC count that does not report its unresolved nodes is not a
measurement.

## Retracted: three theories about why, all wrong

The first error the DFC reports is `IndexError: list index out of range` inside LayerNorm
axis mapping, from an empty `input_format`. Three explanations were proposed and each was
tested with a minimal reproduction:

    rank-3 LayerNorm alone            PARSE OK
    window reshape then LayerNorm     PARSE OK
    CLS concat producing 577 tokens   PARSE OK

All three pass in isolation and fail inside the real graph. Format inference is whole-graph,
so a toy that parses proves nothing. The honest error appears only when `end_node_names` is
passed, and it names `Tile`: unsupported concat over axis batch. The IndexError is a
downstream symptom of the simplify-and-retry path.

Hailo's own Model Zoo settles the CLS question independently: it ships timm ViTs and parses
them whole with no start or end node overrides, and ViT-Base is 197 tokens, which is prime.

## The compiled graph

825 ONNX nodes become 336 Hailo layers. Clipped to
`rf-detr-cpp/docs/measurements/hailo10h-backbone-576-nw1.hn.zst`, 6 KB.

    130 normalization   65 conv   46 layer_normalization   25 ew_add
     24 matmul          14 feature_splitter   12 softmax    4 concat

`layer_normalization` compiles 46 times and `concat` 4 times, so neither is unsupported. Only
concat over the batch axis is, which is what windowing produces.

The HAR itself is 102.5 MB and is not kept. 101.4 MB of it is `windows_1.npz`, weights that
duplicate a checkpoint already held. zstd compresses the whole HAR by 8.5% and `-19` is no
better than `-3`, because float32 weights are near entropy. The `.hn` compresses 41.8x.

## Resolution is the throughput lever, measured

Whole model, `num_windows=1`, backbone plus a plain-DETR decoder, at 30% utilisation:

    res    tokens    GMAC   INT8    INT4
    288       576    17.8   168f    337f
    336       784    25.8   139f    279f
    384      1024    35.9    84f    167f
    432      1296    48.7    62f    123f
    576      2304   107.9    28f     56f

1280 is not reachable: the keypoint variant is patch 12 with 2 windows, so resolution must
divide by 24, and 1280 does not. `AssertionError: Backbone requires input shape to be
divisible by 24`. The 12xx options are 1200, 1224, 1248, 1272, 1296.

Four cameras at 432 and 120 fps needs 117% of one part at PERFECT utilisation. Asymmetric
fits: three body cameras at 288 with one face camera at 432, 120 fps, is 61%.

Framing sets precision, not resolution. Feature stride is 12 input pixels, so at 432 a 1.7 m
subject filling the frame gives 47 mm, about a golf ball, while a 200 mm face filling a
dedicated camera gives 5.6 mm, about a pencil. 45x from framing alone.

## The ANNY forward does not export

`anny` 0.6.0 confirms three claims in RFD 107a's DETAILS: `bone_count` is 104,
`data/keypoints/coco.pth` carries 23 keypoints rather than 17, and its weight vectors are
19,158 wide while `topology="anny"` returns 13,718 vertices. The documented mismatch
reproduces exactly.

The forward is differentiable, with `grad_fn: LinearBlendSkinningBackward`, and it does not
export:

    TypeError: The '_length_' attribute must be an integer

That is ctypes, inside Warp, refusing to be traced. Warp initialises on import.

## Linear blend skinning decomposes exactly

    vertices = sum_k w[v,k] * (M[i[v,k]] @ inv(RB)[i[v,k]]) @ [rest[v], 1]

against `anny`'s own output, at float64:

    bone_poses                            max|diff| 8.471e-01
    bone_poses @ inv(rest_bone_poses)     max|diff| 4.441e-16   MATCH
    inv(rest_bone_poses) @ bone_poses     max|diff| 1.024e+00

4.441e-16 is float64 epsilon, so this establishes the algebra and NOTHING about float32 or
INT8. `inv(rest_bone_poses)` is constant and folds to an initializer.

**The rest it skins is the CORRECTED rest, not the template.** The match above uses
`rest_vertices` from the forward's own output rather than the `template_vertices` buffer, so
the blendshape correctives are already in it. ANNY carries `blendshapes` at (624, 13718, 3)
with `bone_heads_blendshapes` (624, 104, 3) and `bone_orientation_blendshapes`
(624, 104, 3, 3) beside them, and phenotype and local-change coefficients select from those.
A reimplementation that skins `template_vertices` directly will not reproduce this number,
and the error will look like a skinning bug rather than a missing stage.

That stage is also ordinary arithmetic: a coefficient vector against a (624, N, 3) stack is a
matmul, so it folds into the same operator set as the skinning below. The operations are
Gather, MatMul, Mul and ReduceSum, all four of which already compiled in the backbone.

`vertex_bone_weights` is (13718, 9), nine influences per vertex. An earlier cost estimate
assumed four and is low by roughly 2x: the mesh forward is about 1.5 MMAC, not 0.7.

## Withdrawn: the rig was not wrong, and the numbers still differ

This section previously read "Corrected: this was built against the wrong rig", and said the
torch reimplementation above targets the wrong one. That is withdrawn.

**The rest mesh is the definition, and it is ANNY. The skeleton converts.** So a
reimplementation written against ANNY is written against the thing that defines the body, and
the SOMA figures below are a second skeleton over the same mesh rather than a different
subject. `anny_from_soma` in `AlternativeTopology` is that conversion, named in the package.

What stands is narrower and still worth having: the numbers differ, so anything that indexes
by joint or by vertex has to say which skeleton it means.

`lbfgs_polish.py` constructs with `rig="soma", topology="soma"`, and
`sinew-solve/core/soma_rig.h` bakes that skeleton as SoA C arrays:

    SOMA_V 18056    SOMA_J 78    SOMA_F 36108    SOMA_K 10

78 joints and 10 influences against ANNY's 104 and 9. `soma_parents[78]` in the same header is
the forward-kinematics tree. `topology_id` is a foreign key in RFD 107a's schema for this
reason, and the reason survives the withdrawal above: a `vertex_id` or a joint index means
nothing without the skeleton it was taken under.

`sinew-solve` describes itself as the body solve, FK plus linear blend skinning of the ANNY
body, as Lean to Slang kernels, with `core/gen/lbs.spv` compiled and a CPU reference in
`core/spec/tests/lbs_cpu`. `humanoid-rom/HumanoidRom/core/KusudamaEncoding.lean` holds the
joint-limit encoding. Both were already written. Neither is ONNX, so what they supply is the
specification, the baked arrays and a reference to validate against, rather than a graph.

## The clamp is a concatenation of pairwise kusudamas

RFD 107e's decision clamps every unrolled step to the Kusudama cone. How that clamp is
BUILT was settled in a meeting, and it is not the obvious reading of the phrase.

**No kusudama carries two or more cones. Constraints are pairwise, and concatenated.** A
joint limit that a multi-cone kusudama was being asked to express is built instead as a
concatenation of pairwise ones, and nothing in the pipeline constructs a kusudama of two or
more rotation cones.

Note the rule is stricter than the measurement below requires. The degeneracy was measured at
three equidistant cones; the rule cuts at two. That margin is deliberate rather than an
overstatement of the evidence: two cones already admit the opposed case, whose centre sum is
degenerate for the same reason, and a threshold nobody has to reason about at the call site is
worth more than the one cone it gives up.

The measurement behind that choice is already in `humanoid-rom/FINDINGS.md`:

    3 equidistant cones, 120 degrees apart    |sum| = 4.003e-16   degenerate

`KusudamaSolver` derived the pole of its gnomonic projection by summing every cone centre and
normalising. Three equidistant cones sum to zero, `normalize` of zero is undefined, and one
unit in the last place moves the derived pole by 45 degrees. The flip is a degenerate centroid
and not a race. `KusudamaEncoding.lean` separately retires the pole derivation in favour of
projecting against the nearest cone, which is a fix to the solver; the decision recorded here
is upstream of it, and removes the many-cone case from the pipeline rather than repairing it.

The consequence for an unrolled clamp is favourable. A pairwise kusudama is a fixed, small
computation, and a concatenation of them is a fixed-length chain of the same, so the whole
constraint stays feed-forward with no data-dependent count. Comparisons and selects are `Min`
and `Where`, which the backbone already compiled. A many-cone kusudama would have needed a
normalise whose input can be zero, and an INT8 pipeline has no good answer for that division.

Recorded because the unrolled clamp is a new consumer of this decision, and building a single
multi-cone kusudama is what reads most naturally from "clamp to the Kusudama cone".

## What is not measured

Utilisation, which every throughput number above assumes. Whether the unrolled fit reaches an
acceptable residual as a percentage of stature at the precision the part offers, which is the
number the whole approach rests on. Rig calibration, which nothing in the workspace solves.
The cost of two compiled graphs and a per-frame context switch on one device.
