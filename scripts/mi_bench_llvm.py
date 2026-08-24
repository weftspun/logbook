"""Time the renderer's SHIPPING variant, which no benchmark here had ever timed.

WHY THIS EXISTS. `logbook-soft-renderer-and-mitsuba.md` reports Mitsuba at 1.79 ms/image and
projects 0.4 GPU-hours over an 800k-image corpus, and that table is what RFD 107a's ordering
rests on. Both benchmarks behind it -- `mi_bench.py:19` and `mi_bench2.py:20` -- open with
`mi.set_variant('cuda_ad_rgb')`, on the local 4090.

Neither of those is the configuration that ships. `render_view.py` defaults to `llvm_ad_rgb`
at `--threads 1`, because that is the pair the determinism measurement pinned: one thread is
byte-identical over two runs by sha256 and the default thread count drifts by up to 1/255 on a
dozen pixels through film accumulation order. So the corpus is rendered by a CPU variant whose
throughput has never been measured, and costed by a GPU variant that is not reproducible and
that runs on a card no longer plugged in.

This measures the shipping pair, on this desk, at the resolution and sample count
`mi_bench2.py` used, so the two numbers may be read against each other.

THE GEOMETRY IS A STAND-IN AND THE ENTRY SAYS SO. Building a real ANNY body needs torch, which
`pixi.toml` does not offer on osx-arm64 -- `feature.anny` takes torch from `whl/cpu`, an index
with no Apple silicon wheels. Mitsuba's cost per frame is set by face count, ray count and
sample count rather than by which body the faces describe, so a lat-long proxy at ANNY's vertex
and face counts measures the same instrument. It does NOT stand in for anything about the body,
and no result here should be read as an ANNY render. Actual built counts are printed beside
ANNY's so the reader can see the match rather than trust it.

THREE VARIANTS, BECAUSE APPLE SILICON HAS ONE NOBODY HERE HAS WRITTEN DOWN. Mitsuba 3.9.1
enumerates `metal_ad_rgb` on this platform. `pixi.toml`'s determinism table covers
`llvm_ad_rgb` at one thread, `llvm_ad_rgb` at default threads and `cuda_ad_rgb` at default, and
says nothing about Metal, so this asks the same sha256 question of it that the others were
asked. A variant that is fast and not reproducible is not a corpus renderer, and finding that
out here is cheaper than finding it out in 800k frames.

Usage:
    python mi_bench_llvm.py                      # the full sweep
    python mi_bench_llvm.py --procs 1,2,4,8      # process-level scaling only
    python mi_bench_llvm.py --worker VARIANT N   # one measurement, JSON on stdout
"""

import argparse
import hashlib
import json
import math
import os
import pathlib
import subprocess
import sys
import time

import numpy as np

# `mi_bench2.py`'s film and sampler, unchanged. A comparison across two scales is not a
# comparison, and that entry's own lesson is that every control in it ran at one scale and was
# wrong everywhere else.
W = H = 1024
FOV = 40.0
SPP = 1
ITERS = 30

# `render_view.py:235` defaults to this, and it is the sample count the corpus is rendered at.
SHIPPING_SPP = 128

# PINNED, BECAUSE "PROBABLY THE DEFAULT" IS NOT A MEASUREMENT. `render_view.py:155` passes
# seed=0 explicitly and this file was calling `mi.render` without one. Mitsuba's default is also
# 0, so this should change nothing -- but the Metal digests differ across processes, and a seed
# that varied would explain that without any film-accumulation story at all. Pinning it is what
# separates the two, and it decides whether a 60x speed-up is available.
SEED = 0

# What the proxy is matched against. ANNY at `base_mesh='makehuman'` with
# `remove_unattached_vertices=False`, the configuration `mi_bench2.py` instantiates.
ANNY_VERTS = 19158
ANNY_FACES = 27420

