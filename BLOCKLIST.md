# Why each blocklist entry is blocked

`CLAUDE.md` carries the blocklist itself -- the table of what is excluded and the one-line
reason for each. This file carries the argument behind the rows that need one.

**The table is the rule; this is the reasoning.** They are split because they are read at
different times. Somebody checking whether a source is permitted reads a table and stops;
somebody proposing to lift an entry, or wondering whether their case is the one it was written
against, needs the measurement and the retractions. Keeping both in one document meant 570
lines of argument sat between a reader and the next agreement.

Neither half is allowed to drift from the other. `scripts/check_blocklist_detail.py` requires
that every row saying "see below" resolves to a section here, and that every section here
corresponds to a row -- so an entry cannot lose its argument, and an argument cannot outlive
the entry it defends.

### Abliteration is blocked, and the model's own card is the argument

`huihui-ai/Huihui-Qwen3.5-9B-abliterated` is the named instance and the
technique is what is blocked. It came up as a base for an EditScore reward
model, because a grader that refuses to look at an unclothed figure render
scores it low for the wrong reason, and our renders are unclothed bodies.

The card says what was done, in its own words:

> This is a crude, proof-of-concept implementation to remove refusals from an
> LLM model without using TransformerLens.

A refusal direction is found and subtracted from the weights. What that
subtraction does to everything else is not measured, and for a **reward model**
that is the whole problem: the artefact's job is to be a reliable judge, and it
has been edited in a way nobody characterised. A generator that drifts produces
a picture somebody looks at. A judge that drifts silently relabels a corpus.

Tensor parity is not evidence of behavioural parity, and it was tempting to
treat it as such: the abliterated model keeps all 775 tensors against the base's
775, where the Heretic-tool build drops the 15 `mtp.*` ones. Same shapes, edited
values.

**Heretic is permitted, and the line is measurement rather than technique.**
Heretic is automated abliteration — the same directional ablation with a
parameter search over it — so a technique-shaped rule would catch both, and this
one does not. What is blocked is a _crude, unmeasured_ edit, of the kind its own
author calls a proof of concept. A search that optimises against a stated
objective has an argument behind each weight it moves; a hand-subtracted
direction has none.

That distinction is doing real work rather than splitting hairs, and it can be
checked: an abliterated model comes with no statement of what its edit cost, and
a Heretic build comes with the objective it was optimised against. If a future
candidate offers neither, it is the crude case whatever it is called.

**MEASURED: THE STOCK MODEL DOES NOT REFUSE, SO THE PREMISE WAS FALSE.** This
section first said the count was one run away. It has been run.
`Qwen/Qwen3-VL-8B-Instruct` with the stock
`EditScore/EditScore-Qwen3-VL-8B-Instruct` adapter, no uncensoring of any kind,
was asked to grade twelve restyles of an unclothed ANNY render:

    1024x1024 inputs   0 refusals of 12
    512x512 inputs     0 refusals of 12

Every frame came back with a number. A refusal here would be a non-answer rather
than a low score, and there were none of either kind — the low scores it did
return are judgements about edits that ignored their instruction, which is the
model working.

So the reason for reaching for an edited base did not exist. Nobody had checked,
and the check cost one run against images we already had. That is the whole
entry: refusal tuning targets requests to _produce_ content, grading is not
producing, and an unmeasured assumption sent us looking for weights that
somebody had modified in ways nobody characterised.

The sizing came free with it, and it is the useful half now. At NF4 the weights
are 6.29 GiB and the peak is 8.60 GiB on 1024x1024 inputs — over the ASUS
UGen300's 8 GB — but 6.75 GiB at 512x512, which is `image_max_pixels` in
EditScore's own training config. The vision tokens were the budget, not the
weights, and feeding the model four times the pixels it was trained on was our
error rather than the device's limit.

### `rf-detr-keypoint-data` is the holdout, not a training set

