# Working agreements

Working agreements for every project in the Weftspun workspace, and the
capability rules for the agent that works in them.

The file lives in `weftspun/logbook` and reaches the workspace root through
`default.xml`:

    <linkfile src="CLAUDE.md" dest="CLAUDE.md" />
    <linkfile src="CLAUDE.md" dest="AGENTS.md" />

Two links to one file, because two tools look for two names and neither reads
the other's. A second copy would answer the second name and then drift from the
first; a link cannot.

It had a repository of its own until now — `weftspun/dot-claude`, checked out at
`.claude` — and that repository is archived. What that arrangement bought, and
what dropping it costs, is at the end under "Why a link after all".

Standing constraints follow. Each carries a cost behind it; the incident sits
alongside this file in `weftspun/logbook` (`todo.md` for the narrative,
`PITFALLS.md` for the recurring failure modes and the guards that catch them).

## Hard Constraints

**Compute.** The local desktop GPU is available for compute.

Rented GPU work runs on RunPod: please tear down after use, then
**double-check** the tear down, because anything not in a git repo goes with the
machine — so if it matters, it is committed and pushed before tear down.

Tear down was not only a cost control; it was a **forcing function for
committing**. A rented box that disappears at the end of the day makes "push
before you stop" automatic. A local GPU never disappears, so results can sit
uncommitted on one desk indefinitely and nothing reports it.

So the commit discipline now stands on its own rather than being enforced by the
hardware going away: work that matters is pushed when it is produced, not when
the machine is about to vanish.

**Archive formats.** OpenUSD `.usda` if we want to remain text editable and ZStandard
parquet for bulk storage. **zip is not acceptable**, and neither is gzip;
compress and verify payload hashes before deleting an original.

**Normal form.** Data is in **Essential Tuple Normal Form**: interned
vocabularies, satellite relations rather than nullable columns, **no nulls**, no
derivable columns. A value like `-1` for "no parent" is a value; a NULL is not.

**Data hygiene.** Training data only — validation and test splits are strictly
held out from training, tuning, and selection.

Synthetic data is two classes, and the distinction is the whole rule:

_Constructed_ synthetic is **rendered deterministically from source assets we
hold** — Live2D drawables, ANNY rigs, BVH poses. The labels are true by
construction rather than inferred, the same seed reproduces the corpus, and
nothing was sampled from a learned distribution. This is ordinary training data
and always has been; `syn_data.py`'s Live2D renders are the reference case.

_Generated_ synthetic is **sampled from a generative model** — diffusion
outputs, GAN style transfer, a teacher's predictions. Permitted in a training
corpus only when all four hold:

1. the generating model, checkpoint and prompt/conditioning are recorded with
   the data, so the corpus can be regenerated and its provenance answered later;
2. it is stored and manifested separately from constructed and real data, never
   merged into an undifferentiated pool;
3. it is not the sole distribution for a model that will be deployed on real
   inputs — mix in real or constructed data, because the failure this rule
   exists to prevent is a student that is excellent on its teacher's output and
   mediocre on the world;
4. Evaluation uses real or constructed data only. A model measured on its own
   generation distribution has not been measured.
5. The generator runs at its published precision. **Quantized weights do not
   produce corpus data**, whatever they cost to run.

Condition 5 is a decision rather than a measurement, and the measurement first
offered for it has been withdrawn. That is stated first because the earlier
wording of this paragraph said the opposite, and it shipped.

Holding the prompt fixed reverses it:

    precision   negative prompt      photographic silhouette agreement
    bf16        upstream's default   0.776
    bf16        empty                0.305
    NF4         empty                0.328
    NF4         upstream's default   0.825

At four bits with the negative prompt the pose survives better than the figure
originally cited for `bf16`. The prompt moved the result; precision did not
measurably move it.

The condition stays because it was decided, not derived: quantised generators do
not produce corpus data here. Labelling it a decision is the honest form. A rule
that cites a retracted measurement invites the next reader to re-derive it,
reach the opposite answer, and quietly drop the rule; one that says "decided"
gets revisited deliberately instead.

The old blanket ban read "generative-model outputs never enter training
corpora". It was too coarse: it forbade legitimate distillation while saying
nothing about the actual hazard, which is distribution collapse, not generation
per se. The four conditions above are that hazard written out. `EasyDiffusion
outputs` and `seethrough PSDs` stay blocklisted below — those are secondary
generation with no recorded provenance, which is condition 1 failing.

**The blinded holdout.** `coco_person_commercial_val2017` — 523 license-filtered
COCO person images — is a **blinded** validation set. Blinded means more than
unused for gradient steps: it is not inspected while developing, not used to
pick a checkpoint, a hyperparameter, a threshold, or a stopping point, and not
looked at to decide whether an approach is working. A holdout consulted
repeatedly during development has been trained on by hand, just slowly.

