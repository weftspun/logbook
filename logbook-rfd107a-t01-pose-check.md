# Logbook: RFD 107a T01, the pose-library check

T01 is the gate at the head of the critical path: project twenty poses, look at them, and ask
whether a character artist would draw them. It needs no renderer, no GPU and no install. This
entry records the run, three things it got wrong on the way, and what the next pass owes.

## The clips exist, and the count now agrees with data

An earlier entry concluded the clip sources were gone, because `extract_poses.py` names three
datasets and all three return 404 in the organisation, appear in no goal manifest, and leave
nothing on disk. That was a search of git and the org, and the clips are on a Google shared
drive, `0360 - Datasets Allowlist`.

| dataset                              | contents  | licence                   |
| ------------------------------------ | --------- | ------------------------- |
| `dataset-100style-godot-clips`       | 810 glb   | CC-BY-4.0, CITATION.cff   |
| `dataset-100style-mocap`             | 810 bvh   | CC-BY-4.0, Zenodo 8127870 |
| `dataset-o3de-motion-matching-clips` | 24 `.res` | Apache-2.0 OR MIT         |

`mocapClips = 810` in the plan now agrees with a file count rather than with a sentence in the
RFD. That is the first time the quantity has been checked against anything.

`dataset-vr-balance-disturbance` is absent from the drive as well as from git.

Two obligations follow. A Google Drive folder cannot be a manifest `<project>`: `repo` clones
git remotes, and there is nothing to clone, pin or diff. What would satisfy the Sides rule is an
index in git rather than the bytes — drive path, per-dataset counts, licence from each
CITATION.cff, and a hash per file. Separately, `dataset-100style-mocap` carries `base.zip` and
`labelled.zip`, which the archive-format rule forbids; they want recompressing to `.zst` with
payload hashes verified before the originals go.

## What ran

Every fortieth clip of the 810 sorted by name, twenty in all, spanning the styles rather than
clustering on the letter A. `extract_poses.py` at stride 60 returned 2,100 joint-position rows:
twenty clips, five frames, twenty-one bones.

The middle frame of each clip was projected and drawn. All twenty are upright figures mid
stride. The hundred styles vary the gait — Penguin, Monk, Tiptoe, DuckFoot, Depressed — and
never the configuration of the body. Nothing sits, crouches, leans on anything or reaches. RFD
107a predicted exactly this when it said the clips are locomotion, and the sheet turns the
prediction into a picture. How many of the twenty an artist would draw is a human judgement and
is deliberately not recorded here.

## Three corrections, in the order they were found

**The camera was picked by hand, twice.** The first sheet used a front view, which flattened the
thing being judged: mean foot separation is 0.356 m along the travel axis, about five stacked
soda cans, against 0.230 m across it, three and a half. Tiptoe is the clearest case at 0.032 m
across, half a can, versus 0.631 m along. Switching to a side view fixed that dataset and left
the same objection standing for the next one. The workspace already had the answer in
`render_view.py`: `sphere_hammersley_sequence`, the generator TRELLIS.2 and Pixal3D use,
parameterised by an integer so view i of twenty is a yaw and a pitch nobody argued for. The
sequence spans the whole sphere, so view 0 looks straight down, which is correct for
reconstruction and useless for judging a pose; narrowing the pitch band would be a decision to
write down rather than a default to inherit.

**The orthographic basis was degenerate.** Written as `up = right × forward`, every figure
collapsed to a diagonal line. It is `up = forward × right`, checked against the identity case:
forward (0,0,1) with right (1,0,0) must give up (0,1,0).

**The layout was the old one.** The twenty-one bones `extract_poses.py` returns are a
BVH-flavoured skeleton with no fingers, no face and no toes, and drawing them directly produces
the legacy stick figure. RFD 107a is about 104 wholebody points. The twenty-one are evidence,
not the answer: ANNY's makehuman topology carries 104 bones, every one of the twenty-one target
names is among them, so a fit that places the twenty-one leaves the other eighty-three
determined by the rig. Knuckles follow the wrist, toes follow the foot.

## The fit is not done, and the first attempt used the wrong procedure

A first pass solved a rotation vector per bone plus a global translation and uniform scale,
aligning centroids, and reached a mean residual near 50 mm with the worst near 110 mm — most of
a soda can, when a same-rig fit has previously reached 1.7e-4 mm. Centroid alignment is not the
procedure. `lbfgs_polish.py` in `anny-pose-retarget-work` shows the shape of one that is: an
initial solution first, then `torch.optim.LBFGS` with a strong-Wolfe line search, because Adam
alone has a fixed step and under-converges on rotation-composition landscapes. Its initial comes
from AnnyInverter against target vertices, which the next section shows these clips cannot
supply.

So the twenty figures on the desktop are still the twenty-one-point layout.

### Route 2 is deleted by one measurement, and rung 0 has run

`AnnyInverter.__call__` takes `vertices_target`, so the vertex route needs a mesh. The clips do
not have one. `Aeroplane_BR.glb` reports `meshes: 0` with one skin, twenty-four nodes and one
animation: these files are animation curves on a skeleton, and there is no geometry in them to
correspond to ANNY's vertices. That deletes the highest-ceiling route rather than costing it,
and the check was one command.

Rung 0 ran in its place: a closed-form Umeyama similarity alignment of ANNY's rest joints onto
the twenty-one targets as the initial, then LBFGS with a strong-Wolfe line search over per-bone
rotations. Mean residual fell from thirty-three stacked pennies to sixteen. The worst stayed at
about seventy-one pennies, one and a half soda cans, and it stayed there across every clip
tested — 107.3, 107.9 and 108.0 mm on three different poses.

