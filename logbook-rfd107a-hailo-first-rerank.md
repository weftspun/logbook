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

## RETRACTED 2026-08-24: the render table above is a depth pass, not the corpus render

The section below stands as written because knowing which road was taken is worth more than a
tidy document. Two of its claims are withdrawn.

**"The whole corpus renders in an afternoon" and "the renderer is not the expensive thing" are
wrong by 447x.** The film measured was `mi_bench2.py`'s: an `aov` integrator over position and
depth, a box filter, one sample per pixel. `render_view.py:134-153` renders the corpus with a
`path` integrator at max_depth 6, a **gaussian** filter and **128** samples, and then runs a
second path-traced pass for the matte. Same variant, same geometry, the two films:

| film     | integrator     | filter   | spp | `llvm_ad_rgb` 1 thread | 800k                  |
| -------- | -------------- | -------- | --- | ---------------------- | --------------------- |
| bench    | aov pos/depth  | box      | 1   | 73.00 ms               | overnight             |
| shipping | path max_dep 6 | gaussian | 128 | **32,592.00 ms**       | a month of wall-clock |

**The determinism control was blind, and it was never about samples per pixel.** It was the
film. `bench` cannot drift for three independent reasons: an aov position/depth is deterministic
geometry with no Monte Carlo noise, a box filter puts every sample in exactly one pixel so
nothing splats across a thread's block boundary, and one sample has no accumulation order to
vary. The `identical` column was true and worthless — PITFALLS 4, the convenient proxy lies, and
it is always the one that is easy to read. On the shipping film it fires:

    llvm_ad_rgb, default threads, shipping    4,363.90 ms   DIFFERS
    metal_ad_rgb, default threads, shipping     545.00 ms   DIFFERS

**Metal is 60x and still not a corpus renderer.** The obvious objection was that
`mi.render()` was called without a seed while `render_view.py:155` passes `seed=0`. Pinned at 0,
three runs produced **three different sha256 digests**, so the divergence is GPU accumulation
order rather than a seed artefact. A renderer that cannot reproduce a frame is not a corpus
renderer, whatever it costs.

## And every macOS measurement here was CPU-only because a list said so

Two sites, found independently, the same shape:

    render_view.py:110        ("llvm_ad_rgb", "cuda_ad_rgb", "scalar_rgb")   -- no metal_ad_rgb
    gate_onnx_device.py:156   providers=["CPUExecutionProvider"]             -- no CoreML

`logbook-edge-npu-and-the-anny-forward.md` opens "macOS, no accelerator" and reports the backbone
at 1399.3 ms. That is not a property of this machine; it is a property of line 156. **A hardcoded
backend list turns a capability question into a tautology.**

Both lists now offer their Mac entries, and the answers are not the ones expected.

**CoreML is slower and outside tolerance.** At 576 with `num_windows=1`:

    CPUExecutionProvider       476.4 ms    max|diff| 4.470e-06     1.00x
    CoreMLExecutionProvider   1685.1 ms    max|diff| 4.924e-03     0.28x

Nearly four times slower, and past the port's own 4.2e-03 bound, so it fails the gate on
accuracy as well as losing on speed. `get_providers()` reports what was registered rather than
what ran — CoreML partitions a graph and hands unsupported nodes back to the CPU — which is the
likely mechanism.

**The reason is measurable and it unifies both results.** `scripts/gpu_tops.py`, dense GEMM at
2n³ flops, synchronised, best-of-8:

    mps fp32   5.71 TFLOP/s    84.0% of the 6.8 derived peak
    mps fp16   6.20 TFLOP/s    only 1.09x fp32, not the 2x a half pipeline implies
    mps bf16   2.96 TFLOP/s    0.48x fp16 and BELOW fp32
    cpu fp32   2.19 TFLOP/s

This GPU is worth **2.6x its own CPU** on the friendliest shape a device sees. With that little
headroom, a partitioned graph shuttling tensors across the boundary loses, which is what CoreML
did. The bf16 row confirms `bf16Native = 0` by measurement rather than assertion.