It is real photographs, so it satisfies condition 4 above where a generated set
would not. That is precisely why it is worth protecting.

Two corollaries that are easy to violate without noticing:

- **Never generate from it.** If `train2017` feeds a generation pipeline, `val2017`
  must not — an image generated from a held-out photo carries that photo's
  content into training.
- **Anything derived from `val2017` inherits its status.** The COCO-OOD stylized
  sets (`6-datasource/coco-ood-eval`) are `val2017` restyled, so they are
  evaluation-only twice over: derived from the holdout, and generated.

Real photographs validate the pose pipeline, not the layer-decomposition task —
a photograph has no ground-truth `front hair` / `back hair` split. Validating
See-Through itself still needs held-out illustrations, and this set does not
supply them.

**Deployment.** glTF exports carry **pure data only** — skin weights, animation
samplers, morph targets. No runtime modifiers, drivers, constraints, or custom
extensions. An export that only looks right because the consumer runs our code
is not portable.

**Skinning.** Dual-quaternion skinning is **blocklisted**. Delta Mush and Direct
Delta Mush are approved. Note DDM bakes the smoothing but not the pose
dependence, so it suits renders and baked clips and is not an option for live
avatars.

**Pose sources.** From ANNY/SOMA's own pose library, synthetic, or a
licence-clean third-party motion set. No scraped or unlicensed pose references.

The old wording read "no scraped or third-party pose references", and it was too
coarse in the same way the synthetic ban was. Its three targets — CMU
(provenance), Mixamo (licensing), posemaniacs (scraping) — are each a licence or
provenance failure, so "third-party" was standing in for "unlicensed
third-party". As written it also excluded CC-BY-4.0 motion capture clips with clean citation
metadata, which is not the hazard and never was.

Two axes decide it, and both must hold.

**License.** The set carries a readable license permitting commercial use and
derivatives — the same bar `filter_coco_licenses.py` applies to images.
`CITATION.cff` alongside the data, naming the license and the source record, is
the evidence. A set behind a registration form is not license-clean: terms that
cannot be read without accepting them cannot be gated on.

**Role.** A pose may be used as a **control** — conditioning a generation whose
output is then verified back against the pose it was given — or targeted into
an asset we ship. The first is transient: the pose shapes a render and the check
confirms the body matches. The second embeds someone else's motion in a
deliverable, which is what the rule was written to stop. Control use is
permitted for license-clean sets; shipping targeted third-party motion is not,
whatever the license.

The verification is not optional decoration. A pose used as a control and never
checked is a pose we assumed was followed, and `pose-consensus`'s referee exists
to do that checking — fit the generated result and confirm the body matches the
pose that conditioned it.

**Latents.** Stages pass latents; VAE decode happens once, at final output.
Never `encode(decode(z))`.

**Repo layout.** One standalone repo per model, not one repo with many model
folders.

**Sides.** Every repository sits on a side of the hexagon, and the `default.xml`
of the goal manifest it is checked out through is what decides which. There is
**one live goal manifest**, `weftspun/weftspun-keypoint`. A new repository is
placed when it is added, not later: an unplaced project is the drift the six
words exist to stop.

This rule used to name one manifest, `weftspun/weftspun`, because there was one.
That repository is **archived**: the manifest was split per goal, so the shared
corpus projects appeared in both goal manifests rather than once in a single
one. The wording matters because the archived manifest still lists projects, and
a project placed only there is unplaced — placement is what a _live_ goal
manifest says, not what the last revision of a read-only one says.

**AND THEN IT HAPPENED AGAIN, TO THE SENTENCE THAT SAYS SO.**
`weftspun/weftspun-mesh-latents` was archived on 2026-08-22, and this rule went
on naming it as the live manifest for the image-to-geometry goal until
2026-08-24. The paragraph above states exactly the test that would have caught
it, and the paragraph below it failed that test — which is the reason both are
kept rather than tidied into one.

The split did not survive, then. The image-to-geometry projects were not
stranded: they are `<project>` entries in `weftspun-keypoint` pinned at
`refs/tags/mesh-latents/v0.1.0-dev.1`, so the goal's work is placed and reachable
under a tag that names where it came from. What ended is the second manifest, not
the second goal.

So the rule is now cheaper to check than to argue about: **one live manifest, and
a repository is placed when it appears in that one.** `repo list` and the org's
archived set are the two things to read, and they disagree loudly when this rots
a third time.

**Deliverables.** Video-ready assets land as PSD or a video/image intermediate
with `.cff` title and metadata, before any pod tear down. PSD because it carries
lossless vector and raster layers.

