# Working agreements

Working agreements for every project in the weftspun workspace, and the capability rules for
the agent that works in them.

The file lives in `weftspun/logbook` and reaches the workspace root through `default.xml`:

    <linkfile src="CLAUDE.md" dest="CLAUDE.md" />
    <linkfile src="CLAUDE.md" dest="AGENTS.md" />

Two links to one file, because two tools look for two names and neither reads the other's. A
second copy would answer the second name and then drift from the first; a link cannot.

It had a repository of its own until now — `weftspun/dot-claude`, checked out at `.claude` —
and that repository is archived. What that arrangement bought, and what dropping it costs, is
at the end under "Why a link after all".

Standing constraints follow. Each carries a cost behind it; the incident sits alongside this
file in `weftspun/logbook` (`todo.md` for the narrative, `PITFALLS.md` for the recurring
failure modes and the guards that catch them).

## Hard constraints

**Compute.** The local desktop GPU is available for compute. Rented GPU work runs on RunPod:
tear down after use, then **double-check** the teardown, because anything not in a git repo
goes with the machine — so if it matters, it is committed and pushed before teardown.

The rule used to read "never on the local desktop GPU", and lifting it costs one thing worth
naming. Teardown was not only a cost control; it was a **forcing function for committing**. A
rented box that disappears at the end of the day makes "push before you stop" automatic. A
local 4090 never disappears, so results can sit uncommitted on one desk indefinitely and
nothing reports it.

So the commit discipline now stands on its own rather than being enforced by the hardware
going away: work that matters is pushed when it is produced, not when the machine is about to
vanish.

**Archive formats.** zstd, in parquet or standalone. **zip is not acceptable**, and neither
is gzip; recompress to `.zst` and verify payload hashes before deleting an original.
Tabular data is parquet + zstd.

**Normal form.** Parquet is in **Essential Tuple Normal Form**: interned vocabularies,
satellite relations rather than nullable columns, **no NULLs**, no derivable columns. A
value like `-1` for "no parent" is a value; a NULL is not.

**Data hygiene.** Training data only — validation and test splits are strictly held out from
training, tuning, and selection.

Synthetic data is two classes, and the distinction is the whole rule:

_Constructed_ synthetic is **rendered deterministically from source assets we hold** — Live2D
drawables, ANNY rigs, BVH poses. The labels are true by construction rather than inferred, the
same seed reproduces the corpus, and nothing was sampled from a learned distribution. This is
ordinary training data and always has been; `syn_data.py`'s Live2D renders are the reference
case.

_Generated_ synthetic is **sampled from a generative model** — diffusion outputs, GAN style
transfer, a teacher's predictions. Permitted in a training corpus only when all four hold:

1. the generating model, checkpoint and prompt/conditioning are recorded with the data, so the
   corpus can be regenerated and its provenance answered later;
2. it is stored and manifested separately from constructed and real data, never merged into an
   undifferentiated pool;
3. it is not the sole distribution for a model that will be deployed on real inputs — mix in
   real or constructed data, because the failure this rule exists to prevent is a student that
   is excellent on its teacher's output and mediocre on the world;
4. evaluation uses real or constructed data only. A model measured on its own generation
   distribution has not been measured.

The old blanket ban read "generative-model outputs never enter training corpora". It was too
coarse: it forbade legitimate distillation while saying nothing about the actual hazard, which
is distribution collapse, not generation per se. The four conditions above are that hazard
written out. `EasyDiffusion outputs` and `seethrough PSDs` stay blocklisted below — those are
secondary generation with no recorded provenance, which is condition 1 failing.

**The blinded holdout.** `coco_person_commercial_val2017` — 523
license-filtered COCO person images — is a **blinded** validation set. Blinded means more than
unused for gradient steps: it is not inspected while developing, not used to pick a checkpoint,
a hyperparameter, a threshold, or a stopping point, and not looked at to decide whether an
approach is working. A holdout consulted repeatedly during development has been trained on by
hand, just slowly.

It is real photographs, so it satisfies condition 4 above where a generated set would not. That
is precisely why it is worth protecting.

Two corollaries that are easy to violate without noticing:

- **Never generate from it.** If train2017 feeds a generation pipeline, val2017 must not — an
  image generated from a held-out photo carries that photo's content into training.
- **Anything derived from val2017 inherits its status.** The COCO-OOD stylized sets
  (`6-datasource/coco-ood-eval`) are val2017 restyled, so they are evaluation-only twice over:
  derived from the holdout, and generated.

Real photographs validate the pose pipeline, not the layer-decomposition task — a photograph
has no ground-truth `front hair` / `back hair` split. Validating See-Through itself still needs
held-out illustrations, and this set does not supply them.

**Deployment.** glTF exports carry **pure data only** — skin weights, animation samplers,
morph targets. No runtime modifiers, drivers, constraints, or custom extensions. An export
that only looks right because the consumer runs our code is not portable.

**Skinning.** Dual-quaternion skinning is **blocklisted**. Delta Mush and Direct Delta Mush
are approved. Note DDM bakes the smoothing but not the pose dependence, so it suits renders
and baked clips and is not an option for live avatars.

