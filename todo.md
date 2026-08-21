https://github.com/weftspun/request-for-discussion/blob/main/0016-deep-learning-model-inventory/DETAILS.md

Now with what you know please create one repo for each model.

Rerank models by priority.

Make logbook records here and split if too big.

## Status: done

10 standalone repos created and pushed under `weftspun/interactor-*` — one per model, per the
explicit override (not RFD 0036's one-repo-many-folders convention). 4 of the 15 catalog entries
are `State: abandoned` per RFD 0064's pivot (no repo made); 1 (`misamaru_seethrough`) was already
covered by existing `interactor-seethrough-ggml`/`-torch` repos.

Full priority ranking, per-repo rationale, the two license corrections found in the org's own RFDs
(P3-SAM, SkinTokens), and the list of remaining `NotImplementedError` gaps: see
[`logbook-rfd0016-model-repos.md`](./logbook-rfd0016-model-repos.md) (split out — this file was
getting long).

Repos, in priority order: `interactor-trellis2-image-to-textured-mesh`,
`interactor-pixal3d-image-to-textured-mesh`, `interactor-qwen-image-edit`,
`interactor-skintokens-auto-rig`, `interactor-trellis2-image-mesh-painting`,
`interactor-voxhammer-text-mesh-editing`, `interactor-voxhammer-image-mesh-editing`,
`interactor-kimodo-text-to-motion`, `interactor-krea2-turbo-text-to-image`,
`interactor-p3sam-mesh-segmentation`.

## Queued (not started): taskweft/nif batcher + fan-in operator

User request (queued while mid-task on qwen-image-edit pose run): write a batcher and a fan-in
operator using taskweft/nif. Start this next, once currently on an item on the PERT critical path.

## Queued (not started): SkinTokens numeric bone names -> LabRCSF mapping

interactor-skintokens-auto-rig's `_write_joint_map()` (RFD 0046's "joint order
trap") assumes named joints, but SkinTokens likely emits plain numeric bone
indices (not semantic names) -- need a correspondence table (probably
SkinTokens' training joint order, e.g. a SMPL-style fixed index convention)
to translate numeric bone IDs into names before they can go through LabRCSF's
joints.csv mapping at all. Check SkinTokens' own output spec/training config
for what its numeric indices actually correspond to before writing this.

## Queued (not started): systemic FBX-finger-chain-to-ANNY retarget fix

This session's posemaniacs-pose-to-ANNY retarget worked for the body but had to rest-pose the
fingers (see anny-pose-retarget-work/LOGBOOK.md) -- a one-off workaround, not a general fix. Any
future character-avatar retargeting that needs real finger articulation will hit the same chained-
joint convention problem and needs a systemic solution before then, not another one-off patch.

## Queued (not started): default to multiview mesh generation for pixal3d/trellis2

interactor-pixal3d-image-to-textured-mesh and interactor-trellis2-image-to-textured-mesh should
default to multiview mesh generation (multiple input view images), not single-view, for better
reconstruction quality. Not yet implemented in either repo's server.py.

## Queued (not started): broken-region touch-up via image/mesh edit

For cases where a pose retarget (or similar pipeline) locally breaks part of a character (e.g.
fingers in the ANNY retarget work), the fallback isn't to perfect the retarget -- it's to identify
the broken region and fix it via a targeted image-edit (qwen-image-edit) or mesh-edit
(interactor-voxhammer-\*) pass with a text prompt describing the correct state. Not implemented as
a general pattern anywhere yet; the ANNY finger issue was just worked around by resting the hands,
not fixed via this route.

## Logbook 2026-08-14 (late): pixal3d multiview loop

- `interactor-pixal3d-image-to-textured-mesh` v0.3.0 pushed: `/predict` (latent state + nvdiffrast
  views + cameras) / `/extract` (the one GLB+USD decode) — upstream app.py's own flow vendored as
  `worker_entry.py`; Dockerfile rebuilt on py3.10 + upstream's prebuilt-wheel env (no compiles).
  Worker stage NOT yet GPU-verified (one real round trip is the remaining gate, ~$0.25 session).
- `synth_views.py` (Qwen-2511 + fal multiple-angles LoRA + Lightning): camera control verified
  working (front/quarter/side views correct, ~9s/view on 4090) — but images noise-corrupted;
  root cause narrowed to bnb-4bit on torch 2.4.1 (see memory bnb-4bit-qwen-corruption).
- Anny-One dataset: BLOCKLISTED (custom non-commercial license, verified by reading
  AnnyOne_LICENSE.txt; the "free to use" claim in circulation is wrong). Ground-truth multiview
  comes from rendering our own ANNY instead. TODO: add to MODEL_LICENSES.md blocklist.
- All pods torn down, verified `[]`. Session GPU spend ≈ $5.
- Queued: D1/D2 GPU verify of pixal3d worker; VoxHammer wiring (inversion mechanics now fully
  understood from upstream edit_pipeline.py — see plan file hashed-sprouting-mist.md).

## Logbook 2026-08-14 (later): COCO->GEM-X dataflow + full teardown

- RunPod verified completely empty: 0 pods, 0 serverless endpoints, 0 network volumes. $0/hr.
  (Pod 3 was created for the pixal3d worker verify but torn down unused on pivot.)
- New repo `weftspun/dataflow-coco-gemx` (pushed): COCO person-image license filter -- COCO
  images keep their original Flickr licenses; only 523/5000 val2017 person images are
  commercial+derivatives-safe (CC-BY/CC-BY-SA/no-known-copyright/US-Gov; all NC and ND dropped,
  SA identifiable). Output in ETNF zstd parquet (licenses/images/person_observations, no NULLs).
  `run_gemx_batch.sh` prepares the whole GEM-X run for ONE unattended pod session.
- Still queued (GPU-gated): pixal3d worker verify (D1/D2), GEM-X batch pilot, VoxHammer wiring.

## Logbook 2026-08-14: deployment skeleton format (LabRCSF joints.csv analysis)

**CORRECTED — the first version of this entry measured the wrong thing. Kept visible because
the error is instructive.**

**Question**: what intermediate format do we deploy with, given Godot humanoid is the runtime
target? **Source**: meshula/LabRCSF `joints.csv` — 94 canonical joints x 16 skeletal formats.

### What I measured first (WRONG)

Bone-NAME coverage: "how many of ANNY's 61 body+hand joint names have a counterpart in each
format's column". Answer came out 52/61 for Godot, VRM, and OpenUSD alike, dropping the same 9
(`spine03`, `spine04`, 8 metacarpals) — from which I concluded Godot costs nothing.

**Why that metric is wrong**: it counts names in a correspondence table. What actually has to
survive is the deformed **silhouette** — the mesh after skinning + blendshapes — because that
is what the differentiable renderer compares, what the 3D VAE encodes, and what a user sees.
Characteristics in our architecture ARE blendshapes (identity baked at build time, small set of
instanced bodies + instanced accessories), so "does a bone name exist" is not even a proxy for
"does the body still look right".

### What matters instead: twist bones

Twist/roll bones distribute limb rotation along the segment so the mesh does not candy-wrap.
Drop them and a forearm rotation collapses the silhouette even though every "named" joint
mapped perfectly. Re-checking `joints.csv` against ANNY's real 104-bone list, **12 ANNY body
bones have NO row in the canonical table at all** — they are not "dropped by Godot", they are
absent from the pivot entirely:

- all 8 twist bones: `upperarm02.L/R`, `lowerarm02.L/R`, `upperleg02.L/R`, `lowerleg02.L/R`
- `shoulder01.L/R` (scapula — drives shoulder-girdle silhouette on arm raise)
- `pelvis.L/R`

The only twist-related rows in the entire table are `LeftEyeTwist` / `RightEyeTwist`, and both
are empty for every format. So the earlier "52/61 survive, identical across pivots" figure was
both the wrong metric AND undercounted by 12.

### Standing conclusion (format), now with an honest justification status

- internal/archival: **OpenUSD** (RFD 0053) — sublayer semantics the pose/rig/edit stack
  already uses; can carry arbitrary extra joints as metadata
- deploy: **Godot GeneralSkeleton via glTF/VRM** — still the likely answer, but the
  justification "it costs nothing" is NOT established: it rested on the discredited
  name-coverage metric
- the joints no standard carries (the 9 named gaps + these 12 absent ones) ride as **USD
  layer metadata**, per the mechanism RFD 0046 already mandates for the VRM humanoid map

### The measurement that would actually settle it (NOT YET RUN) — reuse the skin matcher

No new algorithm needed: **`anny.AnnyInverter` IS the skin matcher**, and it fits to mesh
VERTICES, not to bones — so it answers the silhouette question natively. Protocol:

1. pose an ANNY mesh with the FULL 104-bone rig (incl. the 8 twist bones) over a sweep that
   stresses twist: forearm pronation/supination, arm raise (scapula), leg internal rotation
2. hand that mesh to AnnyInverter as the target, with the pose search restricted to the
   ~52-bone deployment subset (twist bones locked at rest)
3. **the residual PVE in mm IS the silhouette loss** — the number we actually care about;
   cross-check visually with silhouette IoU from the nvdiffrast renders

Both halves already exist and are proven this session: AnnyInverter reported 2.458 mm / 2.281 mm
(its Adam convergence floor) and the LBFGS polish closed a same-rig fit to 0.00017 mm — so any
residual materially above the ~2 mm floor is real silhouette loss from the missing bones, not
optimizer noise. Needs ANNY installed (CPU is fine); it lived on the torn-down pod.

**License pre-screen composes with this**: everything the matcher ever sees has already passed
the license filter (TexVerse CC-BY/CC0 only, SA and NC/ND dropped; DeepFashion re-export
deleted; Booth/Anny-One/CMU/LAFAN1/Mixamo blocklisted), so blocked assets are screened out
before any fitting runs — the matcher never touches data we cannot ship.

**Caveat that survives the correction**: `joints.csv` proves a NAME exists in a column, never
that rotation conventions transfer. This session's finger-chain failure (twisted fingers from a
name-matched Euler copy) is the direct evidence.

**Follow-up**: (1) run the silhouette measurement above before committing to the deploy rig;
(2) extend `_write_joint_map()` in interactor-skintokens-auto-rig to carry the unmapped joints
as metadata; (3) consider upstreaming twist-bone rows to LabRCSF — their absence is a real gap
in the pivot table, not just our problem.

## Logbook 2026-08-14: twist bones measured, and what SOMA-X already solved

### The measurement (RUN, locally, CPU)

Settled the open question from the previous entry empirically. Method: pose an ANNY mesh with
the FULL 104-bone rig, then re-fit with the 22 undeployable bones LOCKED at rest (8 twist:
`upperarm02/lowerarm02/upperleg02/lowerleg02 .L/.R`; `shoulder01.L/R`; `pelvis.L/R`;
`spine03/04`; 8 metacarpals), LBFGS strong-Wolfe, float64. Residual = representational loss,
not optimizer noise, because the same solver reached 1.7e-4 mm on a same-rig fit.

| sweep                      | PVE mm | max mm |
| -------------------------- | ------ | ------ |
| forearm pronation 90 deg   | 3.456  | 61.286 |
| upper-arm twist 60 deg     | 1.385  | 33.586 |
| arm raise (scapula) 45 deg | 1.287  | 31.599 |
| leg internal rot 30 deg    | 0.701  | 17.202 |
| combined                   | 2.645  | 59.885 |

**Verdict: the loss is real and large.** 61 mm peak error on forearm pronation is exactly the
candy-wrapper collapse twist bones exist to prevent — 6 cm of silhouette on a ~1.7 m body, on
the single most common gameplay motion. The earlier "52/61 joints survive, Godot costs nothing"
claim is now decisively falsified: name-coverage said zero cost, mesh-space says 6 cm.

### What SOMA-X wrote about it (studied)

NVIDIA hit this and solved it _without_ baking blendshapes. From `SOMA-X/docs/data_assets.md`
and `docs/procedural_control_format.md`:

- SOMA's rig is a **122-joint template** exposing a **77/78-joint public rig**. Twist joints are
  **procedural** — computed, never authored per-frame.
- The rule set: "forearm and shin twist come from hand and foot twist, while upper arm and thigh
  twist use reverse start/end compensation." Extraction is swing-twist decomposition
  (`aligned_x_swing_twist` is the shipped default; `local_x_euler` and `local_x_swing_twist`
  also supported).
- It lives in a **declarative JSON sidecar** (`SOMA_procedural_transforms.json`) that is "the
  authoritative runtime source", explicitly designed so "consumers resolve stable joint names to
  indices, validate, compile numeric buffers, and evaluate the same ordered transform **without
  running arbitrary Python**" — i.e. an explicit non-Python consumer plan. Maya and Blender
  reference implementations already exist.
- Turning it off (`enable_procedural_transforms=False`) does exactly what my test did: prunes the
  procedural joints and "aggregates each removed joint's skinning weights to its nearest kept
  parent" — SOMA treats that as the degraded _legacy_ path, which is corroborating evidence that
  the numbers above are the expected cost, not a bug in my setup.
- Ordering note: "body pose correctives are supported **only** with procedural transforms" —
  correctives ride ON TOP of procedural twist, they do not replace it.

### Consequence for the deployment decision

"We can always deploy a blendshape bake, but twist bones are hard" — correct, and the resolution
is that we should not bake twist at all. Revised plan:

1. deploy rig = Godot GeneralSkeleton / VRM humanoid (the ~52 public joints) — unchanged
2. **carry `SOMA_procedural_transforms.json` (or our ANNY-equivalent) as a sidecar and evaluate
   twist procedurally at runtime in Godot** — the format is explicitly designed for exactly this
   kind of non-Python consumer; a Godot `SkeletonModifier3D` is the natural host
3. blendshape correctives only for what remains after procedural twist, per SOMA's own ordering
4. internal/archival stays OpenUSD (SOMA's own template rig is `SOMA_template_rig.usda`, UsdSkel
   — same choice, independently arrived at)

### Follow-ups

- implement the swing-twist evaluator as a Godot SkeletonModifier3D, validated against the
  Python reference (target: reproduce the full-rig mesh to well under the 3.5 mm / 61 mm above)
- re-run this exact measurement with procedural twist ON to quantify what it recovers
- ANNY is now installed locally (CPU) — this test is cheap to repeat; script at
  `$CLAUDE_JOB_DIR/tmp/twist_test.py`, worth moving into a repo

## Logbook 2026-08-14: Godot twist solution + full experimental apparatus

### Scale of the problem, in household terms

The measured deployment loss (twist bones locked, full-rig mesh as target):

| quantity                                        | value       | household scale                                                                                                  |
| ----------------------------------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------- |
| mean per-vertex error, forearm pronation 90 deg | **3.46 mm** | a stack of ~4.5 credit cards (0.76 mm each), or 2 stacked US pennies                                             |
| **peak** per-vertex error, same motion          | **61.3 mm** | **about the width of an adult wrist (55-60 mm)** -- also ~a soda-can diameter (66 mm), or a golf ball and a half |

The peak number is the damning one: the mesh surface is displaced by roughly the entire
thickness of the limb it is supposed to be hugging, on the most ordinary motion there is
(turning a doorknob, holding a mug, aiming). 61.3 mm on a ~1.7 m body is 3.6% of body height.

### CORRECTION: Godot needs NO custom code -- my previous claim was wrong

**Retracted**: the previous version of this entry said "Root cause of Godot's built-in falling
short (MEASURED, not assumed)" and asserted that `ConvertTransformModifier3D` "reads an AXIS
CHANNEL, Euler-style" and therefore gimbals. **That was inference from the API surface
(`get_reference_axis`, `TRANSFORM_MODE_ROTATION`), never verified against the implementation,
and labelling it MEASURED was wrong.** What I actually measured was a numpy comparison of two
algorithms in the abstract; I never measured what Godot does.

**Verified by reading the source** (`godotengine/godot` @ scene/3d):

1. `SkeletonModifier3D::get_roll_angle()` -- the shared helper -- IS a true quaternion
   swing-twist projection:

   ```text
   dot = q.xyz . roll_axis
   roll_component = Quaternion(roll_axis * dot, q.w); normalize
   angle = 2 * acos(clamp(roll_component.w)); signed by direction
   ```

   That is exactly the algorithm I reimplemented. Godot does NOT read an Euler channel here, so
   it does NOT gimbal at large swing.

2. **`BoneTwistDisperser3D` already exists** (Godot 4.7.1,
   `scene/3d/bone_twist_disperser_3d.cpp`) -- a SkeletonModifier3D purpose-built for exactly
   this, and it calls `get_roll_angle`. It is strictly more capable than what I wrote:
   multi-joint dispersal with per-joint `twist_amount`; `DISPERSE_MODE_WEIGHTED` deriving those
   amounts from bone lengths with a `weight_position` bias (= SOMA's segment weights);
   `mutable_bone_axes` for rest- vs pose-space axis (= SOMA's "aligned" variant);
   `twist_from` / `twist_from_rest` reference frames; a damping curve; and it cancels
   accumulated twist in child joints (`prev_rot.inverse() * pose * cur_rot`) -- a chain
   subtlety my single-bone version simply did not handle.

**Consequence**: the custom `SomaTwistModifier3D` addon is DELETED, not kept as a fallback. The
Godot work is configuration, not code. `Desktop/godot-soma-twist/README.md` now holds the
SOMA-rule -> BoneTwistDisperser3D property mapping (forearm<-hand, shin<-foot, upper arm/thigh
via the built-in `joints[end].amount -= 1.0` "remove twist from current pose" step,
`mutable_bone_axes` for aligned extraction, WEIGHTED mode for segment weights).

**What survives from the earlier work**: the two experiments, both still valid, and one of them
now serves a better purpose -- `swingtwist_check.py` validates the algorithm GODOT ITSELF uses
(exact 90.0000 deg twist under 90 deg swing, where an Euler-channel read would give 180.0000).
The 61.3 mm silhouette-loss measurement is unaffected: it measures what LOSING twist bones
costs, which is what justifies configuring the disperser at all.

**Process note**: this is the second time in this session that a name/API-level inference was
wrong and only source-reading settled it (the first was joints.csv name-coverage vs actual
silhouette). Rule going forward: do not write "measured" unless the thing measured is the thing
claimed; read the implementation before asserting a tool's limitation.

### EXPERIMENTAL APPARATUS -- how to recreate both results

Durable copies: `godot-soma-twist/experiments/` (originals lived in an ephemeral job tmp dir).

**Versions**: Godot 4.7.1.stable.official.a13da4feb | ANNY 0.6.0 (pip, CPU) | torch 2.11.0+cu128
| roma, trimesh, warp-lang 1.16.0 | all fitting in float64.

**A. Silhouette-loss measurement** -- `experiments/anny_twist_loss.py`, run
`python anny_twist_loss.py`. Logic:

1. `model = anny.Anny(local_changes="default", facial_actions="all").to(dtype=torch.float64)`
2. undeployable set = every bone matching `upperarm02|lowerarm02|upperleg02|lowerleg02|
shoulder01|pelvis.|spine03|spine04|metacarpal` -> 22 bones; `free_ids` = the rest
3. target: pose the FULL rig with a twist-stressing rotvec (e.g. `lowerarm02.L` = 90 deg
   about local Z for pronation) -> `model(pose_parameters=...)["vertices"]`
4. fit: optimise ONLY `rv_free` (undeployable bones pinned at identity) with
   `torch.optim.LBFGS(lr=1.0, max_iter=250, history_size=50, line_search_fn="strong_wolfe")`,
   loss = MSE over vertices, 3 outer steps
5. report `torch.norm(pred - target, dim=-1) * 1000` -> mean and max in mm
   Control that makes the number trustworthy: the SAME solver reaches 1.7e-4 mm when the twist
   bones are NOT locked, so any residual is representational, not convergence.

**B. Swing-twist correctness** -- `experiments/swingtwist_check.py`, run
`python swingtwist_check.py`. Pure-numpy mirror of the GDScript, asserting: pure twist recovered
exactly (15/45/90/179 deg); pure perpendicular swing leaks ZERO twist; twist survives swing (the
table above); `swing * twist == original` to 1e-9. The GDScript port is
`SomaTwistModifier3D.extract_twist(q, axis)`:

    r = Vector3(q.x, q.y, q.z); proj = axis * r.dot(axis)
    twist = Quaternion(proj.x, proj.y, proj.z, q.w)
    if twist.length_squared() < 1e-12: return IDENTITY   # pure swing: twist undefined
    twist = twist.normalized(); if twist.w < 0: twist = -twist

**C. Godot headless test** -- `test_twist.gd`, run `godot --headless --script test_twist.gd`.
NOT YET GREEN: the run hangs on first-project import in this environment, so the GDScript path
is currently validated only by construction against the passing numpy reference. Getting that
headless run to complete is the next task and a prerequisite before trusting the addon.

### Follow-ups

- unblock the headless Godot run; then re-run the ANNY measurement with procedural twist ON to
  quantify how much of the 61.3 mm the modifier recovers (target: well under the 3.46 mm mean)
- wire the sidecar: parse SOMA's `SOMA_procedural_transforms.json` (or our ANNY equivalent) to
  configure modifier instances, rather than hand-placing them per rig

## Logbook 2026-08-14: identity table built (23k), and why not .b3d / not GNM

**Done**: `anny_render_corpus/` now holds the first three relations of the schema --
`phenotypes` (6 interned names), `identities` (23,000; 22,511 train / 489 val), and
`identity_phenotype` (138,000 long-form rows). Validator: 0 findings (ETNF no-NULLs, FK
integrity, split hygiene). 0 id collisions.

**Source decision -- ANNY's own SimpleShapeDistribution**, after eliminating two candidates:

- **AddBiomechanics `.b3d`: rejected twice over.** (a) Its subjects are biomechanics-lab
  volunteers (Camargo2021, Carter2023, Falisse2017, Fregly2012, Hamner2013) -- young, healthy,
  able-bodied. Sampling 23k identities from that bakes a narrow, inequitable population into the
  whole corpus. (b) Its only reader, nimblephysics, publishes no Windows wheels and its CI
  covers only mac/manylinux/rpi, so reading it here would mean an unsupported from-source build
  of a DART C++ tree. Dropped as an identity source; still fine as motion data (where it is
  separately treadmill-narrow).
- **google/GNM: not applicable yet.** Apache-2.0, Windows CI, genuinely good -- but it ships
  only `gnm/shape` = **GNM Head**, a head/face model. No body model (roadmap only). And SOMA-X
  has no GNM bridge: its supported set is SMPL / SMPL-X / MHR / Anny / GarmentMeasurements.
  Worth revisiting for FACE identity diversity later, which ANNY covers only coarsely.

**The check that mattered was physical, not statistical.** The sampled parameter stats looked
alarming -- height never exceeding 0.67 of its range, weight median 0.915 -- which looked like a
biased sampler. Decoding 300 identities to actual meshes and measuring stature showed the
opposite:

| population                | p05     | p50     | p95                        |
| ------------------------- | ------- | ------- | -------------------------- |
| adults (age > 0.5, n=260) | 1.536 m | 1.709 m | 1.879 m                    |
| all ages                  | 1.161 m | 1.689 m | (min 0.812 m, max 2.008 m) |

That matches the global adult reference (~1.50-1.90 m) and children are genuinely present down
to 0.81 m. The parameter -> stature map is non-linear and age-conditioned, so the parameter
percentiles were meaningless on their own.

**Pattern, third occurrence this session**: an abstract proxy misled and only the concrete
measurement settled it -- (1) joints.csv name-coverage vs actual silhouette, (2) inferring
Godot's twist math from its API surface vs reading the source, (3) phenotype parameter
percentiles vs decoded stature in metres. Standing rule: measure the physical quantity, not the
proxy that is convenient to read.

**Bug caught pre-run**: every sampled identity initially shared `source_subject =
"anny:sampled"`, which would have made the validator's cross-split contamination check fire on
all 23k rows. Each independent draw is now its own subject.

**Next**: poses relation (sample frames from 100STYLE + O3DE + balance-disturbance, carrying
clip/frame provenance and license lineage), then scenes = identity x pose x environment.

## Logbook 2026-08-14: GNM loaded; ANNY facial actions ARE ARKit-52 (exact)

### Headline finding

**ANNY's `facial_actions` is the ARKit 52-blendshape set, name-for-name.**
Measured: 52/52 exact string matches, **zero** ARKit names missing from ANNY, **zero** ANNY
names absent from ARKit. Not "similar", not "mappable" -- identical vocabulary
(browDownLeft ... tongueOut).

Consequence, given ARKit is a FACS-derived set (see melindaozel.com/arkit-to-facs-cheat-sheet):
the expression bridge ANNY <-> ARKit <-> FACS needs **no mapping table and no training** -- it
is a name equality. Any ARKit-driven capture (iPhone ARKit face tracking, any ARKit-compatible
mocap) drives ANNY expressions directly. This is a much better result than the identity/shape
side below, and it was one command to establish.

### GNM loaded and inspected (moved to Desktop)

`Desktop/gnm-anny-headfit/` -- self-contained: `GNM/` clone (173 MB) + `.venv` (py3.13) with
**both** gnm-shape and anny importable in one interpreter.

GNM Head, as loaded: 17,821 vertices; bbox extent [0.255, 0.342, 0.239] = **Y-up**, ~0.34 m,
metres; call signature `(identity, expression, rotations, translation)`; landmark scheme
`HEAD_SPARSE_68` (the standard 300-W/dlib 68); `GNMBodyPart.HEAD` only.

### Composition WITHOUT training an adapter -- status: blocked on correspondence, not on method

The method is right (fit, do not learn) and has two precedents: SOMA-X's own extension
mechanism is correspondence-based ("OBJ pairs used to compute the mesh correspondence to SOMA
topology"), and our LBFGS/AnnyInverter vertex fitting already reaches 1.7e-4 mm on a same-rig
target. What is missing is the _correspondence data_:

- **ANNY ships only COCO-17 BODY keypoints** (`data/keypoints/coco.pth`: nose, eyes, ears,
  shoulders, elbows, wrists, hips...). No facial landmark scheme.
- **GNM ships 68 FACIAL landmarks**. Overlap with COCO-17 is 3 usable points (nose + 2 eye
  centres) -- a poorly conditioned basis for a similarity transform.
- Worse: **`coco.pth`'s regression weights are for a 19,158-vertex topology**, while
  `topology="anny"` is 13,718 and `topology="soma"` is 18,056. The keypoint asset does not
  match either topology we can currently instantiate, so even the 3 points are not yet
  obtainable. (`topology="smplx"` fails on a UnicodeDecodeError under this locale.)

So head/body composition is **not** an adapter-training problem; it is a "author 68 corresponding
vertex indices once" problem, exactly the OBJ-pair recipe SOMA already uses.

### THREE cross-model traps, all verified, all recorded in anny_render_schema.py

1. **Gender inverted.** GNM `Gender(FEMALE=0, MALE=1)` vs ANNY `0=male, 1=female`. Composing
   without `gnm_gender = 1 - anny_gender` gives every character a head of the opposite sex.
2. **Up axis differs.** GNM Y-up, ANNY Z-up. Without `(x,y,z)->(x,-z,y)` the head lies on its
   side.
3. **Assets are topology-bound.** coco.pth (19,158 verts) silently fits no instantiable ANNY
   topology; it failed loudly here only because matrix shapes disagreed.

### EXPERIMENTAL APPARATUS

Environment: `Desktop/gnm-anny-headfit/.venv` (uv, **Python 3.13** -- GNM requires <=3.13, the
system Python is 3.14 and cannot install it), packages `gnm-shape` (editable from the local
clone), `anny` 0.6.0, `trimesh`, `scipy`. GNM v3 HEAD assets ship inside the clone
(`gnm/shape/data/versions/v3_0`), no download.

**A. ARKit-52 equality test** (the headline result), reproduce with:
m = anny.Anny(local_changes="default", facial_actions="all")
set(m.facial_action_labels) == ARKIT_52_SET # -> True, symmetric difference empty
The ARKit-52 name list is inlined in the check; compare both directions, since a one-sided
`issubset` would hide extra ANNY actions.

**B. Head alignment ladder** -- `Desktop/gnm-anny-headfit/headfit.py --rung {0,1,2}`
(rung 0 = 1 head, rung 1 = 4 ethnicities, rung 2 = 16; Gall's law, never batch first).

- `y_up_to_z_up(v)` -> `(x, -z, y)`; `gnm_gender_from_anny()` -> the inversion
- `procrustes()` = closed-form Umeyama similarity (no iteration, no training)
- `anny_head_vertices()` derives the head region as vertices with >0.5 skin weight on the
  `head` bone -- computed, not a hand-authored index list, so it survives an ANNY version bump
- residual = KD-tree nearest-neighbour distance, ANNY head verts -> aligned GNM surface

**RUNG 0 RESULT (bbox-corner alignment, the crude baseline): mean 21.97 mm, p50 21.38,
p95 42.63, max 52.92.** Do NOT read this as shape disagreement -- diagnosis is region mismatch:
ANNY's head-bone region is 4,295 of 13,718 verts with extent [0.172, 0.211, 0.225] while GNM's
head includes neck and full skull at [0.255, 0.239, 0.342]. Different anatomy, so bbox corners
are not corresponding points. This is exactly what rung 0 is for and it cost seconds.

**Left/right determined geometrically, never by name.** In the 3-point attempt the GNM eye
groups (68-scheme indices 36-41 vs 42-47) are ordered against ANNY by comparing x-coordinate
signs, because "left" in a landmark scheme may mean image-left, not subject-left -- the same
class of trap as the gender inversion.

### Next

- author the 68-point ANNY vertex correspondence once (SOMA's OBJ-pair recipe), then re-run the
  ladder; only then is the projection residual meaningful
- resolve which ANNY topology `coco.pth` targets (19,158) -- possibly a topology not exposed by
  the current constructor
- ARKit-52 equality means expression capture can be wired NOW, independent of the shape work

## Logbook 2026-08-14: priority-1 twist fix -- DIAGNOSIS CHANGED

### What we thought the problem was

"Godot/VRM humanoid rigs have no twist bones, so deploy loses forearm twist; configure
BoneTwistDisperser3D with the right ratio and it is fixed." The open question was just "what
ratio?".

### What the measurements actually show

**ANNY's default rig cannot transmit forearm twist at all, at ANY ratio.** Rotating the twist
bone barely moves the forearm skin:

| ratio (twist bone share) | skin twist at x=0.5 | at x=0.8 | at x=0.95 | RMS vs ideal 90x |
| ------------------------ | ------------------- | -------- | --------- | ---------------- |
| 0.00 (locked)            | 0.0 deg             | 0.0      | 2.8       | 51.3             |
| 0.489                    | 2.6                 | 16.1     | 27.7      | 40.4             |
| 0.936                    | 4.4                 | 22.1     | 25.6      | **39.4 (best)**  |
| 1.00 (all on twist bone) | 4.7                 | 22.8     | 24.6      | 39.4             |

Ideal for a 90 deg pronation is `angle(x) = 90x`, i.e. 45 deg at mid-forearm and ~86 at the
wrist. Even giving the twist bone 100% of the rotation yields **22.8 deg where 72 deg is
required**. Root cause found in the skin weights: of 154 forearm-segment vertices (selected
GEOMETRICALLY, by position along the elbow->wrist axis, not by dominant bone -- the first
attempt selected by dominant bone and was rightly suspect), **111 are dominated by
`lowerarm01`, the bone that never twists**, and only 28 by `lowerarm02`.

Two candidate ratios were derived and BOTH are moot given the above: 0.489 from rig geometry
(twist bone sits at 11.10 of 22.71 cm along the forearm) and 0.936 from the twist bone's
skin-influence centroid. They disagree by 0.45, which the sensitivity curve prices at ~70 mm --
but no value in that range produces anatomically correct deformation.

### Where the error actually lands (why this is a mocap blocker)

Locked-twist error by body region, 90 deg pronation, per-vertex:

| region      | verts | mean                        | peak                   |
| ----------- | ----- | --------------------------- | ---------------------- |
| upper arm   | 604   | **0.00 mm**                 | 0.00                   |
| torso       | 1356  | **0.00 mm**                 | 0.00                   |
| forearm     | 482   | 9.16 mm                     | 75.15 mm               |
| wrist/hand  | 128   | 37.14 mm                    | 78.15 mm               |
| **fingers** | 3076  | **38.06 mm (~a golf ball)** | 76.95 mm (~a soda can) |

Whole-mesh mean is only 9.20 mm -- **the mesh average understates the hand error 4x**, because
1356 torso vertices sitting at exactly zero dilute it. For a mocap pipeline the extremity
figure is the metric, not the mesh mean. Reporting mesh-wide statistics would have let this
hide, so the audit needs per-region reporting.

### So "fix priority 1" now means one of these, not "pick a ratio"

1. **Repair the forearm skin weights** in the corpus generator: re-weight the forearm as a ramp
   between lowerarm01 and lowerarm02 so twist distributes linearly. Mechanical, we control it,
   and it fixes the data at the source.
2. **Use the SOMA rig instead** -- SOMA-X advertises "the v0026 nvHuman template with SOMA
   procedural twist joints and updated skin weights", i.e. exactly this problem solved
   upstream. PROBE BLOCKED: `anny.Anny(rig="soma", topology="soma")` loads, but its vertex
   positions and bone rest heads came out in inconsistent frames (median radial distance
   64 cm about a 24.5 cm forearm segment). That is the documented SOMA-is-cm/+Y vs ANNY-is-m/+Z
   trap; resolve the frame before judging the rig.
3. **Constrain the corpus** to poses without heavy pronation until 1 or 2 lands, and document
   the limitation, so we do not train on anatomically wrong forearms.

Deployment-side note: the Godot `BoneTwistDisperser3D` work is still correct and still needed --
a VRChat avatar with properly weighted forearms benefits from it. The point is that our
SYNTHETIC TRAINING DATA is wrong at the source, so fixing only the deployment rig would leave
the model trained on bad forearms.

### Apparatus

- `godot-soma-twist/experiments/twist_recovery.py` -- ratio sweep + sensitivity curve
  (16 mm of error per 0.1 of ratio mismatch; locked = 78 mm at 90 deg, 133 mm at 135 deg)
- the profile and per-region measurements above were run inline against
  `anny.Anny(local_changes="default", facial_actions="all")` in float64; vertex selection is
  geometric (position along the elbow->wrist axis, radial < 6 cm) precisely so that the result
  does not depend on skin-weight assignment, which is the thing under test
- household-scale equivalents via `human_scale()` in `gnm-anny-headfit/headfit.py`

### Caution recorded

The earlier "61.3 mm from locking twist bones" figure came from posing `lowerarm02` directly.
The corrected framing poses the WRIST (what a humanoid channel actually carries) and gives
78 mm. Both say "wrist-to-soda-can", but the second is the mocap-faithful setup.

## Logbook 2026-08-14b: priority-1 twist FIXED -- plus two retractions

### The fix

Forearm twist now transmits. Two changes, both in the corpus generator:

1. **Re-weight the forearm** as a linear elbow->wrist ramp across the twist pair
   (lowerarm01 -> lowerarm02), redistributing only the mass already on those two bones
   so partition of unity holds exactly and nothing outside the forearm moves.
2. **Disperse the wrist roll** onto lowerarm02 (what Godot's BoneTwistDisperser3D does
   at runtime). lowerarm02 is the wrist's parent, so the hand's final orientation is
   unchanged. Delta Mush on top recovers the volume LBS loses.
   DQS is blocklisted for this project and was not used; Delta Mush / Direct Delta Mush
   are the approved route.

Validated across both arms, 45/90/135 deg, and four phenotypes including a child --
the case that matters most, since ANNY is the identity model in the SOMA list that is
specifically noted as well-suited to children, so we cannot escape this by swapping
models.

| case         | forearm mm      | fingers mm      | hand deg (of 90)   |
| ------------ | --------------- | --------------- | ------------------ |
| default      | 18.3 -> **4.5** | 14.7 -> **1.5** | 74.6 -> **88.6**   |
| small female | 13.8 -> **3.4** | 12.2 -> **1.3** | 74.4 -> **88.6**   |
| large male   | 27.8 -> **7.7** | 22.5 -> **1.9** | 74.5 -> **88.6**   |
| child        | 9.7 -> **2.4**  | 6.8 -> **0.6**  | 74.4 -> **88.6**   |
| 135 deg      | 28.8 -> **9.4** | 19.4 -> **1.4** | 121.0 -> **134.2** |

Forearm error ~4x better, fingers ~10x better (a golf ball down to a credit card's
thickness). The residual grows with angle, as expected -- skinning error is
super-linear in rotation.

### RETRACTION 1: the earlier twist numbers measured the wrong rotation

Every previous twist measurement in this project rotated a bone about "local Z" under
`pose_parameterization="local-ref"`, assuming that was the bone's roll axis. It is not.
The local->world rotation map for wrist.L is the IDENTITY, so "local Z" was WORLD Z --
a direction 55 deg away from the forearm. Those runs measured a mixed bend, not a
pronation. **Withdrawn: the ratio sweep, "no ratio works", the 39.4 deg RMS floor, the
22.8-deg-at-ratio-1.0 figure, and the 38.1 mm finger error.** The axis is now recovered
by probing (rotate 10 deg about each local axis, read the world axis the skin turns
about, invert) using DESCENDANT vertices -- a bone's own vertices are LBS-blended with
neighbours, and fitting them put the effective rotation centre 33 mm off the forearm.

What survives from the old analysis: 111 of 154 forearm-segment vertices are dominated
by `lowerarm01`, which never twists. That is a fact about skin weights, independent of
axis, and it is the actual cause -- which is why re-weighting is the fix.

### RETRACTION 2: there is no soma/game_engine "frame hazard"

Earlier today I reported that rig="soma" and "game_engine" return vertices and bone
heads in different coordinate frames (72% / 87% bbox containment), and warned that
keypoint labels exported from them would not match the pixels. **That is wrong.**

`rest_bone_heads` pairs with `rest_vertices` -- and does so at 100% containment for
EVERY rig and EVERY phenotype tested. I had been comparing the REST skeleton against
the IDENTITY-POSE mesh, and an identity `pose_parameters` is not the rest pose.

But the underlying hazard is real and is OURS, not the rigs': mixing rest skeleton with
posed mesh is off by **54.9 mm on the default adult and 500 mm on a child**. It scales
with how far the phenotype sits from default, so it would look fine on the default body
everyone spot-checks and be catastrophic on the small identities. This is exactly the
silent-corruption class the preflight audit exists for, and it is what broke the
small-female and child rows in validation until the geometry was made mesh-derived.

ACTION for the corpus: any joint/keypoint export must take skeleton and mesh from the
same pose, and `preflight_audit.py` needs a check that asserts it at several phenotypes,
not just the default one.

### Rig permutation sweep (all 18 legal combinations)

Answering "if we use SOMA-X can we still use Google's and ANNY's population shape data":
**yes.** `rig`, `topology` and `phenotypes` are independent arguments, and sex dimorphism
reads +13.5 cm (real-world ~13 cm) across essentially every permutation. A skeleton
change does not cost the 23k identities or the GNM face work.

`cmu_mb` was measured for completeness but is EXCLUDED -- CMU mocap provenance is
blocklisted for this project.

The sweep also showed no rig transmits twist on its own, which is why the fix had to be
in the weights. Caveat now understood: the sweep posed from the identity pose, which for
soma sits 1021 mm from its rest pose, so the soma rows specifically should be re-run
from rest before being quoted.

### Next: Unified Pose Correctives

SOMA-X ships "Unified Pose Correctives (Beta)" -- pose-space correctives carried as
blendshapes. That is the principled form of the hand-rolled ramp above, and it matches
the standing instruction to keep blendshapes running all the way through the pipeline.
The ramp is a stopgap; correctives should supersede it.

### Apparatus

- `godot-soma-twist/experiments/rig_permutation_sweep.py` -- all 18 rig x topology combos
- `godot-soma-twist/experiments/twist_fix.py` -- the fix, Delta Mush, screw-interpolated
  ground truth, per-region mm reporting
- `godot-soma-twist/experiments/validate_twist_fix.py` -- angles x sides x phenotypes
- superseded: `twist_recovery.py`, `anny_twist_loss.py`, `swingtwist_check.py` (all used
  the wrong axis; kept for provenance, do not quote their numbers)

## Logbook 2026-08-14c: stage CLOSED -- twist fix is in the pipeline

`anny_rig.py` is now the corpus's single model builder. `preflight_audit`,
`interface_audit` and the future renderer all call `build_corpus_model()`; nothing
constructs a bare `anny.Anny` any more, because doing so is how an audit ends up
certifying a model nothing ships.

Wrist-driven 90 deg pronation, skin roll near the wrist (ideal 78.8 deg):

| arm | raw mocap | shipping     |
| --- | --------- | ------------ |
| L   | 12.9 deg  | **84.4 deg** |
| R   | 13.1 deg  | **85.2 deg** |

Rest pose provably untouched: `max |rest_vertices stock - fixed| = 0.000000 mm`. The
re-weighting only moves mass between two bones that are both at identity at rest, so
this is a property of the fix, not a lucky measurement.

**The gate took three revisions, and that is the transferable lesson.** The first two
passed on a rig _known_ to be broken:

1. dominance-share proxy -- passed outright
2. single distal band, driven from the TWIST BONE -- 66.9 of an ideal 78.8. Wrong edge:
   nothing in the pipeline drives a twist bone, because mocap supplies the wrist channel
3. single distal band, wrist-driven -- still too lenient. With the roll dispersed the
   stock rig reads 67 deg near the wrist while its mid-forearm is flat

Scoring the PROFILE's linearity separates all three cleanly -- stock raw 52.8, stock
dispersed 24.0, shipping 4.4 deg RMSE -- so the gate sits at 15 deg with a negative
control that asserts an unfixed rig fails it. A check that passes on known-broken input
is worse than no check: it certifies the defect.

**State:** preflight 28 checks all pass; suite 10/10 red caught, green clean;
interface_audit 17 interfaces, 12 OK, **0 HAZARD**, 5 UNCHECKED and named.

**Next stage:** poses relation (sample frames with clip/frame provenance and license
lineage), then scenes = identity x pose x environment, then rung 0 of the render ladder
(10 scenes / 350 images, seconds of compute, purely to prove the plumbing).

Still UNCHECKED, carried forward deliberately rather than silently:
ANNY<->SOMA units/axis (no export path yet); GNM<->ANNY gender polarity (gnm not
importable in this env); ANNY->LabRCSF names (12 bones have no canonical name,
hand-authored); renders<->keypoints (no render path yet -- when it exists, joints MUST
come from `bone_heads`+`vertices` or `rest_bone_heads`+`rest_vertices`, never mixed).

## Logbook 2026-08-14d: the audit was measuring the wrong denominator

Prompted by rachelbythebay's ppm post (the dashboard that counted 500s against a
FIXED denominator, so the Sweden datacentre looked healthy at night purely because
traffic was asleep). Two instances of the same error were live in our pipeline.

### 1. The audit could not see what it claimed to certify

A sampled audit catches only defects larger than ~3/n of the population (95%
detection). Our default was `--sample 600`, often run at 300:

| sample            | floor      | identities | images of 800k |
| ----------------- | ---------- | ---------- | -------------- |
| 300               | 10,000 ppm | 230        | 8,000          |
| 600               | 5,000 ppm  | 115        | 4,000          |
| 3,000             | 1,000 ppm  | 23         | 800            |
| **23,000 (full)** | **43 ppm** | **1**      | **35**         |

So a defect touching 23 identities -- 800 images -- slipped through 95% of the time
while the audit printed all-PASS. **Sampling was never a considered trade; it was an
unpriced default.** Full decode costs **95 s**, which is nothing against a gate that
precedes hours of GPU time. The audit now decodes all 23,000, prints its own detection
floor, and FAILS when asked to certify below what its sample can resolve (verified:
`--sample 300` now fails rather than passing quietly).

The deeper point: ppm is a rate over an _unbounded stream_, where you must estimate.
Ours is a _fixed finite population_, where you can **enumerate**. Enumeration beats any
sampled rate, and we were estimating for no reason.

### 2. Quality was a mean over a denominator that does not vary

Whole-mesh mean is our Sweden-at-night: pronating a forearm leaves 1,356 torso vertices
at exactly 0.00 mm, so the mesh mean reads 9.2 mm while fingers are off by ~a golf ball
-- understating the part that matters ~4x. `corpus_defect_rate.py` now reports an
exceedance RATE against a STATED tolerance, over ARM geometry only, against a raw-mocap
baseline (an absolute rate with no reference is not interpretable):

| tolerance | raw mocap   | shipping       | improvement |
| --------- | ----------- | -------------- | ----------- |
| > 5 mm    | 749,830 ppm | 347,415 ppm    | 2x          |
| > 10 mm   | 513,831 ppm | 181,326 ppm    | 3x          |
| > 20 mm   | 260,820 ppm | **44,189 ppm** | **6x**      |

worst single arm vertex 83.0 mm (~1.3 soda cans) -> 44.6 mm (~a golf ball).

**Honest residual: 4.4% of arm vertex-instances still exceed 20 mm**, concentrated at
135 deg pronation and the elbow blend zone. Not a clean win; carried forward.

Two false starts on this measurement, both the same species of error as the one being
studied: the first baseline used stock weights WITH dispersal (flattering, since
dispersal alone recovers much of the gap), and the arm mask swept in the elbow blend
zone that twist should not move anyway.

### Granularity: is ppb reachable?

**ppb is undefined at image scale.** 800,000 images means one image IS 1.25 ppm; there
is no rate between zero and that. Reaching a billion images would cost **2.1-15.7
GPU-years and 188 TB**, and would be pointless for a fixed population. ppb _is_ well
defined per-vertex: 800k x 13,718 = **11.0 billion vertex-instances, so 1 ppb = 11
vertices** -- that is the granularity at which our quality numbers can honestly carry
three more digits.

## Constraint 2026-08-14: no runtime code in glTF

Exports carry **pure data only** -- skin weights, animation sampler channels, morph
targets and their animated weight channels. No runtime modifiers, drivers, constraints,
or custom extensions requiring a runtime to interpret. An export that only looks right
because the consumer runs our code is not portable, and degrades silently to the unfixed
geometry wherever that code is absent.

**This splits the twist fix.** Re-weighted skin weights are data and export cleanly.
`disperse_wrist_roll` is runtime logic and must be **baked at export time**: emit explicit
`lowerarm02` rotation channels next to the wrist channels rather than deferring to Godot's
`BoneTwistDisperser3D`.

| delivery path                 | code-free twist?                                       |
| ----------------------------- | ------------------------------------------------------ |
| baked clip, direct skeleton   | yes -- channels survive                                |
| baked clip, morph-target bake | yes -- survives any skeleton path                      |
| humanoid retarget             | **no** -- profile has no twist slots; channels dropped |
| live / interactive mocap      | **no** -- needs a driver by definition                 |

**Consequence that changes priorities.** The LabRCSF naming gap (12 ANNY bones with no
canonical name: 8 twist + shoulder01.L/R + pelvis.L/R) was logged as a documentation
problem. Under this constraint it becomes a **blocker for the live-avatar path**:
retargeting through a humanoid profile discards baked twist channels and leaves no
runtime to rebuild them, so for live VRChat avatars the twist must come from the skeleton
itself -- which requires those bones to survive retargeting.

No glTF writer exists yet (`extract_poses.py` only reads), so this lands before the
exporter is built rather than as a rewrite.

## Index 2026-08-15: open work is now tracked as issues, not prose

Everything below used to live only as prose in this file. After the local repos were
archived and recycled, prose in a logbook stopped being a tracker, so each open item now
has an issue. This section is the index; the issues are the source of truth.

**weftspun/dataflow-coco-gemx**
| # | title |
|---|---|
| 1 | 100STYLE retarget blocked: 29.6 deg bind-orientation offset before populating poses |
| 2 | interface_audit: 5 interfaces still UNCHECKED |
| 3 | Decide Delta Mush for the render corpus once pose distribution is known |
| 4 | Forearm twist residual: 4.4% of arm vertices still exceed 20 mm at 135 deg |
| 5 | Population sampling: Japan stature bias +6.4 cm and corpus over-dispersion |
| 6 | Dataset provenance: verify 149k Universe images, finish TexVerse pull |
| 7 | Archive format policy: ~12 zip files still on the archive volume, including the 100STYLE pair |

**others**
| repo | # | title |
|---|---|---|
| godot-soma-twist | 1 | LabRCSF naming gap is now a live-avatar blocker |
| interactor-skintokens-auto-rig | 1 | SkinTokens numeric bone indices need a correspondence table |
| interactor-pixal3d-image-to-textured-mesh | 1 | Default to multiview mesh generation |
| interactor-trellis2-image-to-textured-mesh | 1 | Default to multiview mesh generation |
| anny-pose-retarget-work | 1 | Systemic fix for FBX finger-chain retarget |
| logbook | 1 | Broken-region touch-up not implemented as a general pattern |
| logbook | 2 | taskweft/nif batcher + fan-in operator |

**Critical path** is dataflow-coco-gemx #1 -> poses relation -> scenes -> rung 0 of the
render ladder. #3 and #4 both depend on knowing the pose distribution, so they unblock
behind #1. #7 overlaps #1: converting the two 100STYLE zips to ETNF zstd parquet clears the
format violation and produces the poses input in one pass.

## Teardown 2026-08-15

All 22 Desktop repos verified fully pushed -- 0 dirty, 0 unpushed, no upstream-less
branches, 0 stashes -- then recycled. ~17.8 GB reclaimed. 20 under `weftspun`, 2 under
`v-sekai-multiplayer-fabric`.

RunPod confirmed clear (user scan). API key revoked, so the cached 1Password entry is stale.

**Seethrough render outputs: DROPPED, deliberately.** `interactor-seethrough-ggml/out/`
held 343 files (24 PSD, 286 PNG, 1 JPG, plus logs and JSON) that existed only in a
gitignored directory and were never pushed. They were packed to
`seethrough-out-2026-08-15.tar.zst` (853 MB -> 684 MB, 343 files verified) with a `.cff`
sidecar, that archive was then recycled along with everything else, and the decision on
2026-08-15 was to **let it go** rather than restore it. It is gone once the Recycle Bin is
emptied, and that is intended -- not an oversight to be corrected by a future reader.

Consistent with the rest of the policy: the repo is PUBLIC, `seethrough_output*.psd` is
blocklisted from the dataset inventory, and these are secondary-generation outputs, which
never enter training corpora. Nothing downstream depends on them; the code that produced
them is in the repo and pushed.

## Qwen3.8 MTP on turboquant-godot 2026-08-16

**Stage 0 measured, stock upstream, no TurboQuant.** RTX A6000 48GB on RunPod,
`ggml-org/llama.cpp` at `25558268` (the MTP merge, #22673), model
`cygnal/Qwen3.8-27B-heretic-ara-Q4_K_M-MTP-GGUF` (Apache-2.0, sha256
`9d9b864f…`). Paired A/B, `--parallel 1` on both arms so the spec flags are the
only difference, medians of 3 runs x 3 prompts through an unmodified
`qwen38-mtp/probe.py`.

| arm               | overall | P1 code | P2 prose | P3 code | acceptance |
| ----------------- | ------- | ------- | -------- | ------- | ---------- |
| spec off (floor)  | 34.4    | 34.5    | 34.5     | 34.3    | —          |
| draft-mtp n-max 2 | 57.0    | 62.0    | 46.5     | 57.0    | 0.56–0.84  |

+65.7% median. Baseline spread 34.3–34.6 across all nine runs, so the gain is
far outside the noise. Negative control: the MTP arm logs 921 accepted of 1050
drafts; the baseline logs no drafting counters at all, so the gain is
attributable to the flag rather than to an ignored option looking like noise.

**This number does not transfer to the game.** `probe.py` subtracts TTFT and
reports medians, so it measures steady-state decode at 400 tokens. A realtime
policy is judged on TTFT and on p99, and a deadline is missed by the tail. The
published rule is that gains need long generations and that under ~400 tokens
the overhead can dominate — our 400-token result sits exactly on that boundary.
A per-tick action of 1-3 tokens is the regime where MTP is worth least. Recorded
now so the +65.7% is not later quoted for a case it never measured.

**Resolution is RECTGTN.** The policy emits an HTN plan rather than an action,
so generation is long (MTP's good regime) and execution is per-tick and
inference-free, amortising latency across the plan horizon. `replan` is the
recovery path, and because actions carry ISO-8601 durations and plans return a
`temporal` block, deadline detection falls out of the plan instead of a bolted-on
timer. Ladder and two scenarios in `turboquant-project/docs/realtime-rl-ladder.md`.

**Cost.** Pod ran ~35 min at $0.53/hr, about $0.31, then terminated and verified
three ways (pod list empty, direct query null, SSH timed out). Two setup
failures ate part of that: `llama-server` fails to build when the WebUI assets
404, fixed with `-DLLAMA_BUILD_UI=OFF`; and `curl` pulled the 16.8 GB GGUF at
1.4 MB/s where `hf_transfer` did it in ~80 s. `aria2` would not install from
apt on the RunPod pytorch image.

**Pricing, for later reference.** A6000 is $0.33/hr community against $0.53
secure — we paid secure for no reason. The model fits 24 GB (18.9-22.2 GB at
131K with q4_0 KV), so an A5000 at $0.16/hr or a 3090 at $0.22/hr is the right
build rig; on bandwidth-scaled estimates that is roughly $0.78-0.88 per million
output tokens against $2.58 as configured. Serverless is $1.22/hr, so pods win
above ~43% utilisation and serverless below it. OpenRouter is $0.28/M for a
`qwen3-32b`-class base model but cannot serve a finetune at all, so the finetune
premium is ~6x at best and ~20x realistically. For `modules/llm` this is all
moot: inference is in-process on the player's machine, so a finetune costs
nothing to serve.

**Retraction of a line in the 2026-08-15 teardown entry.** That entry states the
RunPod API key was revoked and the cached 1Password entry is stale. As of
2026-08-16 the stored RunPod API credential
authenticates, lists pods, provisions and terminates. Either a new key was
issued into the same item or the note was wrong. The item is live; treat the
earlier line as superseded rather than deleted.

## Queued (not started): the README ladder, and 37 stale names the gate now lists

Parked deliberately. None of this advances a rung of the planner ladder, and the
Gyre earns nothing from it. It is recorded so it is not rediscovered, not so it
is done next.

**What is left.** Four READMEs over the 40-line limit: `1-transport/ingest` (67),
`wallpaper-parsec` (76), `lean/humanoid-rom` (86), `service/godot` (95). Six were
already cut — `authoring/godot-mcp`, `interactor-physics`, `transport-fanout`,
`lean-entity-packet`, `contract-wt`, `transport-gateway` — plus `blender-mcp`,
`service-store` and `service-physics` earlier.

**And 37 stale repository names** across thirteen children, which `check_docs.py`
now enumerates in one run rather than one README at a time. `service/godot` is
the worst: five in its README and three in its `CLAUDE.md`. They resolve on
GitHub redirects, so nothing is broken and nothing is right.

**Why it can wait.** The gate landed in `fabric` on 2026-08-16, so the debt stops
growing on its own: a new document naming a moved repository, using a word RFD
0111 retired, or running past 40 lines fails a build. That was the only part of
this worth doing now. The backlog behind it is cosmetic, and a repository whose
README is 95 lines still builds, still runs, and still pays exactly what a
40-line one pays.

**The one caveat.** Those document checks only see children that are checked out.
CI's bare clone scans zero and says so rather than passing quietly, so the
guarantee holds in a workspace and not in CI. Closing that means a CI job that
syncs the manifest before checking, and that is the only piece here with any
claim on the critical path — because without it the gate is advisory.

## Queued (not started): where the planner ladder actually stands

Rung 0 exists twice and neither is rung 1. `client/turboquant_chat` is the
on-device chat, and `sim/commons.py` is the settlement baseline whose greedy
driver thrashes — three residents walk four hours to a mender who turns in before
they arrive. That failure is the argument for planning with commitment, and it is
already measured.

**Rung A is stale as written.** `docs/planner-ladder.md` says
`godot-goal-task-planner` must build against `turboquant-godot`. That project is
archived as of 2026-08-16 and its Godot tree is `entities-gyre/client`, so the
rung names a build target that no longer exists under that name. The planner
itself is `V-Sekai/godot-goal-task-planner`, a different organisation from
everything else in the ladder, and `modules/goal_task_planner` is not in
`entities-godot/modules` at all — so rung A is not "does the assembly plan hold",
it is "does the module exist here yet", and the answer is no.

**Rung 1 needs no inference work**, which the ladder already says: `LLMChat::cancel()`
is an exit signal checked at every token boundary, so the abort path exists and
rung 1 adds only the deadline that fires it and the fallback it falls back to.
That is the cheapest next rung and the first one that is game mechanics.