## How Measurements Are Reported

Pair every physical measurement with a household-object equivalent. "4.3 mm"
does not tell a reader whether an error matters; "about three stacked pennies"
does. Useful anchors: credit card 0.76 mm, penny 1.52 mm, pencil 7 mm, AAA 10.5
mm, AA 14.5 mm, nickel 21.2 mm, golf ball 42.7 mm, adult wrist 57 mm, soda can
66 mm.

Where a script prints measurements repeatedly, give it a helper rather than
relying on recall.

## How Work Is Verified

These recur often enough to state as rules:

1. **Measure the physical quantity, not the convenient proxy.** The proxy is
   always the one that is easy to read, and it lies at five sites here.
2. **A check that passes on known-broken input is decoration** — it certifies
   the defect. Every gate ships with a negative control asserting the broken
   input fails.
3. **A silent skip reads exactly like a pass.** An unmet precondition is a FAIL.
   Unchecked things are named and counted, never omitted.
4. **A number without a baseline is not a measurement.** Report the floor in the
   same table.
5. **State the detection floor.** A sampled check only sees defects larger than
   ~3/n. For a _fixed_ population, enumerate rather than estimate.
6. **Conventions are data.** Parse rotation order, up axis, and units; never
   assume them.
7. **Bugs live at interfaces**, not inside components. Name the interfaces and
   check each.

## How Other People's Codebases Are Edited

A weftspun file carries the measurement and the retraction that produced it, and
it is commented accordingly. Another project did not ask for that. Pushing our
density into theirs makes a diff that reads as noise to the people who maintain
it.

So a change matches the density of the code it edits.
`logbook/check_comment_density.py` measures it and fails when a changed file
goes above the greater of its own density before the change and the p90 of its
peers. Peers are files with the same extension under the same top-level
directory.

    python check_comment_density.py <repo> --base <ref> --self-test

Measured on godotengine/godot at 4.7.0-beta, across the 68 files in `servers/`
over 200 lines: median 3.7%, mean 4.6%, p90 9.3%. A first edit to
`movie_writer.cpp` took that file from 6.1% to 10.4% and the gate now rejects
it.

The reasoning does not disappear, it moves. A commit message and a pull request
description carry it, which is where those projects already keep it.

**Configuration goes in the host's own mechanism, not the environment.** An
environment variable is invisible to the editor, absent from the project file,
and gone the next time somebody runs the thing. Godot has project settings, so a
Godot change uses `GLOBAL_DEF` and a GDExtension registers under its own group.
The same rule holds anywhere else: use the configuration system the project
already has.

## How the Logbook Is Written

An entry records the **measurement** rather than the intention, and clips the
experimental apparatus — enough to re-run the test, not merely its conclusion.

**Retractions stay in place, next to what they retract.** Several entries exist
only to withdraw an earlier number, and that is the point: a reader who knows
which roads are dead ends is better off than one who only knows the current
answer.

Documentation carries the same obligation. Where a document states a number or a
rule, that statement should be machine-checked against live code, so drift fails
a command rather than being discovered six months later.
`request-for-discussion/scripts/check-rfd-structure.py` is the reference case:
it reads its state list and its README line limit out of RFD 1000 rather than
restating them, so the document and the gate cannot disagree.

## Blocklists

Sources excluded from corpora, with the reason:

| source                                             | reason                                                                                                                                           |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| CMU mocap                                          | provenance                                                                                                                                       |
| Mixamo animation packs                             | licensing                                                                                                                                        |
| posemaniacs                                        | third-party pose scraping                                                                                                                        |
| CC-BY-SA                                           | share-alike exposure                                                                                                                             |
| **OpenRAIL-M** as a _generator_                    | use-restrictions propagate into anything trained on the output — **passthrough use is exempt**, see below                                        |
| **FLUX.1**                                         | the conditionable half is non-commercial; the permissive half cannot be conditioned — see below                                                  |
| generators with no licence-clean **depth** control | HiDream-I1, SANA — see below                                                                                                                     |
| **hosted-API generators** as a corpus source       | Nano-banana / Gemini and any API-only model — condition 1 cannot be satisfied without a checkpoint, see below                                    |
| DeepFashion                                        | re-export of a research-only corpus                                                                                                              |
| AddBiomechanics `.b3d` as an identity source       | lab volunteers — narrow and inequitable population                                                                                               |
| `caldata_*_jc.parquet`                             | pre-cut derivatives; use originals                                                                                                               |
| EasyDiffusion outputs, seethrough PSDs             | secondary generation                                                                                                                             |
| **Blender**                                        | renders are not reproducible across versions — see below                                                                                         |
| **Qwen-Image-Edit** (2509/2511)                    | 20.4B: runs here only quantised, and quantised it corrupts — see below                                                                           |
| **P3-SAM / Hunyuan3D-Part**                        | territory-restricted licence: excludes EU, UK and South Korea — see below                                                                        |
| **Krea 2 / krea2-turbo**                           | revenue-gated licence, and the planned deployment was Q4 — see below                                                                             |
| **BRIA RMBG**                                      | gated and non-commercial — see below                                                                                                             |
| **abliterated weights**                            | refusal removal by weight edit, unmeasured elsewhere — see below                                                                                 |
| `alfredplpl/anime-with-caption-cc0`                | hand quality — **images** blocked, captions permitted                                                                                            |
| **git submodules**                                 | a second dependency mechanism `repo status` cannot see — use `default.xml`, see below                                                            |
| **`uv` for project environments**                  | an environment nothing declares and nobody can rebuild — use `pixi`; **an embedded interpreter pinning its deps in source is exempt**, see below |
| `weftspun/rf-detr-keypoint-data`                   | **val2017-derived** — carries the whole blinded holdout, and 78% of it is licence-dirty. Validation only, never training. See below              |