It is **validation only, never training**, for two independent reasons. Either
one is enough.

**It contains the entire blinded holdout.** The repository takes every val2017
image with a non-crowd keypointed person, 2,346 of 5,000, and splits them 2,112
train and 234 test. The 523 images of `coco_person_commercial_val2017` are all
inside it:

    holdout images in its TRAIN split   481
    holdout images in its TEST split     42
    total                               523 of 523

Training on it trains on the holdout. The blinded rule is not only about
gradient steps, and a split labelled `train-*.parquet` is the most direct way
there is to take one.

**And 78% of it is licence-dirty.** Only 523 of val2017's 5,000 person images
are commercial and derivatives safe, which is what `filter_coco_licenses.py`
measures. This set has 2,346, so 1,823 carry the NC, ND and share-alike terms
that filter exists to drop. Its README states `CC BY 4.0` for the whole set, and
that claim is wrong.

The two faults compound rather than overlap. The licence-clean images are
exactly the holdout, so there is no subset that is both trainable and clean. A
keypoint training set has to be built rather than filtered out of this one,
which is what the renderer in RFD 0122 is for.

`rf-detr-detection-data` and `rf-detr-segmentation-data` are unaffected. Both
come from a Roboflow clothing set rather than COCO, and neither contains a
holdout image.

### `uv` is blocklisted for project environments, and `pixi` is why

The objection is the same one submodules get, one layer down. A `uv pip install`
leaves an environment that no file declares, no lockfile pins, and nobody else
can rebuild. `repo status` cannot see it, a diff cannot show it, and the next
desk gets a different set of versions with no report.

The failure is not hypothetical and is recorded next door. Standing up the Hailo
compiler on a Mac took more than twenty packages, discovered one
`ModuleNotFoundError` at a time, installed ad hoc. Every one of them was a real
dependency of a real tool, and after the session none of it existed anywhere:
not in a manifest, not in a lock, not in the logbook. The work was repeatable
only by repeating the guessing.

`pixi` answers exactly that. `pixi.toml` declares the environment, `pixi.lock`
pins it, both are tracked, and a second environment for a second job is a
`[feature]` rather than a second undeclared venv. `tropes-removal-model` now
carries a `gate` environment with `no-default-feature` for precisely this: the
gate's dependencies were being hand-listed in two CI `pip install` lines that
could drift from the manifest without anybody noticing.

Two limits worth stating rather than discovering.

**This is about PROJECT environments, not about the binary.** `uvx` or `uv run`
to invoke a one-shot tool that touches nothing is not what this blocks. What it
blocks is an environment that work depends on and no file describes.

**A tool that ships its own resolver keeps it.** This rule does not ask anybody
to rewrite a dependency stack that already declares itself elsewhere, and it
does not reach into third-party projects, where the density rule above already
says to match what is there.

**An embedded interpreter that declares its pins in source is exempt.** This is a
third limit and it was added because the rule as written forbade something it was
never aimed at. `pythonx` embeds CPython in a NIF and its entry point is
`Pythonx.uv_init/1`, which takes a `pyproject.toml` as a string literal:

    Pythonx.uv_init("""
    [project]
    name = "nx_shuttle_secondary"
    version = "0.0.0"
    requires-python = "==3.11.*"
    dependencies = ["onnxruntime==1.20.1", "onnx==1.17.0", "numpy"]
    """)

That block is the declaration. It is tracked, it appears in a diff, it pins the
interpreter and the packages, and anybody running the code gets the same set. The
hazard this row names -- an environment nothing declares and nobody can rebuild --
is absent. Measured once: the resolve took 219ms and installed onnxruntime 1.20.1,
onnx 1.17.0 and numpy 2.4.6, from a list a reader can see.

The reason it cannot be `pixi` instead is `weft-warp-burrito`. Burrito packages an
Elixir application into one executable, and an executable cannot shell out to an
environment that is not inside it. An embedded interpreter travels; a `pixi`
environment beside the binary does not.