**Pose sources.** From ANNY/SOMA's own pose library, synthetic, or a licence-clean third-party
motion set. No scraped or unlicensed pose references.

The old wording read "no scraped or third-party pose references", and it was too coarse in the
same way the synthetic ban was. Its three targets — CMU (provenance), Mixamo (licensing),
posemaniacs (scraping) — are each a licence or provenance failure, so "third-party" was
standing in for "unlicensed third-party". As written it also excluded CC-BY-4.0 mocap with
clean citation metadata, which is not the hazard and never was.

Two axes decide it, and both must hold.

**Licence.** The set carries a readable licence permitting commercial use and derivatives —
the same bar `filter_coco_licenses.py` applies to images. `CITATION.cff` alongside the data,
naming the licence and the source record, is the evidence. A set behind a registration form is
not licence-clean: terms that cannot be read without accepting them cannot be gated on.

**Role.** A pose may be used as a **control** — conditioning a generation whose output is then
verified back against the pose it was given — or retargeted into an asset we ship. The first
is transient: the pose shapes a render and the check confirms the body matches. The second
embeds someone else's motion in a deliverable, which is what the rule was written to stop.
Control use is permitted for licence-clean sets; shipping retargeted third-party motion is not,
whatever the licence.

The verification is not optional decoration. A pose used as a control and never checked is a
pose we assumed was followed, and `pose-consensus`'s referee exists to do that checking —
fit the generated result and confirm the body matches the pose that conditioned it.

**Latents.** Stages pass latents; VAE decode happens once, at final output. Never
`encode(decode(z))`.

**Repo layout.** One standalone repo per model, not one repo with many model folders.

**Sides.** Every repository sits on a side of the hexagon, and the `default.xml` of the goal
manifest it is checked out through is what decides which — `weftspun/weftspun-mesh-latents`
for the image-to-geometry goal, `weftspun/weftspun-keypoint` for the keypoint goal. A new
repository is placed when it is added, not later: an unplaced project is the drift the six
words exist to stop.

This rule used to name one manifest, `weftspun/weftspun`, because there was one. That
repository is **archived**: the manifest was split per goal, so the shared corpus projects now
appear in both goal manifests rather than once in a single one. The wording matters because
the archived manifest still lists projects, and a project placed only there is unplaced —
placement is what a _live_ goal manifest says, not what the last revision of a read-only one
says.

**Deliverables.** Video-ready assets land as PSD or a video/image intermediate with `.cff`
title and metadata, before any pod teardown. PSD because it carries lossless vector and
raster layers.

## How measurements are reported

Pair every physical measurement with a household-object equivalent. "4.3 mm" does not tell a
reader whether an error matters; "about three stacked pennies" does. Useful anchors: credit
card 0.76 mm, penny 1.52 mm, pencil 7 mm, AAA 10.5 mm, AA 14.5 mm, nickel 21.2 mm, golf ball
42.7 mm, adult wrist 57 mm, soda can 66 mm.

Where a script prints measurements repeatedly, give it a helper rather than relying on
recall.

## How work is verified

These recur often enough to state as rules:

1. **Measure the physical quantity, not the convenient proxy.** The proxy is always the one
   that is easy to read, and it lies at five sites here.
2. **A check that passes on known-broken input is decoration** — it certifies the defect.
   Every gate ships with a negative control asserting the broken input fails.
3. **A silent skip reads exactly like a pass.** An unmet precondition is a FAIL. Unchecked
   things are named and counted, never omitted.
4. **A number without a baseline is not a measurement.** Report the floor in the same table.
5. **State the detection floor.** A sampled check only sees defects larger than ~3/n. For a
   _fixed_ population, enumerate rather than estimate.
6. **Conventions are data.** Parse rotation order, up axis, and units; never assume them.
7. **Bugs live at interfaces**, not inside components. Name the interfaces and check each.

## How other people's codebases are edited

A weftspun file carries the measurement and the retraction that produced it, and it is
commented accordingly. Another project did not ask for that. Pushing our density into theirs
makes a diff that reads as noise to the people who maintain it.

So a change matches the density of the code it edits. `logbook/check_comment_density.py`
measures it and fails when a changed file goes above the greater of its own density before
the change and the p90 of its peers. Peers are files with the same extension under the same
top-level directory.

    python check_comment_density.py <repo> --base <ref> --self-test

Measured on godotengine/godot at 4.7.0-beta, across the 68 files in `servers/` over 200
lines: median 3.7%, mean 4.6%, p90 9.3%. A first edit to `movie_writer.cpp` took that file
from 6.1% to 10.4% and the gate now rejects it.

The reasoning does not disappear, it moves. A commit message and a pull request description
carry it, which is where those projects already keep it.

**Configuration goes in the host's own mechanism, not the environment.** An environment
variable is invisible to the editor, absent from the project file, and gone the next time
somebody runs the thing. Godot has project settings, so a Godot change uses
`GLOBAL_DEF` and a GDExtension registers under its own group. The same rule holds anywhere
else: use the configuration system the project already has.

## How the logbook is written