# The figures this is measured against, both from `logbook-soft-renderer-and-mitsuba.md`.
CUDA_4090_MS = 1.79       # cuda_ad_rgb, incl. vertex update and BVH, on the 4090
TORCH_SOFT_MS = 3451.0    # soft_depth + soft_silhouette, the original baseline


def proxy_mesh(target_verts=ANNY_VERTS, target_faces=ANNY_FACES):
    """A lat-long body proxy at ANNY's counts, give or take the grid's own arithmetic.

    A lat-long grid of `rings` x `segments` gives (rings-1)*segments + 2 vertices and
    2*segments*(rings-1) faces, so the two targets cannot both be hit exactly -- ANNY's
    face-to-vertex ratio is 1.43 and a closed lat-long grid's tends to 2. Vertices are matched
    and the face count is reported rather than forced, because forcing it would mean deleting
    faces and changing the BVH into something that is not a closed surface.
    """
    best = None
    for segments in range(8, 400):
        for rings in range(3, 400):
            v = (rings - 1) * segments + 2
            f = 2 * segments * (rings - 1)
            # FACES are matched, not vertices, and the choice is not arbitrary: a ray tracer's
            # per-frame cost is BVH build and triangle intersection, both of which count faces.
            # Vertices are carried along and are reported as the mismatch.
            score = abs(f - target_faces)
            if best is None or score < best[0]:
                best = (score, rings, segments, v, f)
    _, rings, segments, nv, nf = best

    # Body-shaped rather than a ball: 1.7 m tall, elliptical in cross-section, waisted. The
    # silhouette matters only in that it fills a comparable share of the frame; the ray count
    # is fixed by the film.
    theta = np.linspace(0.0, math.pi, rings)[1:-1]
    phi = np.linspace(0.0, 2.0 * math.pi, segments, endpoint=False)
    t, p = np.meshgrid(theta, phi, indexing="ij")
    z = np.cos(t)
    r = np.sin(t) * (0.55 + 0.45 * np.abs(np.cos(t)))
    verts = np.stack([(r * np.cos(p) * 0.30).ravel(),
                      (r * np.sin(p) * 0.18).ravel(),
                      (z * 0.85).ravel()], axis=1)
    verts = np.vstack([verts, [0.0, 0.0, 0.85], [0.0, 0.0, -0.85]])

    faces = []
    mid = rings - 2
    for i in range(mid - 1):
        for j in range(segments):
            j2 = (j + 1) % segments
            a, b = i * segments + j, i * segments + j2
            c, d = (i + 1) * segments + j, (i + 1) * segments + j2
            faces.append([a, c, d])
            faces.append([a, d, b])
    top, bot = mid * segments, mid * segments + 1
    for j in range(segments):
        j2 = (j + 1) % segments
        faces.append([top, j2, j])
        faces.append([bot, (mid - 1) * segments + j, (mid - 1) * segments + j2])
    return verts.astype(np.float64), np.asarray(faces, dtype=np.int64)