What stays blocked is the shape, not the letters `uv`: an interpreter whose
packages arrive by hand, a `uv pip install` issued at runtime against a set no
file lists, or a `uv_init` block that drifts from what the code actually imports.
The pins are the exemption. Without them this is the Mac session again, with an
extra layer.

### Git submodules are blocklisted, and `default.xml` is why

A submodule pins a dependency in a file only `git` reads. `repo status` does not
see it, the manifest does not carry it, and a bumped submodule appears in a diff
as a bare hash with no name, no branch and no reason attached.

That is the same invisibility the **Sides** rule exists to stop. An unplaced
project is drift, and a submodule is an unplaced project that also claims to be
placed.

So a third-party dependency is a `<project>` in the goal manifest's
`default.xml`, on a side, with a pinned `revision`. The entry answers "what
version, and from where" in fields a tool reads: a name, a path, a remote and a
revision. A `.gitmodules` line answers the same two questions with a bare hash
and no name attached, which is the whole of the difference.

**Corrected: the "why" is not in the manifest, and the earlier wording said it
was.** This paragraph used to read that the manifest answers "what version, from
where, and why, because a comment can sit beside the entry". Comments in a
manifest are now blocklisted and `check_manifest_comments.py` in
`weftspun/weftspun-keypoint` enforces it, so that clause describes an
arrangement that no longer exists.

The reason is that a comment beside a `<project>` is the one thing in an
otherwise checkable file that nothing can check. Paths resolve, revisions fetch,
linkfiles are followed — and the paragraph above an entry goes on describing the
path or revision it had when somebody wrote it, with no diff, no CI run and no
`repo` command reporting that the two have parted. That is the same
second-place-a-fact-lives failure this section is itself written against, one
layer down.

So the "why" moves to the commit message and the pull request description, which
is where the rule on editing other people's codebases already sends it, and to
an RFD when it is durable. Both are reviewed when written and neither claims to
describe a current state, so neither can go stale in place.

Two consequences worth stating rather than discovering:

- **Fork before you pin.** A `revision` on somebody else's repository is a
  promise they have not made. `godot-cpp` is forked to `weftspun/godot-cpp` for
  exactly this, and pinned at the commit `godot-whisper` ships, so a
  nine-platform build is a question about our code rather than about the binding
  library.
- **A vendored copy is not a submodule and is not blocked.** Copying source into
  `thirdparty/` with its licence and a recorded upstream hash is visible in
  every diff, which is the property submodules lack. Prefer a manifest entry,
  vendor when the dependency is small and stable, and do not reach for a
  submodule in either case.

### Blender is blocklisted, and reproducibility is why

A render is a measurement, and a measurement that cannot be re-run identically
is not one. Blender's headless output moves with the version and with the build
flags it was compiled against, so the same scene rendered on two desks is two
corpora with one name. Nothing reports the difference: the images look right in
both places.

**No exceptions.** Not for a depth pass, not for a one-off bake, not for a
person opening the GUI to check something by eye. A carve-out for manual use is
how the dependency comes back, because the manual result is what somebody then
wants to keep.

The version installed here when this was written was **5.2.0 LTS**, build date
2026-07-14, from a package manager, pinned by nothing. That is the whole
argument in one line: no file in this workspace records it, `repo status` cannot
see it, and the next desk has whatever its own package manager last offered.

**What this costs, stated rather than discovered.** Two things depended on it
and both are now open questions rather than solved problems.

`render_image.py` in `6-datasource/dataflow-coco-gemx` runs as `blender -b
--python render_image.py`, and it writes the depth pass. Depth is the
conditioning signal for the generation path, not a by-product, so this is a hole
in the pipeline and not a tidying-up. The file stays in the tree as the record
of what the pass has to produce; it is not the way to produce it any more.

