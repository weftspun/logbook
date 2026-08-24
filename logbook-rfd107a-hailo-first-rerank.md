# Logbook: what the plan costs once the durations are real, and the card is a 3090

Apparatus: `scripts/mi_bench_llvm.py` for the render timings, `scripts/check_rfd107a_plan.py`
for the reranked path, and `6-datasource/anny-render-corpus/pixi.toml` for the environment that
had to exist first. Every render figure is the Mac mini — Apple M2 Pro, 12 cores, 32 GiB,
macOS 26.5.2 build 25F84, read from osquery's `system_info` rather than scraped from `sysctl`.
Nothing here was measured on the 3090 or the 4090.

Question: RFD 107a ranks its ten tasks on unit durations and says that assumption decides the
answer. What does the answer become when the durations are priced and the Hailo part goes
first?

## The figure the plan rested on was measured on a card that is unplugged

`logbook-soft-renderer-and-mitsuba.md` reports Mitsuba at 1.79 ms/image and projects 0.4
GPU-hours over 800k. Both benchmarks behind it open the same way:

    mi_bench.py:19    mi.set_variant('cuda_ad_rgb')
    mi_bench2.py:20   mi.set_variant('cuda_ad_rgb')

`render_view.py:237` defaults to `llvm_ad_rgb` at `--threads 1`, because that is the pair the
determinism measurement pinned. So the corpus is costed by a variant that is not reproducible,
on hardware no longer in the fleet, and rendered by a variant nobody had ever timed.

**Retracted as a corpus-render estimate.** It remains correct about what it measured.

## The shipping variant, timed

ANNY's face count, 1024², one sample per pixel — `mi_bench2.py`'s film, unchanged, because that
entry's own lesson is that all of its controls ran at one scale and were wrong elsewhere.

| configuration                   | ms/image | 800k projection      |
| ------------------------------- | -------- | -------------------- |
| `llvm_ad_rgb`, 1 thread         | 73.0     | 16.2 h, two shifts   |
| `llvm_ad_rgb`, 1 thread, 8 proc | 77.9     | **2.2 h, one lunch** |
| `llvm_ad_rgb`, default threads  | 11.8     | 2.6 h                |
| `metal_ad_rgb`, default threads | 8.9      | 2.0 h                |
| `cuda_ad_rgb` (4090, UNPLUGGED) | 1.79     | 0.4 h                |
| torch `soft_depth` (baseline)   | 3451     | 766.9 h              |

Determinism is **per-image**, not per-run. One thread makes one frame byte-identical and says
nothing about how many frames are in flight, so eight single-threaded processes reach 2.2 hours
without touching the guarantee. Twelve reach 1.9 hours at 8.92x, which is where the four
efficiency cores stop paying.

The whole corpus renders in an afternoon on the weakest device in the fleet. That settles what
the ordering turned on: the renderer is not the expensive thing, and never was.

## A faster answer that is deliberately not taken

Multithreaded `llvm_ad_rgb` is 6.2x faster than the shipping pair, and `metal_ad_rgb` — a
variant Mitsuba 3.9.1 enumerates on Apple silicon and which appears in no document here — is
8.2x. Both came back byte-identical across two fresh processes.

`pixi.toml` records the multithreaded case drifting by up to 1/255 on a dozen pixels of
1,048,576. Two readings of one configuration, so one is measuring the wrong thing.

The named mechanism is film accumulation order, which needs more than one sample per pixel to
have an order at all. So the control went looking at 1, 4, 16 and 64:

    spp   1      11.80 ms/img   identical
    spp   4      25.03 ms/img   identical
    spp  16      79.38 ms/img   identical
    spp  64     294.10 ms/img   identical

**The control did not fire, and that is the result.** Nothing has shown this check can fail, so
its `identical` column is decoration rather than evidence — PITFALLS 2, a check that never
fails certifies whatever it is pointed at. Two readings survive and this run does not separate
them: the recorded drift may be win-64/linux-64 only and unmeasured on osx-arm64, or this
instrument may be blind to it.

So the one-thread rule stands, and it costs nothing. The process-scaling row reaches the same
throughput with every frame single-threaded, which is the configuration the determinism
measurement actually covers. A 6x speed-up declined on a check that cannot fail is cheaper than
a corpus that has to be re-rendered.

## The environment did not exist on this platform

`pixi.toml` declared `platforms = ["win-64", "linux-64"]` and `pixi.lock` held **zero**
`osx-arm64` entries, so no declared environment could be instantiated on the Mac at all. Two
things were needed and both are now in the manifest rather than in somebody's shell:

- `osx-arm64` on the render and `corpus` features only. The three CUDA-wheel features restate
  `["win-64", "linux-64"]`, so the manifest says which desk holds which work and `pixi install`
  fails at the solver instead of after a model download.