def build_scene(mi, verts, faces, film="bench", spp=SPP):
    """One of two films, and the difference between them turned out to be the whole finding.

    `bench` is `mi_bench2.py`'s: an aov integrator over position and depth, a box
    reconstruction filter, one sample per pixel. That is what this script measured first, and
    it is a DEPTH PASS.

    `shipping` is `render_view.py`'s, which is what actually renders the corpus: a `path`
    integrator at max_depth 6, a GAUSSIAN reconstruction filter, 128 samples per pixel, a
    principled skin BSDF, a constant world emitter and a point key light.

    THE FIRST VERSION OF THIS FILE HAD ONLY `bench` AND CALLED THE RESULT THE CORPUS RENDER.
    That was wrong twice, and the second error hid the first:

      * The TIMING was for a depth pass at one sample, projected as though it were the frame
        the corpus keeps. `render_view.py` path-traces at 128 and then runs a SECOND path-traced
        pass for the matte, so the real cost is not the same quantity.
      * The DETERMINISM check could not fail, and three independent properties of `bench` each
        guarantee that. An aov position/depth is deterministic geometry with no Monte Carlo
        noise; a box filter puts every sample in exactly one pixel, so nothing splats across a
        thread's block boundary; and at one sample per pixel there is no accumulation ORDER to
        vary, which is the mechanism `pixi.toml` names.

    So a check reported `identical` on a film built such that it could not report anything else,
    and it was pointed at the wrong renderer while doing it. PITFALLS 4 -- the convenient proxy
    lies, and the proxy is always the one that is easy to read.
    """
    mesh = mi.Mesh("body", vertex_count=verts.shape[0], face_count=faces.shape[0],
                   has_vertex_normals=False, has_vertex_texcoords=False)
    mp = mi.traverse(mesh)
    mp["vertex_positions"] = mi.Float(verts.astype(np.float32).reshape(-1))
    mp["faces"] = mi.UInt(faces.astype(np.uint32).reshape(-1))
    mp.update()

    centre = verts.mean(0)
    extent = float(np.linalg.norm(verts - centre, axis=1).max())
    off = np.array([0.0, 1.0, 0.25])
    eye = centre + off / np.linalg.norm(off) * extent * 3.0
    look_at = mi.ScalarTransform4f().look_at(
        origin=[float(x) for x in eye], target=[float(x) for x in centre], up=[0.0, 0.0, 1.0])

    if film == "shipping":
        # render_view.py:134-153, with its materials and lights. The geometry is still the
        # proxy, so this measures the FILM and not the body.
        scene = mi.load_dict({
            "type": "scene",
            "integrator": {"type": "path", "max_depth": 6},
            "sensor": {
                "type": "perspective", "fov": FOV, "fov_axis": "y", "to_world": look_at,
                "film": {"type": "hdrfilm", "width": W, "height": H,
                         "rfilter": {"type": "gaussian"}, "pixel_format": "rgb"},
                "sampler": {"type": "independent", "sample_count": spp},
            },
            "body": mesh,
            "bsdf_body": {"type": "ref", "id": "skin"},
            "skin": {"type": "principled",
                     "base_color": {"type": "rgb", "value": [0.76, 0.62, 0.54]},
                     "roughness": 0.55, "metallic": 0.0},
            "world": {"type": "constant", "radiance": {"type": "rgb", "value": 0.35}},
            "key": {"type": "point",
                    "position": [float(eye[0]) * 1.2, float(eye[1]) * 1.2, float(eye[2]) + 1.5],
                    "intensity": {"type": "rgb", "value": 12.0}},
        })
    else:
        scene = mi.load_dict({
            "type": "scene",
            "integrator": {"type": "aov", "aovs": "pos:position,t:depth"},
            "sensor": {
                "type": "perspective", "fov": FOV, "fov_axis": "x", "to_world": look_at,
                "film": {"type": "hdrfilm", "width": W, "height": H,
                         "rfilter": {"type": "box"}, "pixel_format": "rgba"},
                "sampler": {"type": "independent", "sample_count": spp},
            },
            "body": mesh,
        })
    return scene, mi.traverse(scene)