RFD 107a's PBR bake said to do the bake in Blender because MPFB2 is a Blender
addon and the material was authored there. That method is gone with this entry.
The bake still has to happen -- albedo, roughness and normal over the hm08 UV
layout, metallic a constant zero -- and it now needs a renderer that a
`pixi.toml` can pin.

The replacement is not named here, because naming one without measuring it is
how the last unpinnable dependency arrived. What a candidate has to show: it
installs from a lockfile, it renders the same bytes twice on two machines, and
the check for that ships with it.

### BRIA RMBG is blocklisted, and we already own the alternative

`briaai/RMBG-2.0` removes an image background, and Pixal3D's `preprocess_image`
reaches for it whenever an input has no alpha channel. It fails two bars at
once.

**It is gated.** Hugging Face answers `401 ... Access to model briaai/RMBG-2.0
is restricted` until somebody accepts terms in a browser. A licence that cannot
be read without accepting it cannot be gated on, which is the same objection
that keeps DWPose out: terms nobody has read travel into whatever the model
touches.

**And it is non-commercial.** RMBG is offered for non-commercial use with a
separate paid agreement for anything else, which is the class
`filter_coco_licenses.py` exists to drop.

**What replaces it, and the answer is different for the two cases.**

For anything this workspace renders, no matting model is needed at all. The
silhouette of a render is not a thing to infer from pixels: it is which rays hit
the body, which the depth AOV already reports exactly. `render_view.py` writes
RGBA with that alpha, and `preprocess_image` uses an existing alpha channel
directly rather than calling any model. The matte is then ground truth rather
than a prediction, which is strictly better than what the blocked model would
have produced.

For images we did not render, See-Through is the in-house route. It is
passthrough by construction, it already separates a picture into labelled
layers, and RFD 1079 covers what it does and does not model. Reaching for a
gated third-party matter when the workspace maintains a segmentation model of
its own is the drift this table exists to stop.

The distinction worth keeping: the render case removes the dependency, and the
photograph case replaces it. Only the second is a substitution, and only the
second needs measuring against what it replaced.

### Qwen-Image-Edit corrupts at the only precision this desk can run it

Apache-2.0 in base and weights alike, and that is not the problem. It is 20.43B
parameters, 57.7 GB on disk, needing roughly 38 GB at bf16 against a 24 GB card.
So it runs here at NF4 or not at all, and generated-synthetic condition 5 says
quantised weights do not produce corpus data. That alone closes it as a corpus
generator on this hardware.

What makes it a blocklist entry rather than a hardware note is that the
quantised path is also measurably broken. At NF4 it peaks at 11.9 GiB and
returns images speckled across every pixel — camera-correct and noise-corrupted,
the figure roughly in place under a layer of grain. The silhouette scores run
0.098 to 0.719 against a control of 0.222, so some frames are barely
distinguishable from a body that moved 20 px.

Three explanations were eliminated rather than assumed, and each cost a run:

- **Not the torch version.** `interactor-pixal3d` recorded the same corruption
  with torch 2.4.1 the one constant, and asked for a retest at 2.6 or newer. On
  torch 2.11.0+cu128, diffusers 0.40.0 and bitsandbytes 0.50.1 it is unchanged,
  so that hypothesis is retired rather than carried forward.
- **Not the guidance.** The first run passed `true_cfg_scale=4.0` with no
  negative prompt, which diffusers silently ignores. Re-run with guidance
  actually on: same corruption, twice the time.
- **Not the input.** OmniGen2 edits the identical grey matte render cleanly, so
  the frame is not out of distribution in a way that would break any editor.

8-bit would have isolated the quantiser and is not available here: int8 puts
about 20 GB of weights on a 24 GB card, and the run reached step 3 of 30 at
4,925 s/it with 42 GB resident in host RAM — 37 hours projected for one image,
against 3.3 s/it at NF4.