An entry records the **measurement** rather than the intention, and clips the experimental
apparatus — enough to re-run the test, not merely its conclusion.

**Retractions stay in place, next to what they retract.** Several entries exist only to
withdraw an earlier number, and that is the point: a reader who knows which roads are dead
ends is better off than one who only knows the current answer.

Documentation carries the same obligation. Where a document states a number or a rule,
that statement should be machine-checked against live code, so drift fails a command rather
than being discovered six months later. `request-for-discussion/scripts/check-rfd-structure.py`
is the reference case: it reads its state list and its README line limit out of RFD 1000
rather than restating them, so the document and the gate cannot disagree.

## Blocklists

Sources excluded from corpora, with the reason:

| source                                             | reason                                                                                                                              |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| CMU mocap                                          | provenance                                                                                                                          |
| Mixamo animation packs                             | licensing                                                                                                                           |
| posemaniacs                                        | third-party pose scraping                                                                                                           |
| CC-BY-SA                                           | share-alike exposure                                                                                                                |
| **OpenRAIL-M** as a _generator_                    | use-restrictions propagate into anything trained on the output — **passthrough use is exempt**, see below                           |
| **FLUX.1**                                         | the conditionable half is non-commercial; the permissive half cannot be conditioned — see below                                     |
| generators with no licence-clean **depth** control | HiDream-I1, SANA — see below                                                                                                        |
| **hosted-API generators** as a corpus source       | Nano-banana / Gemini and any API-only model — condition 1 cannot be satisfied without a checkpoint, see below                       |
| DeepFashion                                        | re-export of a research-only corpus                                                                                                 |
| AddBiomechanics `.b3d` as an identity source       | lab volunteers — narrow and inequitable population                                                                                  |
| `caldata_*_jc.parquet`                             | pre-cut derivatives; use originals                                                                                                  |
| EasyDiffusion outputs, seethrough PSDs             | secondary generation                                                                                                                |
| **Blender**                                        | renders are not reproducible across versions — see below                                                                            |
| **Qwen-Image-Edit** (2509/2511)                    | 20.4B: runs here only quantised, and quantised it corrupts — see below                                                              |
| **P3-SAM / Hunyuan3D-Part**                        | territory-restricted licence: excludes EU, UK and South Korea — see below                                                           |
| **Krea 2 / krea2-turbo**                           | revenue-gated licence, and the planned deployment was Q4 — see below                                                                |
| **BRIA RMBG**                                      | gated and non-commercial — see below                                                                                                |
| `alfredplpl/anime-with-caption-cc0`                | hand quality — **images** blocked, captions permitted                                                                               |
| **git submodules**                                 | a second dependency mechanism `repo status` cannot see — use `default.xml`, see below                                               |
| **`uv` for project environments**                  | an environment nothing declares and nobody can rebuild — use `pixi`, see below                                                      |
| `weftspun/rf-detr-keypoint-data`                   | **val2017-derived** — carries the whole blinded holdout, and 78% of it is licence-dirty. Validation only, never training. See below |

The cosplay photo library may be used for **validation only**, never
training.

### `rf-detr-keypoint-data` is the holdout, not a training set

It is **validation only, never training**, for two independent reasons. Either one is enough.

**It contains the entire blinded holdout.** The repository takes every val2017 image with a
non-crowd keypointed person, 2,346 of 5,000, and splits them 2,112 train and 234 test. The 523
images of `coco_person_commercial_val2017` are all inside it:

    holdout images in its TRAIN split   481
    holdout images in its TEST split     42
    total                               523 of 523

Training on it trains on the holdout. The blinded rule is not only about gradient steps, and a
split labelled `train-*.parquet` is the most direct way there is to take one.

**And 78% of it is licence-dirty.** Only 523 of val2017's 5,000 person images are commercial
and derivatives safe, which is what `filter_coco_licenses.py` measures. This set has 2,346, so
1,823 carry the NC, ND and share-alike terms that filter exists to drop. Its README states
`CC BY 4.0` for the whole set, and that claim is wrong.

The two faults compound rather than overlap. The licence-clean images are exactly the holdout,
so there is no subset that is both trainable and clean. A keypoint training set has to be
built rather than filtered out of this one, which is what the renderer in RFD 0122 is for.

`rf-detr-detection-data` and `rf-detr-segmentation-data` are unaffected. Both come from a
Roboflow clothing set rather than COCO, and neither contains a holdout image.

### `uv` is blocklisted for project environments, and `pixi` is why

The objection is the same one submodules get, one layer down. A `uv pip install` leaves an
environment that no file declares, no lockfile pins, and nobody else can rebuild. `repo status`
cannot see it, a diff cannot show it, and the next desk gets a different set of versions with
no report.

The failure is not hypothetical and is recorded next door. Standing up the Hailo compiler on a
Mac took more than twenty packages, discovered one `ModuleNotFoundError` at a time, installed
ad hoc. Every one of them was a real dependency of a real tool, and after the session none of
it existed anywhere: not in a manifest, not in a lock, not in the logbook. The work was
repeatable only by repeating the guessing.

