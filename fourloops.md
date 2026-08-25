# Running the four loops

Four pipelines share one shape: propose an artifact, score it against whatever
conditioned it, repair, go round again. This says what has to be running before a
round can happen, and what each loop costs while it runs. The stage beside it
carries the order and the chart beside it carries the schema, so neither is
repeated here.

## Start the server first

The notebooks live on the Livebook server in `7-service/service-livebook`, and
`LIVEBOOK_HOME` points at its notebooks directory, so all four are on the home
screen.

    MIX_ENV=prod mix run --no-halt -e 'IO.puts ServiceLivebook.start()'

It prints a URL with a boot token. Two other ways to run it exist and neither
reaches the card: the container, and the same image under bubblewrap. Both are
for the schema and the prose, not for a round.

A Windows service is closed. A Mix release installs one through `erlsrv`, whose
install command requires a node name, and Livebook starts distribution itself
with its own EPMD module, so a release that already started a node aborts with
`{:already_started, _}`. That was measured, not predicted: the first container
did exactly this until the release env set `RELEASE_DISTRIBUTION=none`.

## What has to be listening

A loop calls services over HTTP and models through `pixi`. A service that is not
up produces a connection error rather than a low score, which is the intended
behaviour: an unmet precondition is a failure, never a quiet zero.

| what                         | where                 | needed by                             |
| ---------------------------- | --------------------- | ------------------------------------- |
| CycleGAN style transfer      | `localhost:8000`      | loop 3                                |
| Pixal3D                      | `localhost:8002`      | loop 4                                |
| VoxHammer                    | `localhost:8003`      | loop 4's latent arm, which is stubbed |
| pixi environment `omnigen2`  | the corpus repository | loops 2, 3, 4                         |
| pixi environment `editscore` | the corpus repository | all four                              |
| pixi environment `anny`      | the corpus repository | loop 1                                |

The two heavy environments cannot be merged and the notebooks do not try:
OmniGen2 pins `torch 2.6.0+cu124` and EditScore pins `cu128`. The notebooks pin
only Pillow, NumPy, Matplotlib and Requests in their own embedded interpreter,
and reach the models by subprocess.

## What a round costs

Everything runs on the desk card, 24 GB. The numbers below were measured by the
scripts that do the work, not estimated, and they are what the settings follow
from rather than decoration.

| stage                  | precision | peak                    | note                                  |
| ---------------------- | --------- | ----------------------- | ------------------------------------- |
| EditScore at 512x512   | NF4       | 6.75 GiB                | fits the 8 GiB budget                 |
| EditScore at 1024x1024 | NF4       | 8.60 GiB                | does not, hence a pixel cap of 262144 |
| OmniGen2               | bf16      | about 17 GiB of weights | no quantised path is offered          |

### Measured on the desk, 2026-08-24

The table above was read out of the scripts. These were measured by running them.

| what ran                           | weights   | peak       | seconds  |
| ---------------------------------- | --------- | ---------- | -------- |
| OmniGen2 bf16, 1024x1024, 30 steps | 14.75 GiB | 17.14 GiB  | 131      |
| OmniGen2 NF4, same input and seed  | 4.33 GiB  | 6.72 GiB   | 133      |
| EditScore NF4, 512x512             |           | 6.7506 GiB | 28 to 36 |

Four bits bought memory and not speed: 133 s against 131 s, because dequantisation costs
about what the narrower reads save on this card. The NF4 peak of 6.72 GiB sits under the
UGen300's 8 GB, which is 7.45 GiB if that number is decimal, leaving 0.73 GiB for
everything else on the module. Fitting the memory is necessary and not sufficient: the
device runs a fixed operator set, and nothing has censused this graph against it.

EditScore returns each component out of ten and `overall` as their geometric mean, so a
score is in 0..10. A matching instruction scored 4.29 on a pair of ANNY views and a nonsense
instruction on the same pair scored 0.0.

The components are recorded rather than only their mean, because the mean is what the two
runs agree on and the components are where they differ. These sat in the chart beside this
entry until the chart was removed, so they are written out here instead.

| instruction             | prompt following | consistency | perceptual quality | overall |
| ----------------------- | ---------------- | ----------- | ------------------ | ------- |
| a matching instruction  | 10.0             | 9.2         | 2.0                | 4.29    |
| nonsense, the same pair | 0.0              | 10.0        | 2.0                | 0.00    |

Consistency rising to 10.0 on the nonsense run is the tell: an edit that was not asked for
was not made, so the pair is maximally consistent and the score is correctly zero.

The asymmetry is a rule rather than an oversight. A quantised generator does not
write corpus data; a quantised verifier may, because condition 5 is about what
produces the corpus and a scorer produces a number.

## Two things that will bite

RF-DETR emits 17 joints and the ANNY keypoint asset emits 23, the extra six being
feet. They are separate vocabularies with a mapping between them, because a
23-row array reaching a 17-row consumer truncates at the tail, which is where the
feet are.

Loop 4 routes on the spread across views rather than on one number. High variance
means the views disagree about the shape, and a shape wrong along one axis scores
well from the view that hides it. That arm calls VoxHammer, whose steps raise
`NotImplementedError` outside stub mode and which takes a mesh rather than the
latent. The notebook reports that it selected an arm that cannot run rather than
using the other one, because that substitution would record a geometry failure as
an appearance failure that was repaired.

## What no loop may touch

`coco_person_commercial_val2017` is the blinded holdout: not inspected while
developing, not used to choose a checkpoint, a threshold or a stopping point, and
not consulted to decide whether an approach is working. Anything derived from it
inherits that status, including the stylized COCO-OOD sets, which are evaluation
only twice over.

Every round writes a provenance record naming the model, the checkpoint, the
prompt or instruction, the seed and the hashes. Generated data that cannot be
regenerated and whose provenance cannot be answered later does not belong in a
corpus, and the record is what makes the answer possible.