**The corruption was measured under our settings, not upstream's, and is not
being chased.** Both runs used 30 inference steps where upstream's examples use
50, and the guidance re-run passed an empty negative prompt -- the same empty
string that turned out to be doing all the work in the OmniGen2 comparison
retracted above. So "broken at NF4" should be read as broken under a
configuration we chose, with at least two knobs untouched.

Nothing about the block depends on that, which is why it is a qualification
rather than a retraction. The model needs about 38 GB at bf16 against a 24 GB
card, so on this desk it runs only in the mode that does not produce corpus
data, and that is true whatever the step count says. The honest position is:
blocked for a structural reason, plus a quality observation that was not run to
ground.

**Not blocked for hardware that can hold it.** A card with 48 GB or more runs
the published bf16 path, which nothing here has tested and nothing here impugns.
The entry says something narrower: on this desk the only runnable mode is the
one condition 5 forbids, and it is broken as well as forbidden.

OmniGen2 is the replacement and needs no exception — 7.8B, Apache-2.0, 17.3 GiB
at bf16, clean output on the same input.

### P3-SAM's licence excludes territories, which is a different failure

`Tencent-Hunyuan/Hunyuan3D-Part` ships under Tencent's own Community License
Agreement, and it carves out the EU, the UK and South Korea. RFD 0041 records
the model as MIT; that is wrong, and `logbook-rfd0016-model-repos.md` already
corrected it by reading the real LICENSE file.

The other entries here block on what the output may be used for. This one blocks
on **who may run the tool at all**, which is a worse property for a workspace
whose collaborators and customers are not enumerated in advance. A restriction
on the output can at least be traced through a corpus; a restriction on the
operator means the same command is permitted at one desk and forbidden at
another, and nothing in a manifest or a build log would show the difference.

Passthrough does not rescue it either, and it is worth saying why, because the
OpenRAIL entry does rescue passthrough uses. That exemption turns on the
restriction travelling with a single artefact to whoever supplied it. A
territory exclusion does not travel with the artefact — it sits on the person
invoking the model — so the distinction the OpenRAIL rule is built on has
nothing to bite.

### Krea 2 is revenue-gated, and that propagates

The Krea 2 Community License permits commercial use free only below \$1M
company-wide annual revenue and fewer than 50 seats; above either line it needs
a separate enterprise agreement. That is a use restriction, and this workspace
already has a rule about those: OpenRAIL-M is blocked as a _generator_ because
restrictions travel into whatever trains on the output, where no licence check
can see them afterwards. Krea 2 is a text-to-image generator, so its outputs are
corpus data, so the same reasoning applies unchanged.

The revenue threshold makes it worse rather than better, and the reason is worth
stating. Whether the licence is satisfied depends on _who deploys the trained
model_, which is not a fact about our corpus and not one we can settle in
advance. A term that clears today for a small deployer and fails for their
customer is a term that cannot be gated on at corpus-build time.
`logbook-rfd0016-model-repos.md` already flagged this as "clears the bar for a
small deployer, not for every possible customer" — this entry is that flag
resolved rather than carried.

**The second reason is newer and independent.** RFD 0016's plan for it was the
Q4_K_M GGUF set: 33.8 GB bf16 down to 9.30 GB quantised, because that is what
fits. Generated-synthetic condition 5 now says quantised weights do not produce
corpus data, so the deployment shape that made the model affordable is the one
that disqualifies its output. Even with the licence resolved, the plan on file
would not have produced usable corpus.

Neither reason depends on the other. A permissive re-licence would leave the Q4
problem, and a 48 GB card running bf16 would leave the revenue gate.

### A corpus generator must be a checkpoint we hold

Any API-only model is excluded as a _corpus source_, and the reason is
structural rather than contractual, so it survives whatever the terms happen to
say this year.