`pixi` answers exactly that. `pixi.toml` declares the environment, `pixi.lock` pins it, both
are tracked, and a second environment for a second job is a `[feature]` rather than a second
undeclared venv. `tropes-removal-model` now carries a `gate` environment with
`no-default-feature` for precisely this: the gate's dependencies were being hand-listed in two
CI `pip install` lines that could drift from the manifest without anybody noticing.

Two limits worth stating rather than discovering.

**This is about PROJECT environments, not about the binary.** `uvx` or `uv run` to invoke a
one-shot tool that touches nothing is not what this blocks. What it blocks is an environment
that work depends on and no file describes.

**A tool that ships its own resolver keeps it.** This rule does not ask anybody to rewrite a
dependency stack that already declares itself elsewhere, and it does not reach into third-party
projects, where the density rule above already says to match what is there.

### Git submodules are blocklisted, and `default.xml` is why

A submodule pins a dependency in a file only `git` reads. `repo status` does not see it, the
manifest does not carry it, and a bumped submodule appears in a diff as a bare hash with no
name, no branch and no reason attached.

That is the same invisibility the **Sides** rule exists to stop. An unplaced project is drift,
and a submodule is an unplaced project that also claims to be placed.

So a third-party dependency is a `<project>` in the goal manifest's `default.xml`, on a side,
with a pinned `revision`. The entry answers "what version, and from where" in fields a tool
reads: a name, a path, a remote and a revision. A `.gitmodules` line answers the same two
questions with a bare hash and no name attached, which is the whole of the difference.

**Corrected: the "why" is not in the manifest, and the earlier wording said it was.** This
paragraph used to read that the manifest answers "what version, from where, and why, because
a comment can sit beside the entry". Comments in a manifest are now blocklisted and
`check_manifest_comments.py` in `weftspun/weftspun-keypoint` enforces it, so that clause
describes an arrangement that no longer exists.

The reason is that a comment beside a `<project>` is the one thing in an otherwise checkable
file that nothing can check. Paths resolve, revisions fetch, linkfiles are followed — and the
paragraph above an entry goes on describing the path or revision it had when somebody wrote
it, with no diff, no CI run and no `repo` command reporting that the two have parted. That is
the same second-place-a-fact-lives failure this section is itself written against, one layer
down.

So the "why" moves to the commit message and the pull request description, which is where the
rule on editing other people's codebases already sends it, and to an RFD when it is durable.
Both are reviewed when written and neither claims to describe a current state, so neither can
go stale in place.

Two consequences worth stating rather than discovering:

- **Fork before you pin.** A `revision` on somebody else's repository is a promise they have
  not made. `godot-cpp` is forked to `weftspun/godot-cpp` for exactly this, and pinned at the
  commit `godot-whisper` ships, so a nine-platform build is a question about our code rather
  than about the binding library.
- **A vendored copy is not a submodule and is not blocked.** Copying source into `thirdparty/`
  with its licence and a recorded upstream hash is visible in every diff, which is the property
  submodules lack. Prefer a manifest entry, vendor when the dependency is small and stable, and
  do not reach for a submodule in either case.

### Blender is blocklisted, and reproducibility is why

A render is a measurement, and a measurement that cannot be re-run identically is not one.
Blender's headless output moves with the version and with the build flags it was compiled
against, so the same scene rendered on two desks is two corpora with one name. Nothing
reports the difference: the images look right in both places.

**No exceptions.** Not for a depth pass, not for a one-off bake, not for a person opening
the GUI to check something by eye. A carve-out for manual use is how the dependency comes
back, because the manual result is what somebody then wants to keep.

The version installed here when this was written was **5.2.0 LTS**, build date 2026-07-14,
from a package manager, pinned by nothing. That is the whole argument in one line: no file
in this workspace records it, `repo status` cannot see it, and the next desk has whatever
its own package manager last offered.

**What this costs, stated rather than discovered.** Two things depended on it and both are
now open questions rather than solved problems.

`render_image.py` in `6-datasource/dataflow-coco-gemx` runs as
`blender -b --python render_image.py`, and it writes the depth pass. Depth is the
conditioning signal for the generation path, not a by-product, so this is a hole in the
pipeline and not a tidying-up. The file stays in the tree as the record of what the pass has
to produce; it is not the way to produce it any more.

RFD 107a's PBR bake said to do the bake in Blender because MPFB2 is a Blender addon and the
material was authored there. That method is gone with this entry. The bake still has to
happen -- albedo, roughness and normal over the hm08 UV layout, metallic a constant zero --
and it now needs a renderer that a `pixi.toml` can pin.

The replacement is not named here, because naming one without measuring it is how the last
unpinnable dependency arrived. What a candidate has to show: it installs from a lockfile, it
renders the same bytes twice on two machines, and the check for that ships with it.

### BRIA RMBG is blocklisted, and we already own the alternative

`briaai/RMBG-2.0` removes an image background, and Pixal3D's `preprocess_image` reaches for
it whenever an input has no alpha channel. It fails two bars at once.

**It is gated.** Hugging Face answers `401 ... Access to model briaai/RMBG-2.0 is restricted`
until somebody accepts terms in a browser. A licence that cannot be read without accepting it
cannot be gated on, which is the same objection that keeps DWPose out: terms nobody has read
travel into whatever the model touches.

