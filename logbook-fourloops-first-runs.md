# Logbook: the first four-loop rounds on the desk card

Everything the four loops asserted was written before a card was switched on. Two EditScore
calls have now run. They confirmed one number, moved none, and killed one assumption, and
this entry is where those measurements live now that `fourloops.md` is gone.

## Apparatus

The desk card is 24 GB. Services are reached over HTTP and models through `pixi`, and a
service that is not up produces a connection error rather than a low score, which is the
intended behaviour: an unmet precondition is a failure, never a quiet zero.

| what                         | where                 | needed by                             |
| ---------------------------- | --------------------- | ------------------------------------- |
| CycleGAN style transfer      | `localhost:8000`      | loop 3                                |
| Pixal3D                      | `localhost:8002`      | loop 4                                |
| VoxHammer                    | `localhost:8003`      | loop 4's latent arm, which is stubbed |
| pixi environment `omnigen2`  | the corpus repository | loops 2, 3, 4                         |
| pixi environment `editscore` | the corpus repository | all four                              |
| pixi environment `anny`      | the corpus repository | loop 1                                |

The notebooks run on the Livebook server in `7-service/service-livebook`, started with

    MIX_ENV=prod mix run --no-halt -e 'IO.puts ServiceLivebook.start()'

which prints a URL carrying a boot token. The two heavy environments cannot be merged and
the notebooks do not try: OmniGen2 pins `torch 2.6.0+cu124` and EditScore pins `cu128`. The
notebooks pin only Pillow, NumPy, Matplotlib and Requests in their own embedded interpreter
and reach the models by subprocess.

A Windows service is closed. A Mix release installs one through `erlsrv`, whose install
command requires a node name, and Livebook starts distribution itself with its own EPMD
module, so a release that already started a node aborts with `{:already_started, _}`. That
was measured rather than predicted: the first container did exactly this until the release
env set `RELEASE_DISTRIBUTION=none`.

## Measured on the desk, 2026-08-24

| what ran                           | weights   | peak       | seconds  |
| ---------------------------------- | --------- | ---------- | -------- |
| OmniGen2 bf16, 1024x1024, 30 steps | 14.75 GiB | 17.14 GiB  | 131      |
| OmniGen2 NF4, same input and seed  | 4.33 GiB  | 6.72 GiB   | 133      |
| EditScore NF4, 512x512             |           | 6.7506 GiB | 28 to 36 |

Four bits bought memory and not speed: 133 s against 131 s, because dequantisation costs
about what the narrower reads save on this card. The EditScore peak is the one number the
run confirmed rather than corrected -- the scoring script already cited 6.75 GiB, and
6.7506 GiB is that number measured.

`logbook-rfd0016-model-repos.md` carries the same NF4 pair against the ASUS UGen300's 8 GB
and is not repeated here.

## The scale is 0 to 10, and the router assumed 0 to 1

EditScore returns each component out of ten and `overall` as their geometric mean, so a
score lands in 0..10.

| instruction             | prompt following | consistency | perceptual quality | overall |
| ----------------------- | ---------------- | ----------- | ------------------ | ------- |
| a matching instruction  | 10.0             | 9.2         | 2.0                | 4.29    |
| nonsense, the same pair | 0.0              | 10.0        | 2.0                | 0.00    |

The components are recorded rather than only their mean, because the mean is what the two
runs agree on and the components are where they differ. Consistency rising to 10.0 on the
nonsense run is the tell: an edit that was not asked for was not made, so the pair is
maximally consistent and `overall` is correctly zero. The nonsense instruction is the
negative control, and a scorer that returned anything above zero for it would be certifying
its own defect.

Loop four's threshold has now been wrong twice for one reason. First as a variance against
0.15, which almost never fired; then as a standard deviation on a range ten times larger,
where it fires on almost anything. A constant compared against an assumed range is the
defect, not the constant, so the router becomes scale-free -- spread over mean -- and the
threshold is set from measured view scores rather than from a third guess.

The quantisation asymmetry is a rule rather than an oversight. A quantised generator does
not write corpus data; a quantised verifier may, because condition 5 is about what produces
the corpus and a scorer produces a number.

## Where the rest of that document went

`fourloops.md` also carried the loop shapes, the two-counts hazard and the holdout rules.
None of that was a measurement, and all three are now stated once in a layer a gate reads:
`fourloops-plan.usda` for the task graph and `fourloops-etnf.usda` for the schema, the
hazards and the columns deliberately absent. `scripts/check_fourloops_etnf.py` reads the
second against the code, which is why the numbers above are cited from here.