**Condition 1 cannot be satisfied.** The generated-synthetic rule requires the
generating model and checkpoint recorded with the data so the corpus can be
regenerated and its provenance answered later. A hosted model has no checkpoint
to pin: the weights change on the vendor's schedule and the endpoint is
eventually retired, so "generated by X" stops resolving to the thing that
generated it. That is the same failure `EasyDiffusion outputs` is blocklisted
for, arriving through a different door.

Two further reasons apply to Nano-banana / Gemini specifically, and both would
be sufficient on their own:

- The [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms)
  state that users "may not use the services to develop models that compete with
  the services", nor "reverse engineer, extract, or replicate any component of
  the services, including underlying data or models". Building a training corpus
  _is_ using the service to develop a model; whether the result competes is a
  judgement we are not positioned to make, which is the same propagation problem
  OpenRAIL poses, now with a counterparty able to enforce it.
- On the unpaid tier and AI Studio, Google uses submitted content **and
  generated responses** to improve its products, and human reviewers may read
  them. Our renders, prompts and captions would go with it.

Worth recording how SDPose-OOD actually used it, because the paper is the reason
the question came up: Nano-banana produced the colour-sketch variant of COCO-OOD
— an **evaluation** set, not training data — and the sets under test were
deliberately made with CycleGAN and StyTR² "to avoid introducing priors from
large-scale pretrained diffusion models". Their own caution is the argument
against reaching further than they did.

Nothing is lost by the exclusion. CycleGAN fills the stylisation role and clears
all three bars: BSD, offline, and pinnable.

### A generator needs licence-clean depth conditioning, not just a licence

The permissive licence is the easy half and it is not the deciding one. Every
corpus use here renders an ANNY pose and requires the generated image to keep
that geometry, so a generator that cannot take a **depth** control cannot do the
job however clean its terms are.

Stating it as a rule rather than a list, because the list keeps growing and each
entry arrives looking attractive:

- **HiDream-I1** is **MIT** — the most permissive licence of any candidate
  reviewed — and its only conditioning is `ControlNetLoRA/hidream-i1`: a single
  LoRA, not a ControlNet family, under `license:other`, with 14 downloads and no
  likes. That fails the same way the FLUX ControlNets do, on unreadable terms
  rather than on absence.
- **SANA** is Apache-2.0 throughout and its ControlNet _architecture_ supports
  depth — `SanaControlNetModel` is in diffusers. **No depth checkpoint is
  published**: the released weights are HED only. Edge conditioning from a
  render carries silhouette and internal contours with no depth ordering, so it
  cannot say which limb is in front, and for a body limb overlap is the hard
  part. This is the one candidate whose gap is _work rather than terms_ — the
  licence is clean end to end, so a depth ControlNet could be trained. Costed as
  a training job, not adopted as-is.
- **FLUX.1** fails a third way, below.

Three clear at the time of writing, all Apache-2.0 in base _and_ control:

- **Qwen-Image** — a union plus a dedicated depth model, from several
  independent maintainers.
- **Z-Image-Turbo** — union, `alibaba-pai`. **Kolors is not blocklisted, and its
  position is precise.** It is the only from-scratch, Apache-2.0,
  SDXL-architecture model with its own ControlNets — trained by Kwai with a
  ChatGLM text encoder, so it carries no SDXL weight lineage and none of
  OpenRAIL's terms. Architecture similarity is not licence inheritance, and the
  converse holds too: relabelling an SDXL _derivative_ as Apache-2.0 does not
  shed OpenRAIL++'s use restrictions, which is what makes `segmind/SSD-1B` a
  trap rather than an alternative.

Two measurements bound what it can do, and both were taken rather than assumed.

