# Apparatus

The scripts behind the logbook entries. Each one is kept so a number can be re-run rather than
believed, which is the whole reason an entry clips its apparatus.

| script               | entry                     | what it measures                                                  |
| -------------------- | ------------------------- | ----------------------------------------------------------------- |
| `cfhd_probe.py`      | cineform-movie-writer     | what CineForm costs a depth map, in millimetres, at 10 and 12 bit |
| `bench1024.py`       | soft-renderer-and-mitsuba | the soft renderer at 256, 512 and 1024, with peak memory          |
| `bench_cull.py`      | soft-renderer-and-mitsuba | the bounding-box cull against the unculled reference              |
| `sweep.py`           | soft-renderer-and-mitsuba | block size against work and wall time                             |
| `mi_bench.py`        | soft-renderer-and-mitsuba | first Mitsuba pass, and the three ways it flattered itself        |
| `mi_bench2.py`       | soft-renderer-and-mitsuba | Mitsuba against an exact z-buffer, with Dr.Jit actually synced    |
| `samples.py`         | soft-renderer-and-mitsuba | ANNY depth and silhouette renders, written to disk for inspection |
| `keypoint_render.py` | soft-renderer-and-mitsuba | 104 keypoints coloured by See-Through layer in OKHSL              |

These import from `3-interactor/pose-consensus/python` and expect `anny` installed. They were
run against a local 4090 and name that in their output, because a timing without the machine
is not a measurement.