**And it is non-commercial.** RMBG is offered for non-commercial use with a separate paid
agreement for anything else, which is the class `filter_coco_licenses.py` exists to drop.

**What replaces it, and the answer is different for the two cases.**

For anything this workspace renders, no matting model is needed at all. The silhouette of a
render is not a thing to infer from pixels: it is which rays hit the body, which the depth AOV
already reports exactly. `render_view.py` writes RGBA with that alpha, and
`preprocess_image` uses an existing alpha channel directly rather than calling any model. The
matte is then ground truth rather than a prediction, which is strictly better than what the
blocked model would have produced.

For images we did not render, See-Through is the in-house route. It is passthrough by
construction, it already separates a picture into labelled layers, and RFD 1079 covers what it
does and does not model. Reaching for a gated third-party matter when the workspace maintains
a segmentation model of its own is the drift this table exists to stop.

The distinction worth keeping: the render case removes the dependency, and the photograph case
replaces it. Only the second is a substitution, and only the second needs measuring against
what it replaced.

### Qwen-Image-Edit corrupts at the only precision this desk can run it

Apache-2.0 in base and weights alike, and that is not the problem. It is 20.43B parameters,
57.7 GB on disk, needing roughly 38 GB at bf16 against a 24 GB card. So it runs here at NF4 or
not at all, and generated-synthetic condition 5 says quantised weights do not produce corpus
data. That alone closes it as a corpus generator on this hardware.

What makes it a blocklist entry rather than a hardware note is that the quantised path is also
measurably broken. At NF4 it peaks at 11.9 GiB and returns images speckled across every pixel —
camera-correct and noise-corrupted, the figure roughly in place under a layer of grain. The
silhouette scores run 0.098 to 0.719 against a control of 0.222, so some frames are barely
distinguishable from a body that moved 20 px.

Three explanations were eliminated rather than assumed, and each cost a run:

- **Not the torch version.** `interactor-pixal3d` recorded the same corruption with torch 2.4.1
  the one constant, and asked for a retest at 2.6 or newer. On torch 2.11.0+cu128, diffusers
  0.40.0 and bitsandbytes 0.50.1 it is unchanged, so that hypothesis is retired rather than
  carried forward.
- **Not the guidance.** The first run passed `true_cfg_scale=4.0` with no negative prompt, which
  diffusers silently ignores. Re-run with guidance actually on: same corruption, twice the time.
- **Not the input.** OmniGen2 edits the identical grey matte render cleanly, so the frame is not
  out of distribution in a way that would break any editor.

8-bit would have isolated the quantiser and is not available here: int8 puts about 20 GB of
weights on a 24 GB card, and the run reached step 3 of 30 at 4,925 s/it with 42 GB resident in
host RAM — 37 hours projected for one image, against 3.3 s/it at NF4.

**Not blocked for hardware that can hold it.** A card with 48 GB or more runs the published
bf16 path, which nothing here has tested and nothing here impugns. The entry says something
narrower: on this desk the only runnable mode is the one condition 5 forbids, and it is broken
as well as forbidden.

OmniGen2 is the replacement and needs no exception — 7.8B, Apache-2.0, 17.3 GiB at bf16, clean
output on the same input.

### P3-SAM's licence excludes territories, which is a different failure

`Tencent-Hunyuan/Hunyuan3D-Part` ships under Tencent's own Community License Agreement, and it
carves out the EU, the UK and South Korea. RFD 0041 records the model as MIT; that is wrong, and
`logbook-rfd0016-model-repos.md` already corrected it by reading the real LICENSE file.

The other entries here block on what the output may be used for. This one blocks on **who may
run the tool at all**, which is a worse property for a workspace whose collaborators and
customers are not enumerated in advance. A restriction on the output can at least be traced
through a corpus; a restriction on the operator means the same command is permitted at one desk
and forbidden at another, and nothing in a manifest or a build log would show the difference.

Passthrough does not rescue it either, and it is worth saying why, because the OpenRAIL entry
does rescue passthrough uses. That exemption turns on the restriction travelling with a single
artefact to whoever supplied it. A territory exclusion does not travel with the artefact — it
sits on the person invoking the model — so the distinction the OpenRAIL rule is built on has
nothing to bite.

### Krea 2 is revenue-gated, and that propagates

The Krea 2 Community License permits commercial use free only below \$1M company-wide annual
revenue and fewer than 50 seats; above either line it needs a separate enterprise agreement.
That is a use restriction, and this workspace already has a rule about those: OpenRAIL-M is
blocked as a _generator_ because restrictions travel into whatever trains on the output, where
no licence check can see them afterwards. Krea 2 is a text-to-image generator, so its outputs
are corpus data, so the same reasoning applies unchanged.

The revenue threshold makes it worse rather than better, and the reason is worth stating.
Whether the licence is satisfied depends on _who deploys the trained model_, which is not a fact
about our corpus and not one we can settle in advance. A term that clears today for a small
deployer and fails for their customer is a term that cannot be gated on at corpus-build time.
`logbook-rfd0016-model-repos.md` already flagged this as "clears the bar for a small deployer,
not for every possible customer" — this entry is that flag resolved rather than carried.