- `libllvm20`, and `DRJIT_LIBLLVM_PATH` through `[target.osx-arm64.activation.env]`. Dr.Jit
  finds its own LLVM on Windows and Linux and not here, and stock macOS ships no linkable
  `libLLVM.dylib` — Xcode has none at a usable path and Homebrew was absent. Without it the
  shipping variant does not load:

      ImportError: jit_init_thread_state(): the LLVM backend is inactive because the LLVM
      shared library ("libLLVM.dylib") could not be found!

## Hailo-first reaches backwards into the training run

RFD 107e already decided the backbone compiles at `num_windows=1` — 825 ONNX nodes parse
against 868 rejected — and that it "costs 1.35x wall-clock and **needs retraining**".

T09 converts and ports, and it sits _after_ T08 trains. A plan followed in its own numbered
order therefore trains at the windowing the detector was written with, finds out at T09 that
the compiler refuses it, and pays for the training run twice. Nothing in the graph says
otherwise, because the constraint belongs to the compiler and the graph only knows tasks.

Recorded as a standing constraint, `EdgeCompileGatesTraining`, rather than a new edge. An edge
from T09 back into T08 is a cycle and is checked for; splitting a new task out ahead of T08
would say the schedule is waiting on work, and it is not — 107e's decision is made and the
compile is measured. What is owed is that T08 honours it.

One quantization schedule comes out of DFC 5.3.0 and the rest of the fleet runs that same
schedule. A detector quantised three ways is three detectors, and a number measured on one desk
stops transferring to the next.

**Not condition 5.** That forbids a quantised _generator_ from writing corpus data. The
detector's quantization is deployment — it reads frames somebody else rendered and emits
keypoints, and nothing it produces enters a corpus. Only T05's generator path is bound.

## The rerank: 38.8 engineering days, and 44% of it is one task

Computed by `check_rfd107a_plan.py` from the durations in the stage, by RFD 204d's formulas,
and asserted against RFD 107a's own text so the two cannot drift.

**The chain is the same six tasks the unit-duration reading named.** That is the least
interesting thing about it. What moves is the weight:

- **T08 masked training is 17.2 days, 44% of the path.** One task is nearly half the project
  and no resequencing touches it.
- **T02 keeps its position and loses its cushion** — slack falls from a full layer to 0.2 days.
  The renderer is co-critical rather than comfortable, despite the render itself being an
  afternoon.
- **T06 gains slack rather than losing it**: 11.2 days, and it is the one outstanding task that
  runs on any desk in the fleet.

**The bottleneck is a device, and the graph cannot express it.** T05, T07 and T08 are all
`gpuBound` and all want the one plugged-in bf16 card, because condition 5 forbids the quantised
alternative for anything writing corpus data. Their expected durations sum to **28.2 days on a
single RTX 3090** — a serial floor that no dependency edge describes.

So the largest lever is not a resequencing. Plugging in the 4090 brings the path to **25.2
days, saving 13.6**, by scaling the `gpuBound` tasks on derived peak rate. That is a ranking
and not a budget, in the sense `logbook-edge-npu-and-the-anny-forward.md` set: it assumes those
tasks are compute-bound and perfectly portable, and neither was measured. It still costs a
cable.

## Peak rates, derived rather than quoted

`cores x lanes x 2 for the fused multiply-add x clock`, re-derived by the checker so a
transcription error fails a command:

| device      | derivation               | FP32    | memory | bf16   |
| ----------- | ------------------------ | ------- | ------ | ------ |
| 3090 (live) | 82 x 128 x 2 x 1.695 GHz | 35.6 TF | 24 GiB | native |
| 4090 (off)  | 128 x 128 x 2 x 2.52 GHz | 82.6 TF | 24 GiB | native |
| M2 Pro      | 19 x 128 x 2 x 1.398 GHz | 6.8 TF  | 32 GiB | **no** |
| Hailo-10H   | published, 40 TOPS INT4  | —       | 8 GiB  | n/a    |

All three clocks are vendor boost figures. **None was read off a desk**, and the checker counts
them as ASSUMED rather than letting the table read as measured. The Hailo row divides by 40
TOPS INT4 at an ASSUMED 30% utilisation, which is the convention the edge-NPU entry set and
also flagged: the DFC profiler was never run.

The M2 Pro has the largest memory pool in the fleet and the smallest compute, and no native
bf16 — so running a generator at published precision there is emulation, which is a correctness
question before a speed one and is unmeasured either way.

## Still open

- Nothing was measured on the 3090. Every GPU duration above is an estimate scaled from a 4090
  figure by derived peak rate, and the 2.3x that scaling rests on is arithmetic, not a run.
- `metal_ad_rgb` is 8.2x the shipping variant and has no determinism evidence that survives its
  own control. A firing control would make it the corpus renderer.
- `feature.anny` still has no osx-arm64 offering, because its torch comes from `whl/cpu`, an
  index with no Apple silicon wheels. So the render measurement used a face-matched lat-long
  proxy — 27,324 faces against ANNY's 27,420 — rather than a real body. Mitsuba's per-frame cost
  counts faces rather than which body they describe, but that is an argument and not a
  measurement, and a mac-scoped feature taking torch from PyPI would settle it.