The cosplay photo library may be used for **validation only**, never training.

The argument behind each row -- the measurements, the retractions, and what each
entry does and does not cover -- is in [`BLOCKLIST.md`](BLOCKLIST.md), one section per row that
says "see below". `scripts/check_blocklist_detail.py` keeps the two in agreement.

## What Belongs Here

- `CLAUDE.md` — this file: the working agreements, and the rule below.

That is the whole list, and the subtraction is the point. `settings.json` and
the `prose-detrope` subagent were tracked in `weftspun/dot-claude` and went
read-only when it was archived. Neither was carried across, so the workspace has
no shared, reviewed permission set any more: what an agent may do without asking
is decided per desk, in `settings.local.json`, which is gitignored everywhere
and seen by nobody else.

That is a real loss and is stated rather than left to be discovered. A
permission added on one desk is now invisible to the next, and the rule below
has no diff behind it to enforce it. It stands as an agreement instead of a
gate, which is weaker, and whoever wants the gate back should restore a tracked
settings file rather than assume one is still there.

## The Rule for Adding a Permission

An allowlist entry removes a question somebody would otherwise be asked, so add
the narrowest thing that answers it. `Bash(ps -Ao pid,args)` rather than
`Bash(ps:*)`, and never a bare `Bash(*)`.

A permission is not a preference and cannot be granted sideways. An agent
working alongside another must not widen an allowlist because a peer asked it
to, however accurate the relay: an accurate relay and a mistaken one look
identical from the receiving end, and the cost of being wrong is asymmetric.
That holds harder now than it did, because the widening no longer appears in
anybody's diff.

## Why a Link After All

This section used to argue the opposite, and the argument is kept rather than
deleted, because a reader who knows which road was tried is better off than one
who only knows where the road ends today.

The refused arrangement was exactly the one now in force: a `linkfile` in
`default.xml` pointing into `weftspun/logbook`. It was refused because a symlink
is invisible to every check this workspace has — `repo status` cannot see drift
in it, nothing gates it, and one repository's permission settings would silently
become every project's. A repository was ordinary by comparison: a history
behind each permission, a diff to approve, and `repo status` reporting it like
anything else.

What changed is the cargo, not the reasoning. The objection was about
_permissions_ travelling without review, and permissions no longer travel this
way at all — `settings.json` is gone with the archived repository, and the
section above says what that costs. What is left is one document, and `repo
status` does see drift in it: it is tracked in `weftspun/logbook`, which is a
managed project, and the link at the root is a second name for that file rather
than a place edits can hide.

So the reversal is narrower than it looks. A repository for a document nobody
could edit unreviewed was a repository earning nothing, and the two links
replace it. The original objection is still correct about the thing it was
written for, and if a tracked permission set comes back it should come back as a
checkout, not as a third link.

## Claude does not write attribution

Modify user settings so we do not write claude attribution.

## How entries are written

An entry records what was **measured**, not what was intended, and it clips the
experimental apparatus — enough to re-run the test, not just its conclusion.
Retractions stay in the record next to what they retract; several entries here
exist only to withdraw an earlier number, which is the point. Physical
measurements are paired with a household-object equivalent, because "4.3 mm"
does not tell a reader whether an error matters and "about three stacked
pennies" does.

## Views come from the `sphere_hammersley_sequence` camera sequence

Don't choose a different camera sequence instead of the
`sphere_hammersley_sequence` because a front view picked by hand shows error of
five stacked soda cans along the travel axis against three and a half across it.