**The second reason is newer and independent.** RFD 0016's plan for it was the Q4_K_M GGUF set:
33.8 GB bf16 down to 9.30 GB quantised, because that is what fits. Generated-synthetic condition
5 now says quantised weights do not produce corpus data, so the deployment shape that made the
model affordable is the one that disqualifies its output. Even with the licence resolved, the
plan on file would not have produced usable corpus.

Neither reason depends on the other. A permissive re-licence would leave the Q4 problem, and a
48 GB card running bf16 would leave the revenue gate.

### A corpus generator must be a checkpoint we hold

Any API-only model is excluded as a _corpus source_, and the reason is structural rather than
contractual, so it survives whatever the terms happen to say this year.

**Condition 1 cannot be satisfied.** The generated-synthetic rule requires the generating
model and checkpoint recorded with the data so the corpus can be regenerated and its
provenance answered later. A hosted model has no checkpoint to pin: the weights change on the
vendor's schedule and the endpoint is eventually retired, so "generated by X" stops resolving
to the thing that generated it. That is the same failure `EasyDiffusion outputs` is blocklisted
for, arriving through a different door.

Two further reasons apply to Nano-banana / Gemini specifically, and both would be sufficient
on their own:

- The [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms) state that users
  "may not use the services to develop models that compete with the services", nor "reverse
  engineer, extract, or replicate any component of the services, including underlying data or
  models". Building a training corpus _is_ using the service to develop a model; whether the
  result competes is a judgement we are not positioned to make, which is the same propagation
  problem OpenRAIL poses, now with a counterparty able to enforce it.
- On the unpaid tier and AI Studio, Google uses submitted content **and generated responses**
  to improve its products, and human reviewers may read them. Our renders, prompts and
  captions would go with it.

Worth recording how SDPose-OOD actually used it, because the paper is the reason the question
came up: Nano-banana produced the colour-sketch variant of COCO-OOD — an **evaluation** set,
not training data — and the sets under test were deliberately made with CycleGAN and StyTR²
"to avoid introducing priors from large-scale pretrained diffusion models". Their own caution
is the argument against reaching further than they did.

Nothing is lost by the exclusion. CycleGAN fills the stylisation role and clears all three
bars: BSD, offline, and pinnable.

### A generator needs licence-clean depth conditioning, not just a licence

The permissive licence is the easy half and it is not the deciding one. Every corpus use here
renders an ANNY pose and requires the generated image to keep that geometry, so a generator
that cannot take a **depth** control cannot do the job however clean its terms are.

Stating it as a rule rather than a list, because the list keeps growing and each entry arrives
looking attractive:

- **HiDream-I1** is **MIT** — the most permissive licence of any candidate reviewed — and its
  only conditioning is `ControlNetLoRA/hidream-i1`: a single LoRA, not a ControlNet family,
  under `license:other`, with 14 downloads and no likes. That fails the same way the FLUX
  ControlNets do, on unreadable terms rather than on absence.
- **SANA** is Apache-2.0 throughout and its ControlNet _architecture_ supports depth —
  `SanaControlNetModel` is in diffusers. **No depth checkpoint is published**: the released
  weights are HED only. Edge conditioning from a render carries silhouette and internal
  contours with no depth ordering, so it cannot say which limb is in front, and for a body
  limb overlap is the hard part. This is the one candidate whose gap is _work rather than
  terms_ — the licence is clean end to end, so a depth ControlNet could be trained. Costed as
  a training job, not adopted as-is.
- **FLUX.1** fails a third way, below.

Three clear at the time of writing, all Apache-2.0 in base _and_ control:

- **Qwen-Image** — a union plus a dedicated depth model, from several independent maintainers.
- **Z-Image-Turbo** — union, `alibaba-pai`.
  **Kolors is not blocklisted, and its position is precise.** It is the only from-scratch,
  Apache-2.0, SDXL-architecture model with its own ControlNets — trained by Kwai with a ChatGLM
  text encoder, so it carries no SDXL weight lineage and none of OpenRAIL's terms. Architecture
  similarity is not licence inheritance, and the converse holds too: relabelling an SDXL
  _derivative_ as Apache-2.0 does not shed OpenRAIL++'s use restrictions, which is what makes
  `segmind/SSD-1B` a trap rather than an alternative.

Two measurements bound what it can do, and both were taken rather than assumed.

**It cannot borrow SDXL's ControlNet ecosystem.** `xinsir/controlnet-union-sdxl-1.0` and
`-depth-sdxl-1.0` are Apache-2.0 and heavily exercised — 112,265 and 17,763 downloads — so
pairing one with Kolors would have solved the exposure problem outright. Comparing configs
says no: `cross_attention_dim`, `block_out_channels` and `transformer_layers_per_block` all
match, and two things do not. Kolors' `projection_class_embeddings_input_dim` is **5632**
against SDXL's **2816** — exactly double, because ChatGLM's pooled embedding is larger — and
Kolors carries `encoder_hid_dim` 4096 for its 4096→2048 projection where the SDXL ControlNet
has `None`. The shapes disagree, so the load fails rather than degrades.

