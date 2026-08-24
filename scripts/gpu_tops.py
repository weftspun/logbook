"""Measured throughput for the devices in RFD 107a's plan, against their derived peak rates.

WHY THIS EXISTS. `rfd107a-plan.usda`'s Devices scope carries peak rates DERIVED from
architecture -- units x lanes x 2 for the fused multiply-add x clock -- and every clock in it is
a vendor boost figure marked ASSUMED. `check_rfd107a_plan.py` re-derives the arithmetic, which
catches a transcription error and nothing else: a derivation cannot tell you whether a device
reaches its peak, and the plan currently scales GPU-bound work by ratios of numbers no one has
observed.

`logbook-edge-npu-and-the-anny-forward.md` set the convention this answers to. It divides by
40 TOPS INT4 at an ASSUMED 30% utilisation and says plainly to "treat those as a ranking and
not a budget", because the DFC profiler was never run. This runs the profiler for the one
device that is here.

METHOD, AND IT IS THE ORDINARY ONE. Dense GEMM, C = A @ B at (n, n) @ (n, n), which costs
exactly 2*n^3 floating-point operations -- n^3 multiplies and n^3 adds, the fused pair counted
as two, the same convention the derived peak uses. Anything else measures a kernel author. Sizes
are swept because a single size measures a cache; the best rate over the sweep is what the
device reaches. The device is synchronised before and after, since an asynchronous queue times
the enqueue rather than the work -- which is the trap `mi_bench2.py` records paying for.

WHAT A RATIO TO PEAK DOES AND DOES NOT MEAN. GEMM is the friendliest shape a device sees. A
number here is an upper bound on what real work reaches, so a low ratio is evidence and a high
one is not a promise.

Usage:
    python gpu_tops.py [--sizes 1024,2048,4096] [--results DIR]
"""

import argparse
import json
import pathlib
import subprocess
import sys
import time

# Derived peak, from `rfd107a-plan.usda`'s Devices scope. Restated here would be a second place
# for the fact to live, so the arithmetic is repeated rather than the answer: 19 cores x 128
# lanes x 2 x 1.398 GHz. If the stage changes, this line is what should be edited to match, and
# `check_rfd107a_plan.py` is what checks the stage against itself.
M2PRO_CORES, M2PRO_LANES, M2PRO_GHZ = 19, 128, 1.398
DERIVED_TFLOPS = M2PRO_CORES * M2PRO_LANES * 2 * M2PRO_GHZ / 1000.0


def machine():
    """osquery rather than a scraped sysctl string. Conventions are data; parse them."""
    try:
        out = subprocess.run(
            ["osqueryi", "--json",
             "select cpu_brand, hardware_model, physical_memory from system_info;"],
            capture_output=True, text=True, timeout=30)
        r = json.loads(out.stdout)[0]
        return (f"{r['hardware_model']}, {r['cpu_brand']}, "
                f"{int(r['physical_memory']) / 1024 ** 3:.0f} GiB")
    except Exception as exc:
        return f"UNKNOWN ({type(exc).__name__}) -- provenance degraded, said rather than hidden"


def gemm(torch, device, dtype, n, iters=8):
    """Best-of over `iters`, after a warm-up, with the queue drained on both sides."""
    a = torch.randn(n, n, device=device, dtype=dtype)
    b = torch.randn(n, n, device=device, dtype=dtype)
    sync = torch.mps.synchronize if device == "mps" else (lambda: None)

    for _ in range(2):
        c = a @ b
    sync()

    best = float("inf")
    for _ in range(iters):
        t0 = time.perf_counter()
        c = a @ b
        sync()
        best = min(best, time.perf_counter() - t0)
    del c
    return 2.0 * n ** 3 / best / 1e12          # TFLOP/s


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default="1024,2048,4096")
    ap.add_argument("--results", default=str(pathlib.Path.home() / "Desktop"))
    a = ap.parse_args(argv)

    import torch
    sizes = [int(s) for s in a.sizes.split(",") if s.strip()]

    print(f"machine          {machine()}")
    print(f"torch            {torch.__version__}, mps available {torch.backends.mps.is_available()}")
    print(f"derived peak     {M2PRO_CORES} x {M2PRO_LANES} x 2 x {M2PRO_GHZ} GHz = "
          f"{DERIVED_TFLOPS:.1f} TFLOPS fp32, clock ASSUMED")
    print(f"method           dense GEMM, 2*n^3 flops, best-of-8, synchronised\n")

    rows, results = [], {}
    # bf16 IS IN THE SWEEP TO TEST A CLAIM THE PLAN MAKES. The Devices scope records
    # `bf16Native = 0` for this part, and the consequence it draws is that running a generator
    # at published precision here is emulation. That is checkable: if bf16 lands far below
    # fp16, the claim holds; if it matches, the claim is wrong and the plan should say so.
    for label, device, dtype in (("mps fp32", "mps", torch.float32),
                                 ("mps fp16", "mps", torch.float16),
                                 ("mps bf16", "mps", torch.bfloat16),
                                 ("cpu fp32", "cpu", torch.float32)):
        if device == "mps" and not torch.backends.mps.is_available():
            print(f"  {label:10s} SKIPPED -- no MPS. Named and counted, never omitted.")
            continue
        best, at = 0.0, None
        for n in sizes:
            try:
                tf = gemm(torch, device, dtype, n, iters=4 if device == "cpu" else 8)
            except Exception as exc:
                print(f"  {label:10s} n={n:5d} FAILED {type(exc).__name__}: {exc}")
                continue
            if tf > best:
                best, at = tf, n
        if at is None:
            continue
        util = best / DERIVED_TFLOPS * 100.0
        rows.append((label, best, at, util))
        results[label] = {"tflops": best, "at_n": at, "pct_of_derived_fp32": util}
        print(f"  {label:10s} {best:7.2f} TFLOP/s at n={at:<5d} "
              f"{util:5.1f}% of derived fp32 peak")

    print(f"\n  Derived fp32 peak is {DERIVED_TFLOPS:.1f} TFLOPS and is a RANKING, not a budget.")
    print("  GEMM is the friendliest shape a device sees, so these are an upper bound on what")
    print("  real work reaches -- a low ratio is evidence, a high one is not a promise.")

    out = pathlib.Path(a.results).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "gpu_tops-results.json"
    dest.write_text(json.dumps({
        "machine": machine(),
        "derived_fp32_tflops": DERIVED_TFLOPS,
        "derivation": f"{M2PRO_CORES} x {M2PRO_LANES} x 2 x {M2PRO_GHZ} GHz, clock ASSUMED",
        "method": "dense GEMM, 2*n^3 flops, best-of, synchronised",
        "sizes": sizes,
        "measured": results,
    }, indent=2))
    print(f"\nresults written to {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
