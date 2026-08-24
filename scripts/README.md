# Apparatus

The scripts behind the logbook entries. Each one is kept so a number can be re-run rather than
believed, which is the whole reason an entry clips its apparatus.

| script               | entry                      | what it measures                                                             |
| -------------------- | -------------------------- | ---------------------------------------------------------------------------- |
| `cfhd_probe.py`      | cineform-movie-writer      | what CineForm costs a depth map, in millimetres, at 10 and 12 bit            |
| `bench1024.py`       | soft-renderer-and-mitsuba  | the soft renderer at 256, 512 and 1024, with peak memory                     |
| `bench_cull.py`      | soft-renderer-and-mitsuba  | the bounding-box cull against the unculled reference                         |
| `sweep.py`           | soft-renderer-and-mitsuba  | block size against work and wall time                                        |
| `mi_bench.py`        | soft-renderer-and-mitsuba  | first Mitsuba pass, and the three ways it flattered itself                   |
| `mi_bench2.py`       | soft-renderer-and-mitsuba  | Mitsuba against an exact z-buffer, with Dr.Jit actually synced               |
| `samples.py`         | soft-renderer-and-mitsuba  | ANNY depth and silhouette renders, written to disk for inspection            |
| `mi_bench_llvm.py`   | rfd107a-hailo-first-rerank | the SHIPPING render variant, `llvm_ad_rgb` at one thread, never before timed |
| `gpu_tops.py`        | rfd107a-hailo-first-rerank | measured GEMM throughput against the derived peak, fp32/fp16/bf16 and CPU    |
| `keypoint_render.py` | soft-renderer-and-mitsuba  | 104 keypoints coloured by See-Through layer in OKHSL                         |

These import from `3-interactor/pose-consensus/python` and expect `anny` installed.

A timing without the machine is not a measurement, and the desks do not agree: at least a 3090
and a 4090 are in use, 24 GB each and not the same throughput. So this file names no GPU, and
a timing that reaches an entry has to carry the machine it was measured on rather than inherit
one from here.

**The scripts do not all do that yet.** `samples.py` prints its device through
`torch.cuda.get_device_name(0)` and `mi_bench_llvm.py` prints its chip and core count through
`sysctl`; the other seven report timings with nothing identifying what produced them. That is a gap rather than a convention, and it is written down here because the
previous wording claimed the opposite and no run would have contradicted it.