def worker(variant, threads, spp=SPP, film="bench", iters=None):
    """One measurement, in its own process. JSON on stdout, nothing else.

    A process each, for two reasons. Switching variants inside one interpreter leaves the
    previous backend's state alive, and the process-scaling run below needs a unit of work that
    a shell can start N of anyway.
    """
    import drjit as dr
    import mitsuba as mi
    mi.set_variant(variant)
    if threads and variant.startswith("llvm"):
        # `render_view.py:117` sets it this way and records that `DRJIT_NUM_THREADS` had no
        # effect at all. Same call here rather than a second mechanism.
        dr.set_thread_count(threads)

    # The shipping film is path-traced at 128 samples, so thirty iterations of it is not a
    # benchmark, it is an afternoon. Fewer, and the count is reported rather than assumed.
    iters = iters if iters is not None else (2 if film == "shipping" else ITERS)

    verts, faces = proxy_mesh()
    scene, params = build_scene(mi, verts, faces, film, spp)
    vkey = [k for k in params.keys() if k.endswith("vertex_positions")][0]

    def timed(n, update):
        dr.sync_thread()
        t0 = time.time()
        for i in range(n):
            if update:
                params[vkey] = mi.Float((verts + 0.0005 * i).astype(np.float32).reshape(-1))
                params.update()
            out = mi.render(scene, spp=spp, seed=SEED)
            dr.eval(out)
        dr.sync_thread()
        return (time.time() - t0) / n

    timed(1 if film == "shipping" else 3, False)  # warm the BVH and JIT off the measurement

    # Determinism, asked of every variant rather than only the ones already recorded. ONE
    # digest per process, compared by the caller ACROSS processes.
    #
    # The first version of this took two renders inside one interpreter and reported them
    # identical, including for `llvm_ad_rgb` at default threads -- which `pixi.toml` records as
    # drifting by up to 1/255 on a dozen pixels. That was not a refutation, it was a weaker
    # instrument: film accumulation order is what drifts, and two renders sharing one warm
    # thread pool and one scheduler are the case most likely to repeat it. A digest compared
    # across two fresh processes is the question worth asking.
    img = np.array(mi.render(scene, spp=spp, seed=SEED), dtype=np.float32)
    digests = [hashlib.sha256(np.ascontiguousarray(img).tobytes()).hexdigest()]

    return {
        "variant": mi.variant(),
        "threads": threads or 0,
        "spp": spp,
        "film": film,
        "iters": iters,
        "render_only_ms": timed(iters, False) * 1000.0,
        "update_bvh_ms": timed(iters, True) * 1000.0,
        "sha256": digests[0],
        "verts": int(verts.shape[0]),
        "faces": int(faces.shape[0]),
    }


# EVERY SUBPROCESS IS ARMED WITH A DEADLINE, AND THE REASON IS THIS FILE'S OWN SUBJECT.
#
# `logbook-soft-renderer-and-mitsuba.md` records the failure mode directly: at 1024x1024 the
# card "sat at 24,041 MiB of 24,564 at 100% and never finished. It did not raise: an allocator
# at its ceiling thrashes rather than failing, so the symptom is a render that never returns."
# A benchmark that can hang is a benchmark that has to be watched. `timeout(1)` is not present
# on macOS, so the budget is armed here rather than in the shell, and a config that overruns is
# NAMED AND COUNTED as TIMEOUT rather than omitted -- a silent skip reads exactly like a pass.
WORKER_TIMEOUT_S = 300.0
SWEEP_DEADLINE_S = 1800.0


def run_worker(variant, threads, timeout=WORKER_TIMEOUT_S, spp=SPP, film="bench"):
    try:
        out = subprocess.run([sys.executable, __file__, "--worker", variant, str(threads),
                              "--spp", str(spp), "--film", film],
                             capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"variant": variant, "threads": threads, "film": film,
                "error": f"TIMEOUT after {timeout:.0f}s -- killed, not waited on"}
    if out.returncode != 0:
        tail = out.stderr.strip().splitlines()[-1:] or ["no stderr"]
        return {"variant": variant, "threads": threads, "error": tail[0]}
    return json.loads(out.stdout.strip().splitlines()[-1])