That constancy is the finding. A residual that does not vary with the pose is not the optimiser
failing to converge; it is a fixed disagreement between two skeletons. Per-target residuals name
it precisely:

Per-target residuals name it, in millimetres and in stacked pennies:

| target    | residual | pennies |
| --------- | -------- | ------- |
| `root`    | 107.7 mm | 71      |
| `spine02` | 45.9 mm  | 30      |
| `spine03` | 43.2 mm  | 28      |
| `head`    | 37.6 mm  | 25      |
| `foot.R`  | 5.8 mm   | 4       |

`extract_poses.py` maps the source `Hips` onto ANNY's `root`, and they are different things:
ANNY's `root` rests on the floor, at y = 0.000 m, while the clip puts its target between 0.948
and 1.039 m — about fifteen soda cans up, which is pelvis height on a standing adult. The fit is asked to place a floor bone at hip height and pays
for it in the whole spine above. The feet, which sit where ANNY expects feet, land within four
pennies. `spine05` also rests at y = 0.000 m, so two of the twenty-one targets are pinned to one
place while the clip separates them by a hand's width.

This is T02's territory rather than T01's. The plan already records that the `coco.pth` weight
map was measured with `searchsorted` rather than assumed, at a maximum positional difference of
zero exactly. BONE_MAP has had no such treatment: it is a name-level mapping, which is the
failure `extract_poses.py`'s own docstring warns about — three times in one session a name-level
map looked right and was wrong.

So rungs 1 and 4 stay unjustified for now. Feeding a mis-mapped fit's vertices to the inverter
anchors on the error, and asking EditScore to choose between candidates that share a wrong hip
spends GPU time on a comparison whose outcome is already determined. The next spend is measuring
the correspondence.

### Four routes, and a referee rather than an argument

`AnnyInverter.__call__` takes `vertices_target`, and the clips give twenty-one joint positions
and no mesh in ANNY's topology. `lbfgs_polish.py` works because its targets were already in that
topology from an earlier retarget. Four ways across that gap are available, none obviously best,
so all four get run and scored instead of one being argued for.

1. **Joints to a provisional pose, then vertices.** Solve roughly from the twenty-one, take the
   posed ANNY vertices as `vertices_target`, then inverter plus LBFGS. Cheapest, and circular
   if the provisional solve is poor.
2. **The clips' own skinned mesh.** The glb carry a character mesh whose posed vertices exist,
   in the source topology, so this needs a correspondence to ANNY's. That is the same problem
   T02 records for `coco.pth`, where the map was measured with `searchsorted` rather than
   assumed, at a maximum positional difference of zero exactly.
3. **Inverter for shape, LBFGS for pose.** Run the inverter once on the rest pose to settle
   phenotypes, then LBFGS over pose only against the joint targets, starting from that solution.
   Invents no correspondence and uses what the clips actually provide.
4. **EditScore in the loop.** Generate several fits per pose — different seeds, different
   regularisation weights — decode each from Hammersley viewpoints and keep the one the reward
   model prefers. Best-of-N rather than a single solve, with the referee choosing.

**How they are compared.** Joint residual in millimetres against the twenty-one targets, paired
with a household object, which is the physical quantity. Then EditScore on the decoded views,
which answers a different question: whether the recovered body reads as a body. A fit can put
every constrained joint within a penny's thickness and still fold an elbow the wrong way,
because eighty-three of the 104 are unconstrained, and the residual cannot see that. The spread
of per-view scores is the third number, since a pose that scores well from one Hammersley
viewpoint and badly from the next is inconsistent in 3D.

**And against the image corpus.** `coco_person_commercial_train2017` holds 12,620 licence-clean
photographs of people, the train split rather than the blinded val2017. Scoring renders only
against each other measures agreement inside our own distribution. Sampling real photographs
through the same instrument gives the scale those numbers sit on: if a fitted render scores
below an ordinary photograph of a standing person, the gap is the thing to report, and it is not
visible from renders alone.

## Where OmniGen2, EditScore and VoxHammer belong

Recorded because the pipeline has more checkpoints available than it is using.

EditScore reads two images and an instruction and returns a number, so it can sit at any stage
that produces a frame, not only after a restyle. It runs at 6.75 GiB at 512 pixels square, which
fits the ASUS UGen300's 8 GB, and it refused none of twelve unclothed figure renders.

A SLAT or mesh latent can be decoded to images and scored the same way. Decoding from
Hammersley viewpoints rather than a front and back pair gives per-view scores whose disagreement
measures 3D consistency: one view cannot separate a good edit from an edit that is good only
from that angle. The cameras are already deterministic and reproducible from an index.

VoxHammer edits the latent directly, so a frame EditScore rejects can be corrected in 3D and
re-decoded rather than discarded, and the re-decode is scored by the same instrument.

## Two gates added while doing this

`check_prose_tropes.exs` caps the aphoristic negative definition, calibrated against
public-domain narrative prose at 0.30 per 1000 words rather than against our own p90, which
would have licensed the habit. `check_household_units.exs` catches a length reported without a
household equivalent.

The second one earned its place immediately. It found `$1M` of revenue being read as one metre,
and an occlusion tolerance of thirteen pennies split at its decimal point into a bare fragment
that then read as unpaired. Both were its own bugs and both are now controls.
Then it found an error that had been sitting in `keypoint_render.py` since it was written: the
occlusion tolerance was annotated "20 mm, about thirteen stacked credit cards". A credit card is
0.76 mm, so thirteen make 10 mm and twenty need twenty-six of them; thirteen pennies make
19.8 mm. The anchor was out by a factor of two, in the direction that made the tolerance sound
tighter than it is.