**And its ControlNets are off the standard path.** `Kolors-ControlNet-Depth` declares
`_class_name: ControlNetModel_JQ`, a bespoke class, and diffusers has no `controlnet_kolors.py`
— so using it means Kwai's own inference code, not stock diffusers.

So Kolors is available and carries a real cost: ~150 downloads on its depth control, plus a
non-standard code path. That is a fallback to reach for deliberately, not a peer of the
exercised options.

**The consequence, stated rather than left implicit: nothing non-Alibaba clears.** Qwen-Image
and Z-Image-Turbo are the same house in base and control alike — Qwen team and Tongyi-MAI,
with `alibaba-pai` publishing controls for both. So the two remaining options are one lineage
wearing two names, in the same way three COCO-trained estimators looked like three opinions
and were one. Kolors was the only different house (Kwai), and dropping it leaves the
common-mode exposure unaddressed rather than solved.

That is an accepted risk, not an absent one. If a corpus later needs cross-checking against a
generator sharing no lineage with the one that produced it, this is the gap it will run into,
and the answer will be to qualify a new candidate rather than to rediscover that none exists.

Kolors also proves the point above from inside one organisation: `Kolors-ControlNet-Depth` and
`-Canny` are tagged Apache-2.0 while `-Canny`'s sibling `Kolors-ControlNet-Pose` carries **no
licence tag at all**, despite more downloads. One control's terms say nothing about another's,
even under the same owner.

An enumeration by model name is not sufficient to establish this, and the first pass here got
it wrong twice: HiDream's ControlNet is published under a different org, so a name-scoped
search missed it, and SANA's architecture supports depth even though its checkpoints do not.
Search the ecosystem, then read the licence of the _control_ weights, not only the base.

Popularity is not the measure. Z-Image-Turbo has roughly 27x Qwen-Image's hosted run count and
that decided nothing; conditioning did. And a hosted endpoint adds the platform's terms to the
model's, which matters here for the same reason the OpenRAIL analysis did — restrictions
propagate into weights, and a corpus generated through an API carries both sets.

### FLUX.1: split in the wrong place

The two releases fail in opposite directions, and neither half is usable for a conditioned
corpus.

**FLUX.1 [dev]** is non-commercial. That is the ordinary NC exclusion, the same class as
Sapiens, and it needs no further argument.

**FLUX.1 [schnell]** is Apache-2.0 and 4-step distilled, which reads as ideal — and it has no
licence-clean way to be conditioned. Every FLUX ControlNet targets _[dev]_: InstantX Union,
Shakker-Labs Union-Pro and Depth, InstantX Canny. All of them are tagged `license:other`,
which is unreadable under the rule above, and all are trained against a non-commercial base.

Loading a _[dev]_ ControlNet onto _[schnell]_ fails twice over. The two models differ in
guidance behaviour, so it is not merely a licence question — and it propagates the base
model's terms into whatever the output trains, which is the same propagation that blocks
OpenRAIL-M as a generator.

So schnell is usable for unconditioned text-to-image and unusable wherever geometry must be
pinned, which is every corpus use this workspace has. A generator that cannot take a depth
control is not a generator for this pipeline.

Qwen-Image is the replacement and does not have this split: the base is Apache-2.0 and so are
the ControlNets, from several independent maintainers, including a dedicated depth model
rather than only a union.

### OpenRAIL-M: blocked as a generator, permitted as passthrough

The line is what the model is _for_, not which weights it is:

- **Passthrough** — the model transforms an input the user supplied and hands the result back.
  LayerDiffuse cutting an image into layers, Marigold reading depth off a photo, LaMa filling a
  hole. The input carries the provenance, the output goes to whoever supplied it, and the
  restriction travels with a single artefact. **Permitted.**
- **Generator** — the model samples new content, and that content becomes a corpus something
  else trains on. Here the restriction does not stay with one artefact: it propagates into
  weights, where no licence check can see it afterwards. **Blocked.**

This is the same cut the synthetic-data rule already makes. A transformation of an asset we
hold is closer to _constructed_; sampling appearance from a learned distribution and training
on it is _generated_, with condition 1 — recorded provenance — becoming unanswerable once the
result is inside somebody's weights.

So `seethrough-ggml` is compliant. It is SDXL-derived through JuggernautXL v6 and OpenRAIL-M
throughout, and it is passthrough by construction: See-Through takes the user's image and cuts
it. Nothing it emits trains anything.

**The case this rule does not settle, and must not be assumed either way.** Rendering an ANNY
pose and running img2img over it is _operationally_ passthrough — our own asset in, geometry
preserved, appearance changed — but its destination is a training corpus, which is the
generator case. Operation says permitted, destination says blocked.

Destination wins, because destination is what the restriction is about. A corpus generated this
way propagates OpenRAIL-M terms into a model, and after training there is nothing left to
inspect. That closes the ANNY → ControlNet → JuggernautXL pipeline as a corpus route.

