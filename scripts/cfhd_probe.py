"""Can depth survive CineForm, and does Matroska accept it?

CineForm is a wavelet codec sold as VISUALLY lossless. Depth is not a picture, it is a
measurement in metres, so "you cannot see the difference" is not the test. The test is how
many millimetres come back changed, and that is what this measures before any corpus is
written through it.

The probe encodes a known ramp plus a hard depth discontinuity, because wavelets do their
worst at edges and a smooth ramp alone would flatter the codec.
"""
import json
import os
import subprocess
import sys

import numpy as np

SP = os.path.dirname(os.path.abspath(__file__))
W = H = 1024
N = 24
# The band must contain the step, or the clip in `quantise` shows up as codec error. The
# first version used 2.4 .. 3.5 with a step down to 2.2, so 200 mm of pure clipping was
# reported as a max error and read as if the codec had done it.
NEAR, FAR = 2.0, 3.6


def source_depth(i):
    """A ramp, plus a step of 0.2 m -- an arm crossing a torso -- that moves with the frame."""
    # The ramp spans a SUB-range of the band, so a 0.2 m step down still lands inside it.
    # Spanning the full band meant the step clipped at the near end, and 200 mm of clipping
    # was reported twice as if it were an error the codec had made.
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    z = (NEAR + 0.25) + ((FAR - 0.05) - (NEAR + 0.25)) * (x / (W - 1))
    step = (y > (H * 0.3 + i * 8)) & (y < (H * 0.7 + i * 8))
    return np.where(step, z - 0.2, z).astype(np.float32)


def quantise(z, bits=12):
    """Depth to integer codes. The mapping is linear and its ends travel with the file."""
    n = (1 << bits) - 1
    q = np.clip((z - NEAR) / (FAR - NEAR), 0.0, 1.0)
    return np.round(q * n).astype(np.uint16)


def dequantise(code, bits=12):
    n = (1 << bits) - 1
    return NEAR + (code.astype(np.float32) / n) * (FAR - NEAR)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


results = {}
# Both containers behaved identically in the first pass, so Matroska only from here -- it is
# the FOSS one. The variable now is BIT DEPTH, which is what actually decides precision.
#   gbrp12le      12-bit planar RGB, depth in all three planes
#   gbrap12le     12-bit planar RGB + alpha, for the overlay layer
#   yuv422p10le   10-bit, depth in luma only so 4:2:2 chroma subsampling cannot touch it
for container, ext, pix, bits, nplanes in (
        ("matroska", "12bit.mkv", "gbrp12le", 12, 3),
        ("matroska", "10bit.mkv", "yuv422p10le", 10, 1)):
    out = os.path.join(SP, "probe.%s" % ext)
    if os.path.exists(out):
        os.remove(out)
    # gbrp12le is planar 12-bit RGB. Depth goes in all three planes identically, so the
    # codec sees no chroma detail to spend bits on.
    enc = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", pix, "-s", "%dx%d" % (W, H),
         "-r", "30", "-i", "pipe:0",
         "-c:v", "cfhd", "-quality", "film3+", "-pix_fmt", pix,
         "-f", container, out],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    for i in range(N):
        plane = quantise(source_depth(i), bits).astype("<u2")
        for _ in range(nplanes):
            enc.stdin.write(plane.tobytes())
        if pix == "yuv422p10le":              # neutral chroma at half width
            neutral = np.full((H, W // 2), 1 << (bits - 1), dtype="<u2")
            enc.stdin.write(neutral.tobytes())
            enc.stdin.write(neutral.tobytes())
    enc.stdin.close()
    err = enc.stderr.read().decode(errors="ignore")
    enc.wait()
    if enc.returncode != 0 or not os.path.exists(out):
        results[ext] = {"ok": False, "why": err.strip()[:300]}
        print("%-4s ENCODE FAILED: %s" % (ext, err.strip()[:200]))
        continue

    dec = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", out,
         "-f", "rawvideo", "-pix_fmt", pix, "pipe:1"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    raw = dec.stdout
    per = W * H * 2
    stride = per * nplanes + (W * H * 2 if pix == "yuv422p10le" else 0)
    frames = len(raw) // stride
    # Two errors, separated, because they have different causes and different fixes.
    #   quantisation -- chosen, fixed by more bits or a tighter band
    #   codec        -- what CineForm ADDS on top, fixed only by a different codec
    worst_med = worst_max = 0.0
    codec_med = codec_max = 0.0
    exact = 0
    total = 0
    for i in range(min(frames, N)):
        g = np.frombuffer(raw, dtype="<u2", count=W * H, offset=i * stride).reshape(H, W)
        ref = source_depth(i)
        qref = quantise(ref, bits)
        got = dequantise(g, bits)
        d = np.abs(got - dequantise(qref, bits))    # codec only
        codec_med = max(codec_med, float(np.median(d)))
        codec_max = max(codec_max, float(d.max()))
        e = np.abs(got - ref)                        # end to end
        worst_med = max(worst_med, float(np.median(e)))
        worst_max = max(worst_max, float(e.max()))
        exact += int((g == qref).sum())
        total += g.size
    size = os.path.getsize(out)
    results[ext] = {"ok": True, "pix_fmt": pix, "bits": bits,
                    "mm_per_code": (FAR - NEAR) / ((1 << bits) - 1) * 1000, "frames": frames, "bytes": size,
                    "median_mm": worst_med * 1000, "max_mm": worst_max * 1000,
                    "codec_median_mm": codec_med * 1000, "codec_max_mm": codec_max * 1000,
                    "codes_exact_pct": 100.0 * exact / total,
                    "mb_per_1000_frames": size / max(frames, 1) * 1000 / 2**20}
    r = results[ext]
    print("%-10s %2df %6.1f MB/1000f | end-to-end med %.4f max %.3f mm | "
          "CODEC ONLY med %.4f max %.3f mm | %.2f%% codes exact"
          % (pix, frames, r["mb_per_1000_frames"], r["median_mm"], r["max_mm"],
             r["codec_median_mm"], r["codec_max_mm"], r["codes_exact_pct"]))

# the floor: what pure 12-bit quantisation costs, with no codec at all
for b in (10, 12):
    q = dequantise(quantise(source_depth(0), b), b)
    qe = np.abs(q - source_depth(0))
    print("%d-bit floor (no codec): median %.4f mm  max %.4f mm  |  one code step over "
          "%.2f m = %.4f mm" % (b, float(np.median(qe)) * 1000, float(qe.max()) * 1000,
                                FAR - NEAR, (FAR - NEAR) / ((1 << b) - 1) * 1000))
json.dump(results, open(os.path.join(SP, "cfhd_probe.json"), "w"), indent=1)