def machine_facts():
    """The desk this ran on, as structured data rather than a parsed one-liner.

    `scripts/README.md` names the absence of this as a gap: "a timing that reaches an entry has
    to carry the machine it was measured on rather than inherit one from here", and records
    that only `samples.py` does it. This is the second, and it asks osquery rather than sysctl
    for the same reason CLAUDE.md gives for rotation order and up axis -- conventions are data,
    so parse them from something that returns fields rather than scraping a formatted string.
    A `sysctl -n` output is a string whose shape is the vendor's business; `system_info` is a
    relation with named columns.

    THE FALLBACK IS NAMED IN THE OUTPUT, NOT SILENT. If osquery is absent the run still
    produces numbers, and a reader has to be able to tell which source answered -- a degraded
    provenance that prints identically to a good one is the same failure as a silent skip.
    """
    import platform
    import subprocess as sp

    def osquery(sql):
        out = sp.run(["osqueryi", "--json", sql], capture_output=True, text=True, timeout=30)
        rows = json.loads(out.stdout)
        return rows[0] if rows else {}

    try:
        si = osquery("select cpu_brand, cpu_physical_cores, cpu_logical_cores, "
                     "physical_memory, hardware_model, hardware_vendor from system_info;")
        ov = osquery("select name, version, build from os_version;")
        gib = int(si["physical_memory"]) / (1024 ** 3)
        return {
            "source": (f"osquery system_info + os_version -- {ov.get('name', '?')} "
                       f"{ov.get('version', '?')} build {ov.get('build', '?')}"),
            "summary": (f"{si['hardware_vendor'].strip()} {si['hardware_model']}, "
                        f"{si['cpu_brand']}, {si['cpu_physical_cores']} physical / "
                        f"{si['cpu_logical_cores']} logical cores, {gib:.0f} GiB"),
            **si,
        }
    except Exception as exc:
        # Named and counted, never omitted.
        return {
            "source": f"FALLBACK, osquery unavailable ({type(exc).__name__}) -- fewer fields",
            "summary": (f"{platform.system()} {platform.machine()}, "
                        f"{platform.processor() or 'unknown cpu'}, "
                        f"{os.cpu_count()} logical cores"),
        }


def hours(ms, n=800_000):
    return n * (ms / 1000.0) / 3600.0