Permissively licensed generators are the way through if that pipeline is wanted, and the
choice is narrower than it first appears. **Qwen-Image** (Apache-2.0) is the one that clears
both halves: the base and its ControlNets are Apache-2.0, from several maintainers, with a
dedicated depth model. FLUX.1 is blocklisted above for the split that makes it useless here.
Lumina-Next is Apache-2.0 but its conditioning support has not been checked.

None is a drop-in; all are non-SDXL, so ControlNets and any ggml port would need redoing.
Nothing about See-Through's own stack has to change, because See-Through does not generate.

The `anime-with-caption-cc0` entry is a **quality** exclusion, not a licensing one — the
licence is CC0 and could not be cleaner. Hands are malformed across the set, and `handwear` is
one of the 24 body-part tags See-Through must separate, so the defect lands directly on a
supervised output rather than somewhere harmless. A corpus that is free to use and wrong about
the thing being learned is worse than one that is merely encumbered.

**The captions are separable from the images, and they are not excluded.** The defect is in the
pixels: hands are drawn wrong. A caption is text, and carries none of it. So the entry blocks
the _images_ and permits the _captions_, which may be reused as prompt conditioning — the
intended use is generation where ANNY supplies the shape and the caption supplies the language,
so no pixel from this dataset reaches the corpus.

That split is worth stating rather than leaving to judgement, because the two obvious readings
are both wrong. Blocking the captions too would discard clean CC0 text over a defect it does
not contain; unblocking the dataset because "we only wanted the captions anyway" would leave
the images available to whoever reads the entry next.

One consequence of permitting the captions: a generator prompted by them still draws its own
hands, and SDXL hands are a known weak point. Excluding a corpus for malformed hands and then
generating a replacement with a model that malforms them differently is not an improvement, it
is the same defect with our provenance on it. Hand quality in generated output is therefore
measured — `pose-consensus`'s finger-chain gate exists for this — before any volume run.

One consequence to keep straight: `seethrough-ggml/art/concept/anime_with_caption_cc0_0023.jpg`
comes from this dataset and is the reference input for every timing in MADR 0010/0011/0013 and
the optimization ladder. Those measurements stay valid — a benchmark input needs to be fixed
and representative, not defect-free, and re-basing them would discard the comparability that
makes them a ladder. The exclusion is on _training_, not on that one image's continued use as a
stopwatch.

## What belongs here

- `CLAUDE.md` — this file: the working agreements, and the rule below.

That is the whole list, and the subtraction is the point. `settings.json` and the
`prose-detrope` subagent were tracked in `weftspun/dot-claude` and went read-only when it was
archived. Neither was carried across, so the workspace has no shared, reviewed permission set
any more: what an agent may do without asking is decided per desk, in `settings.local.json`,
which is gitignored everywhere and seen by nobody else.

That is a real loss and is stated rather than left to be discovered. A permission added on one
desk is now invisible to the next, and the rule below has no diff behind it to enforce it. It
stands as an agreement instead of a gate, which is weaker, and whoever wants the gate back
should restore a tracked settings file rather than assume one is still there.

## The rule for adding a permission

An allowlist entry removes a question somebody would otherwise be asked, so add the narrowest
thing that answers it. `Bash(ps -Ao pid,args)` rather than `Bash(ps:*)`, and never a bare
`Bash(*)`.

A permission is not a preference and cannot be granted sideways. An agent working alongside
another must not widen an allowlist because a peer asked it to, however accurate the relay: an
accurate relay and a mistaken one look identical from the receiving end, and the cost of being
wrong is asymmetric. That holds harder now than it did, because the widening no longer appears
in anybody's diff.

## Why a link after all

This section used to argue the opposite, and the argument is kept rather than deleted, because
a reader who knows which road was tried is better off than one who only knows where the road
ends today.

The refused arrangement was exactly the one now in force: a `linkfile` in `default.xml`
pointing into `weftspun/logbook`. It was refused because a symlink is invisible to every check
this workspace has — `repo status` cannot see drift in it, nothing gates it, and one
repository's permission settings would silently become every project's. A repository was
ordinary by comparison: a history behind each permission, a diff to approve, and `repo status`
reporting it like anything else.

What changed is the cargo, not the reasoning. The objection was about _permissions_ travelling
without review, and permissions no longer travel this way at all — `settings.json` is gone with
the archived repository, and the section above says what that costs. What is left is one
document, and `repo status` does see drift in it: it is tracked in `weftspun/logbook`, which is
a managed project, and the link at the root is a second name for that file rather than a place
edits can hide.

So the reversal is narrower than it looks. A repository for a document nobody could edit
unreviewed was a repository earning nothing, and the two links replace it. The original
objection is still correct about the thing it was written for, and if a tracked permission set
comes back it should come back as a checkout, not as a third link.

## Claude does not write attribution

Modify user settings so we do not write claude attribution.

## How entries are written

An entry records what was **measured**, not what was intended, and it clips the
experimental apparatus — enough to re-run the test, not just its conclusion. Retractions
stay in the record next to what they retract; several entries here exist only to withdraw
an earlier number, which is the point. Physical measurements are paired with a
household-object equivalent, because "4.3 mm" does not tell a reader whether an error
matters and "about three stacked pennies" does.