**It cannot borrow SDXL's ControlNet ecosystem.**
`xinsir/controlnet-union-sdxl-1.0` and `-depth-sdxl-1.0` are Apache-2.0 and
heavily exercised — 112,265 and 17,763 downloads — so pairing one with Kolors
would have solved the exposure problem outright. Comparing configs says no:
`cross_attention_dim`, `block_out_channels` and `transformer_layers_per_block`
all match, and two things do not. Kolors'
`projection_class_embeddings_input_dim` is **5632** against SDXL's **2816** —
exactly double, because ChatGLM's pooled embedding is larger — and Kolors
carries `encoder_hid_dim` 4096 for its 4096→2048 projection where the SDXL
ControlNet has `None`. The shapes disagree, so the load fails rather than
degrades.

**And its ControlNets are off the standard path.** `Kolors-ControlNet-Depth`
declares `_class_name: ControlNetModel_JQ`, a bespoke class, and diffusers has
no `controlnet_kolors.py` — so using it means Kwai's own inference code, not
stock diffusers.

So Kolors is available and carries a real cost: ~150 downloads on its depth
control, plus a non-standard code path. That is a fallback to reach for
deliberately, not a peer of the exercised options.

**The consequence, stated rather than left implicit: nothing non-Alibaba
clears.** Qwen-Image and Z-Image-Turbo are the same house in base and control
alike — Qwen team and Tongyi-MAI, with `alibaba-pai` publishing controls for
both. So the two remaining options are one lineage wearing two names, in the
same way three COCO-trained estimators looked like three opinions and were one.
Kolors was the only different house (Kwai), and dropping it leaves the
common-mode exposure unaddressed rather than solved.

That is an accepted risk, not an absent one. If a corpus later needs
cross-checking against a generator sharing no lineage with the one that produced
it, this is the gap it will run into, and the answer will be to qualify a new
candidate rather than to rediscover that none exists.

Kolors also proves the point above from inside one organisation:
`Kolors-ControlNet-Depth` and `-Canny` are tagged Apache-2.0 while `-Canny`'s
sibling `Kolors-ControlNet-Pose` carries **no licence tag at all**, despite more
downloads. One control's terms say nothing about another's, even under the same
owner.

An enumeration by model name is not sufficient to establish this, and the first
pass here got it wrong twice: HiDream's ControlNet is published under a
different org, so a name-scoped search missed it, and SANA's architecture
supports depth even though its checkpoints do not. Search the ecosystem, then
read the licence of the _control_ weights, not only the base.

Popularity is not the measure. Z-Image-Turbo has roughly 27x Qwen-Image's hosted
run count and that decided nothing; conditioning did. And a hosted endpoint adds
the platform's terms to the model's, which matters here for the same reason the
OpenRAIL analysis did — restrictions propagate into weights, and a corpus
generated through an API carries both sets.

### FLUX.1: split in the wrong place

The two releases fail in opposite directions, and neither half is usable for a
conditioned corpus.

**FLUX.1 [dev]** is non-commercial. That is the ordinary NC exclusion, the same
class as Sapiens, and it needs no further argument.

**FLUX.1 [schnell]** is Apache-2.0 and 4-step distilled, which reads as ideal —
and it has no licence-clean way to be conditioned. Every FLUX ControlNet targets
_[dev]_: InstantX Union, Shakker-Labs Union-Pro and Depth, InstantX Canny. All
of them are tagged `license:other`, which is unreadable under the rule above,
and all are trained against a non-commercial base.

Loading a _[dev]_ ControlNet onto _[schnell]_ fails twice over. The two models
differ in guidance behaviour, so it is not merely a licence question — and it
propagates the base model's terms into whatever the output trains, which is the
same propagation that blocks OpenRAIL-M as a generator.

So schnell is usable for unconditioned text-to-image and unusable wherever
geometry must be pinned, which is every corpus use this workspace has. A
generator that cannot take a depth control is not a generator for this pipeline.

Qwen-Image is the replacement and does not have this split: the base is
Apache-2.0 and so are the ControlNets, from several independent maintainers,
including a dedicated depth model rather than only a union.

### OpenRAIL-M: blocked as a generator, permitted as passthrough

The line is what the model is _for_, not which weights it is:

- **Passthrough** — the model transforms an input the user supplied and hands
  the result back. LayerDiffuse cutting an image into layers, Marigold reading
  depth off a photo, LaMa filling a hole. The input carries the provenance, the
  output goes to whoever supplied it, and the restriction travels with a single
  artefact. **Permitted.**
- **Generator** — the model samples new content, and that content becomes a
  corpus something else trains on. Here the restriction does not stay with one
  artefact: it propagates into weights, where no licence check can see it
  afterwards. **Blocked.**

This is the same cut the synthetic-data rule already makes. A transformation of
an asset we hold is closer to _constructed_; sampling appearance from a learned
distribution and training on it is _generated_, with condition 1 — recorded
provenance — becoming unanswerable once the result is inside somebody's weights.

So `seethrough-ggml` is compliant. It is SDXL-derived through JuggernautXL v6
and OpenRAIL-M throughout, and it is passthrough by construction: See-Through
takes the user's image and cuts it. Nothing it emits trains anything.

**The case this rule does not settle, and must not be assumed either way.**
Rendering an ANNY pose and running img2img over it is _operationally_
passthrough — our own asset in, geometry preserved, appearance changed — but its
destination is a training corpus, which is the generator case. Operation says
permitted, destination says blocked.

Destination wins, because destination is what the restriction is about. A corpus
generated this way propagates OpenRAIL-M terms into a model, and after training
there is nothing left to inspect. That closes the ANNY → ControlNet →
JuggernautXL pipeline as a corpus route.

Permissively licensed generators are the way through if that pipeline is wanted,
and the choice is narrower than it first appears. **Qwen-Image** (Apache-2.0) is
the one that clears both halves: the base and its ControlNets are Apache-2.0,
from several maintainers, with a dedicated depth model. FLUX.1 is blocklisted
above for the split that makes it useless here. Lumina-Next is Apache-2.0 but
its conditioning support has not been checked.

None is a drop-in; all are non-SDXL, so ControlNets and any ggml port would need
redoing. Nothing about See-Through's own stack has to change, because
See-Through does not generate.

The `anime-with-caption-cc0` entry is a **quality** exclusion, not a licensing
one — the licence is CC0 and could not be cleaner. Hands are malformed across
the set, and `handwear` is one of the 24 body-part tags See-Through must
separate, so the defect lands directly on a supervised output rather than
somewhere harmless. A corpus that is free to use and wrong about the thing being
learned is worse than one that is merely encumbered.

**The captions are separable from the images, and they are not excluded.** The
defect is in the pixels: hands are drawn wrong. A caption is text, and carries
none of it. So the entry blocks the _images_ and permits the _captions_, which
may be reused as prompt conditioning — the intended use is generation where ANNY
supplies the shape and the caption supplies the language, so no pixel from this
dataset reaches the corpus.

That split is worth stating rather than leaving to judgement, because the two
obvious readings are both wrong. Blocking the captions too would discard clean
CC0 text over a defect it does not contain; unblocking the dataset because "we
only wanted the captions anyway" would leave the images available to whoever
reads the entry next.

One consequence of permitting the captions: a generator prompted by them still
draws its own hands, and SDXL hands are a known weak point. Excluding a corpus
for malformed hands and then generating a replacement with a model that malforms
them differently is not an improvement, it is the same defect with our
provenance on it. Hand quality in generated output is therefore measured —
`pose-consensus`'s finger-chain gate exists for this — before any volume run.

One consequence to keep straight:
`seethrough-ggml/art/concept/anime_with_caption_cc0_0023.jpg` comes from this
dataset and is the reference input for every timing in MADR 0010/0011/0013 and
the optimization ladder. Those measurements stay valid — a benchmark input needs
to be fixed and representative, not defect-free, and re-basing them would
discard the comparability that makes them a ladder. The exclusion is on
_training_, not on that one image's continued use as a stopwatch.