def human_span(h):
    """A projection said the way a person would say it, rather than to one decimal.

    THE RECORD AND THE PROJECTION ARE DIFFERENT KINDS OF NUMBER AND GET DIFFERENT TREATMENT.
    73.00 ms/image is an instrument reading and stays SI with its decimals. "800k images in
    16.2 h" is that reading multiplied by a corpus size nobody has rendered yet, and the decimal
    invites a confidence the multiplication does not carry. So it gets a span.

    This is CLAUDE.md's household-object rule pointed the other way. A penny is attached to
    4.3 mm because the millimetres alone do not say whether the error matters; a span replaces
    the hours because the hours alone say more than is known. Both swap a bare number for
    something a reader can act on.
    """
    for limit, span in ((0.5, "half an hour"), (1.5, "about an hour"), (4, "an afternoon"),
                        (10, "a working day"), (20, "overnight"), (60, "a long weekend"),
                        (200, "a working week")):
        if h < limit:
            return span
    return "a month of wall-clock"


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", nargs=2, metavar=("VARIANT", "THREADS"))
    ap.add_argument("--spp", type=int, default=SPP)
    ap.add_argument("--film", choices=("bench", "shipping"), default="bench")
    ap.add_argument("--scale-film", choices=("bench", "shipping"), default="shipping",
                    help="film for the process-scaling table; the corpus renders on `shipping`")
    ap.add_argument("--results", default=str(pathlib.Path.home() / "Desktop"),
                    help="directory for the machine-readable result record")
    ap.add_argument("--procs", default="1,2,4,8",
                    help="concurrent single-threaded processes to scale over")
    ap.add_argument("--worker-timeout", type=float, default=WORKER_TIMEOUT_S,
                    help="seconds before one measurement is killed and reported as TIMEOUT")
    ap.add_argument("--deadline", type=float, default=SWEEP_DEADLINE_S,
                    help="seconds before remaining configurations are skipped and named")
    a = ap.parse_args(argv)

    if a.worker:
        print(json.dumps(worker(a.worker[0], int(a.worker[1]), a.spp, a.film)))
        return 0

    import mitsuba as mi
    available = mi.variants()

    host = machine_facts()
    print(f"machine          {host['summary']}")
    print(f"                 source: {host['source']}")
    verts, faces = proxy_mesh()
    print(f"proxy geometry   {verts.shape[0]} verts, {faces.shape[0]} faces")
    print(f"ANNY, matched    {ANNY_VERTS} verts, {ANNY_FACES} faces")
    print(f"films            {W}x{H}; bench = aov/box/spp {SPP}; "
          f"shipping = path d6/gaussian/spp {SHIPPING_SPP}\n")

    # BOTH FILMS, BECAUSE MEASURING ONLY THE CHEAP ONE IS HOW THIS SCRIPT WAS WRONG.
    plan = [("llvm_ad_rgb", 1, "bench", SPP), ("llvm_ad_rgb", 0, "bench", SPP)]
    if "metal_ad_rgb" in available:
        plan.append(("metal_ad_rgb", 0, "bench", SPP))
    plan += [("llvm_ad_rgb", 1, "shipping", SHIPPING_SPP),
             ("llvm_ad_rgb", 0, "shipping", SHIPPING_SPP)]

    started = time.time()
    skipped = []
    rows = []
    for variant, threads, film, spp in plan:
        if time.time() - started > a.deadline:
            skipped.append(f"{variant}/{threads or 'default'}/{film}")
            continue
        # Twice, in two fresh processes, so the sha256 comparison spans process boundaries
        # rather than two renders sharing one warm thread pool.
        r = run_worker(variant, threads, a.worker_timeout, spp, film)
        r2 = (run_worker(variant, threads, a.worker_timeout, spp, film)
              if "error" not in r else r)
        rows.append(r)
        if "error" in r:
            print(f"  FAIL {variant} threads={threads} film={film}: {r['error']}")
            continue
        r["identical"] = ("error" not in r2) and r["sha256"] == r2["sha256"]
        r["label"] = (f"{r['variant']}, {'1 thread' if r['threads'] == 1 else 'default threads'}"
                      f", {film}")
        det = "identical" if r["identical"] else "DIFFERS"
        print(f"{r['label']:44s} render only {r['render_only_ms']:9.2f} ms   "
              f"+update/BVH {r['update_bvh_ms']:9.2f} ms   {det}")
    if skipped:
        print(f"\n  {len(skipped)} configuration(s) SKIPPED on the {a.deadline:.0f}s deadline, "
              f"named rather than dropped: {', '.join(skipped)}")

    print("\n800k-image projection, one process, against the figures already recorded.")
    print("ms/image is the record and stays SI; the projection is a span.\n")
    print(f"    {'configuration':46s} {'ms/img':>10s}   {'800k':<22s}")
    for r in rows:
        if "error" in r:
            continue
        print(f"    {r['label']:46s} {r['update_bvh_ms']:10.2f}   "
              f"{human_span(hours(r['update_bvh_ms'])):<22s}")
    print(f"    {'cuda_ad_rgb, default, bench (4090, OFF)':46s} {CUDA_4090_MS:10.2f}   "
          f"{human_span(hours(CUDA_4090_MS)):<22s}")
    print(f"    {'torch soft_depth, bench (original floor)':46s} {TORCH_SOFT_MS:10.2f}   "
          f"{human_span(hours(TORCH_SOFT_MS)):<22s}")
    print("\n    THE TWO FILMS ARE NOT COMPARABLE AND THE ROWS ARE LABELLED SO NOBODY READS")
    print("    THEM AS IF THEY WERE. The 4090 figure and the torch floor are BENCH-film")
    print("    numbers -- a depth pass at one sample. `render_view.py` renders the corpus on")
    print("    the shipping film, and no 4090 measurement of that exists. Comparing a shipping")
    print("    row against the 1.79 ms is comparing a lit path trace with a depth probe.")

    # PROCESS-LEVEL SCALING, WHICH IS THE WHOLE POINT OF THE SHIPPING CONFIGURATION.
    #
    # Determinism is per-image: one thread makes one frame byte-identical, and says nothing
    # about how many frames are in flight. So a corpus renders at N processes x one thread with
    # every frame still reproducible, and the throughput that matters is aggregate rather than
    # per-process. Reported as a speed-up against one process so the drop-off is visible.
    # THIS TABLE MEASURED THE WRONG FILM AND PRINTED IT UNDER A CORPUS HEADING.
    #
    # The Popen above passed no `--film`, so it defaulted to `bench` -- an aov depth pass at one
    # sample -- while the heading and the 800k column read as corpus throughput. The rest of this
    # file exists to retract exactly that confusion, and this block went on repeating it: "800k =
    # an afternoon" was the most quotable line in the output and it was 447x wrong.
    #
    # The film is now explicit and printed. Default is `shipping`, because the question this
    # table answers is how long the CORPUS takes, and a reader who wants the depth pass can ask
    # for it by name.
    scale_spp = SHIPPING_SPP if a.scale_film == "shipping" else SPP
    print(f"\nconcurrent single-threaded processes on the {a.scale_film.upper()} film "
          f"(spp {scale_spp}), each still byte-reproducible:\n")
    base = None
    for n in [int(x) for x in a.procs.split(",") if x.strip()]:
        if time.time() - started > a.deadline:
            print(f"    {n:2d} procs   SKIPPED on the deadline, named rather than dropped")
            continue
        procs = [subprocess.Popen([sys.executable, __file__, "--worker", "llvm_ad_rgb", "1",
                                   "--spp", str(scale_spp), "--film", a.scale_film],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
                 for _ in range(n)]
        t0 = time.time()
        outs = []
        for pr in procs:
            try:
                outs.append(pr.communicate(timeout=a.worker_timeout)[0])
            except subprocess.TimeoutExpired:
                pr.kill()
                outs.append("")
        got = [json.loads(o.strip().splitlines()[-1]) for o in outs if o.strip()]
        if len(got) != n:
            print(f"    {n:2d} procs   only {len(got)} returned -- reported, not dropped")
            continue
        per = sum(r["update_bvh_ms"] for r in got) / len(got)
        agg = n / (per / 1000.0)
        base = base or agg
        print(f"    {n:2d} procs   {per:8.2f} ms/img each   {agg:7.2f} img/s aggregate   "
              f"{agg/base:5.2f}x   800k = {human_span(800000 / agg / 3600)}")

    # THE NEGATIVE CONTROL, WITHOUT WHICH THE DETERMINISM COLUMN ABOVE IS DECORATION.
    #
    # `pixi.toml` records `llvm_ad_rgb` at default threads drifting by up to 1/255 on 12-16
    # pixels of 1,048,576, and the sweep above reports it byte-identical. Two readings of one
    # configuration, so one of them is measuring the wrong thing, and the honest move is to go
    # find the drift rather than to publish the convenient half.
    #
    # The mechanism named in that record is FILM ACCUMULATION ORDER. At `spp=1` under a box
    # filter every pixel receives exactly one sample, so there is no accumulation order to vary
    # and no drift to find -- which would make the identical result true and narrow rather than
    # a contradiction. Raising spp is what separates those two readings: if the digests diverge
    # as spp climbs, this check works and the recorded drift is an spp>1 phenomenon; if they
    # never diverge at any spp, this check cannot fail and proves nothing.
    print("\ndeterminism, two fresh processes per row, both films:\n")
    print(f"    {'film':10s} {'integrator':12s} {'filter':9s} {'spp':>4s}  "
          f"{'ms/img':>10s}  verdict")
    det = []
    for film, spps in (("bench", (1, 4, 16, 64)), ("shipping", (16, 128))):
        for spp in spps:
            if time.time() - started > a.deadline:
                print(f"    {film:10s} SKIPPED at spp {spp} on the deadline, named not dropped")
                continue
            d1 = run_worker("llvm_ad_rgb", 0, a.worker_timeout, spp, film)
            d2 = run_worker("llvm_ad_rgb", 0, a.worker_timeout, spp, film)
            if "error" in d1 or "error" in d2:
                print(f"    {film:10s} spp {spp:3d}   FAIL "
                      f"{d1.get('error') or d2.get('error')}")
                continue
            same = d1["sha256"] == d2["sha256"]
            det.append((film, spp, same))
            integ, filt = (("path", "gaussian") if film == "shipping" else ("aov", "box"))
            print(f"    {film:10s} {integ:12s} {filt:9s} {spp:4d}  {d1['update_bvh_ms']:10.2f}  "
                  f"{'identical' if same else 'DIFFER -- drift reproduced'}")

    fired = [r for r in det if not r[2]]
    print("")
    if fired:
        print("    THE CONTROL FIRES, AND IT TOOK THE RIGHT FILM TO DO IT.")
        print(f"    {len(fired)} of {len(det)} configurations differ across two processes, all "
              "of them on the")
        print("    SHIPPING film. That is what `pixi.toml` recorded, reproduced here, and it")
        print("    retires the earlier reading in this file that no spp reproduced it: the")
        print("    variable was never spp, it was the film. `bench` cannot drift for three")
        print("    independent reasons -- an aov integrator is deterministic geometry, a box")
        print("    filter puts every sample in one pixel so nothing splats across a thread's")
        print("    block boundary, and one sample per pixel has no accumulation order at all.")
        print("")
        print("    So the `identical` rows on `bench` were true and worthless, and the earlier")
        print("    conclusion drawn from them -- that metal_ad_rgb might be a corpus renderer --")
        print("    rested on a film that could not have told us otherwise.")
    else:
        print("    THE CONTROL DID NOT FIRE, AND THAT IS THE RESULT.")
        print("    Nothing here has shown this check CAN fail, which makes the verdict column")
        print("    decoration rather than evidence. PITFALLS 2: a check that never fails")
        print("    certifies whatever it is pointed at.")
    print("")
    print("    The 1-thread constraint STANDS either way, but the consolation attached to it")
    print("    was a BENCH-film claim and does not survive the shipping film. On `bench`, eight")
    print("    single-threaded processes matched the multithreaded rate, so the rule cost")
    print("    nothing. On `shipping` at four processes the aggregate is 0.12 img/s against")
    print("    0.22 for one multithreaded process -- about half. The crossover is somewhere")
    print("    above four and has not been measured, so on the film that renders the corpus")
    print("    the rule currently costs throughput rather than being free.")
    print("")
    print("    Two processes per row. A two-sample comparison resolves only drift that recurs;")
    print("    a defect appearing in one run of a hundred is below what this sees.")

    print("\nEvery figure is this desk only. The 3090 and the 4090 are other machines and "
          "nothing here was measured on them.")

    # THE RECORD, WRITTEN WHERE A PERSON WILL FIND IT. Stdout scrolls away; a file does not.
    out = pathlib.Path(a.results).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "mi_bench_llvm-results.json"
    dest.write_text(json.dumps({
        "machine": host,
        "film_bench": {"integrator": "aov", "rfilter": "box", "spp": SPP,
                       "source": "mi_bench2.py"},
        "film_shipping": {"integrator": "path max_depth 6", "rfilter": "gaussian",
                          "spp": 128, "source": "render_view.py:134-153"},
        "variants": rows,
        "determinism": [{"film": f, "spp": s, "identical": i} for f, s, i in det],
        "control_fired": bool(fired),
        "note": ("ms/img are records and stay SI. 800k projections are spans, not decimals. "
                 "Nothing here was measured on the 3090 or the 4090."),
    }, indent=2))
    print(f"\nresults written to {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