**None of this makes the old hardcoded list correct.** It made a capability claim nobody had
tested and happened to pick the right backend for the wrong reason. The next model or the next
runtime version moves that answer and nothing would have noticed.

The derived peak survives its own test at 84%, so the Devices table's ranking stands. GEMM is an
upper bound, so read it as one.

## The shipping variant, timed

ANNY's face count, 1024², one sample per pixel — `mi_bench2.py`'s film, unchanged, because that
entry's own lesson is that all of its controls ran at one scale and were wrong elsewhere.

| configuration                   | ms/image | 800k projection       |
| ------------------------------- | -------- | --------------------- |
| `llvm_ad_rgb`, 1 thread         | 73.00    | overnight             |
| `llvm_ad_rgb`, 1 thread, 8 proc | 77.88    | **an afternoon**      |
| `llvm_ad_rgb`, default threads  | 11.79    | an afternoon          |
| `metal_ad_rgb`, default threads | 8.86     | an afternoon          |
| `cuda_ad_rgb` (4090, UNPLUGGED) | 1.79     | half an hour          |
| torch `soft_depth` (baseline)   | 3451.00  | a month of wall-clock |

**Two kinds of number, treated differently.** ms/image is a record — an instrument reading —
and keeps its decimals in SI. The 800k column is that reading multiplied by a corpus nobody has
rendered yet, and a decimal there invites a confidence the multiplication does not carry, so it
gets a span. This is CLAUDE.md's household-object rule pointed the other way: a penny is
attached to 4.3 mm because the millimetres alone do not say whether the error matters; a span
replaces the hours because the hours alone say more than is known.

Three rows land on "an afternoon" and are not thereby equal — they are indistinguishable at the
resolution a plan can act on, and the ms/image column is where the difference lives.

Determinism is **per-image**, not per-run. One thread makes one frame byte-identical and says
nothing about how many frames are in flight, so eight single-threaded processes reach an
afternoon without touching the guarantee. Twelve get no further span at 8.83x, which is where
the four efficiency cores stop paying.

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

## The rerank: 20.0 size points, and 38% of it is one task

Computed by `check_rfd107a_plan.py` from the sizes in the stage, by RFD 204d's formulas, and
asserted against RFD 107a's own text so the two cannot drift.

**Sizes rather than days, and the swap is an admission.** The first pass at this entry carried
optimistic, likely and pessimistic figures in engineering days and reported "38.8 engineering
days". Not one of those was measured — they were judgement, and a decimal point made them read
as something else. A t-shirt size cannot be mistaken for a calendar, which is the whole reason
to use one. The spread is kept, because it carried a real signal: T08's pessimistic sits four
times its optimistic, and that is a different fact from T08 merely being large. Points are
Fibonacci and relative — they order tasks against each other and convert to no duration at all.

**The chain is the same six tasks the unit-duration reading named.** That is the least
interesting thing about it. What moves is the weight:

- **T02 is back on the critical path**, resized from `S/M/L` to `M/L/XL`. The first rerank
  demoted the renderer on the strength of a depth pass; correcting that promotes it and takes
  `T04 → T05` off the path, each gaining 1.7 slack.
- **T08 masked training is 7.5 points, 38% of the path.** Still the single heaviest, and no
  resequencing touches it.
- **T06 gains slack rather than losing it**: 7.3, over seven times its own size, and it is the
  one outstanding task that runs on any desk in the fleet.

**The bottleneck is a device, and the graph cannot express it.** T05, T07 and T08 are all
`gpuBound` and all want the one plugged-in bf16 card, because condition 5 forbids the quantised
alternative for anything writing corpus data. Their expected sizes sum to **13.0 of the 18.3
points — 65% of the path — on a single RTX 3090**, a serial floor that no dependency edge
describes.

So the largest lever is not a resequencing. Plugging in the 4090 brings the path to **11.9
points, cutting 30% off it**, by scaling the `gpuBound` tasks on derived peak rate. That is a ranking
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
