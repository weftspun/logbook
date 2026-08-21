# Logbook: CineForm in Godot, and what recording actually costs

Apparatus: `scripts/cfhd_probe.py` for the codec precision, and
`v-sekai-fabric/entities-godot` branch `feat/movie-writer-async-readback` for the rest.
Measured on the local 4090 with a 16 thread CPU.

## What CineForm costs a depth map

CineForm is a wavelet codec sold as visually lossless. Depth is a measurement in metres, so
"you cannot see the difference" is not the test. Over 24 frames at 1024x1024 of a depth ramp
carrying a 0.2 m step, because wavelets do their worst at edges:

| pixel format  | bits | MB per 1000 frames | end to end median | worst  | codec only |
| ------------- | ---- | ------------------ | ----------------- | ------ | ---------- |
| `gbrp12le`    | 12   | 127                | 0.46 mm           | 3.3 mm | 0.39 mm    |
| `yuv422p10le` | 10   | 94                 | 2.10 mm           | 7.9 mm | 1.56 mm    |

Quantisation alone is 0.39 mm for each step at 12 bit and 1.56 mm at 10 bit, so CineForm adds
about one step and no more. 0.46 mm is half a credit card's thickness. 10 bit is ruled out:
its 2.10 mm is coarser than the 0.54 mm agreement measured between two independent renderers,
so it would become the largest error in the chain.

**Retracted.** A first probe reported 97% of codes bit exact and 0.0 mm from the codec. The
probe clipped the depth step below the near plane, and flat clipped regions compress exactly,
so the codec looked perfect on data that was already ruined. A check that passes on broken
input certifies the defect.

## CineForm has no HDR mode

No PQ, no HLG, no BT.2020, no SMPTE 2084 anywhere in the SDK. `TAG_COLORSPACE_YUV` knows 601
and 709 only. Its answer to dynamic range is the film scan one: log encode into 12 bits and
record the curve so a decoder can invert it. That is latitude, not HDR10.

`W13A` and `WP13`, signed 16 bit with the whitepoint at 1<<13, look like the right answer and
are **not usable**: `CSampleEncoder::GetInputFormats` does not advertise either. They appear
only in `VideoBuffers.cpp` pitch arithmetic. The encoder's first preference is `RG64`, 16 bit
RGBA. The 8 bit `BGRA` this writer uses sits eleventh.

## Vendoring the SDK into an engine

Five frictions, none visible from reading the code:

- Godot builds with `/fp:strict`, under which MSVC's C compiler does not fold floating point
  constant expressions, so the codec's static colour matrices fail with C2099.
- `CoCreateGuid` is reached only through platform branches that skip this configuration.
- `LPTSTR lpValueName` takes a string literal. That is const correctness in C++, not the
  UNICODE mismatch it resembles, and undefining UNICODE would have "fixed" it by silently
  switching every Win32 call in the file to ANSI.
- Five `MessageBox` calls raise a system modal licensing dialog from inside the encoder. In a
  headless render that blocks forever, and in a shipped game it cannot be dismissed.
- `mkvmuxer.cc` includes `mkvparser/mkvparser.h`, so trimming the parser out does not work.

## Recording, measured

1920x1080 at 60 fps, 240 frames, budget 16.67 ms for each frame:

|                              | encode      | note |
| ---------------------------- | ----------- | ---- |
| blocking drain, no alpha     | 16.65 ms    |      |
| blocking drain, alpha        | 22.17 ms    |      |
| **pipelined pool, no alpha** | **2.12 ms** | 7.9x |
| **pipelined pool, alpha**    | **2.39 ms** | 9.3x |

The blocking `_drain(true)` waited for each frame's own sample and idled 15 of 16 encoder
threads. **Every 4K figure taken before this fix is void**, including a 52 ms one that was
reported as roughly half readback and half encode. The encode half was this bug.

At 3840x2160 the encoder is 8 ms for each frame with alpha, against a 16.67 ms budget, and
alpha is nearly free: 8.21 against 7.94 ms. Data rate 1.09 Gbit/s, which is ProRes 422 HQ
territory.

## The trap that cost more than the codec

`movie_size` comes from project settings. The window is whatever the display server grants.
When they differ, `add_frame` crops and resizes every frame so the output keeps one
resolution, which is correct and was silent.

Asking for 3840x2160 on a display that grants 3840x2130, over 180 frames:

    movie 3840x2160, window 3840x2130     222 ms for each frame
    movie 3840x2130, window 3840x2130      39 ms for each frame

**A 30 pixel mismatch cost 5.7x**, and the encoder was 8 ms of either figure. This is engine
behaviour shared by every movie writer, not something this module introduced.
`editor/movie_writer/size_mismatch_action` now selects Resize Every Frame, Use Window Size, or
Abort.

## Container

AVI caps a file at 4 GB, which these bitrates reach in about 56 seconds of 4K60 or 95 seconds
of 1080p60. The writer could not record a two minute clip. Replaced with libwebm's mkvmuxer.

`DocTypeIsWebm()` is a DocType selector, not a rejection: a codec id outside the WebM set makes
the muxer emit `matroska`. The video track is `V_MS/VFW/FOURCC` with a `CFHD` fourcc and a
`BITMAPINFOHEADER` CodecPrivate, which is what FFmpeg writes and reads. Audio is
`A_PCM/INT/LIT`.

Matroska takes duration from the last timestamp, so a 120 frame recording at 60 fps reported
1.983 s until the duration was set explicitly.

## Verified by something that is not this code

FFmpeg's own `cfhd` decoder, on files this writer produced: 120 frames at 1920x1080
`gbrp12le`, audio 2.000 s stereo at 48 kHz, container duration 2.000000 s, every frame
decoding and sampled frames all distinct. A codec checked only against its own output has been
checked against nothing.

## Where the remaining time goes, narrowed

At 4K60 the whole pipeline is 50 ms for each frame, of which the writer is 12.8 ms and render
is 1.5 ms. The 36 ms remainder was hypothesised to be the 33 MB PCIe readback.

**That hypothesis is weakened by measurement.** A resolution ladder from 640x360 to 3840x2160,
alpha on, taking the slope of a 120 frame and a 480 frame run so startup cancels:

| resolution | pixels  | rep 1    | rep 2    | encode   |
| ---------- | ------- | -------- | -------- | -------- |
| 640x360    | 0.23 MP | 16.75 ms | 16.51 ms | 0.55 ms  |
| 1280x720   | 0.92 MP | 16.74 ms | 16.24 ms | 1.34 ms  |
| 1920x1080  | 2.07 MP | 16.48 ms | 16.61 ms | 2.51 ms  |
| 2560x1440  | 3.69 MP | 17.34 ms | 19.82 ms | 6.25 ms  |
| 3840x2160  | 8.29 MP | 35.96 ms | 31.58 ms | 11.50 ms |

640x360 moves 36 times fewer pixels than 4K and costs the same 16.75 ms. **A cost that does not
move with pixel count is not a transfer**, so whatever the floor is, it is not the readback.
It sits at one 60 Hz refresh on a 60 Hz display, which points at the present and does not prove
it. `--disable-vsync` did not lower it, which weakens that reading rather than settling it.

Encode is innocent below 4K: it scales properly, 0.55 to 11.50 ms, and is hidden under the floor
until 4K, where it becomes the late component.

**Two readings retracted.** Dividing wall clock by frame count reported 25 ms for both 1080p and
1440p — startup is 1.4 s, which over 180 frames adds 8 ms to every frame, larger than the encode
being measured. And every sub 4K entry landing within one percent of 16.67 ms looked like the
runner pacing to the target rate; `--fixed-fps` at 30, 60 and 120 all return the same 16.6 ms, so
Movie Maker runs flat out and the figure is real work.

**The largest configuration that records at realtime is 1920x1080 at 60 fps with alpha**, and it
wins by being the largest resolution still indistinguishable from the smallest, not by being
fastest. Naming it on the 0.06 ms by which it undercut the budget would have been the convenient
proxy again: the top three rows are one number with a few tenths of noise, and the budget line
runs through the middle of it.

Delivered clip: 600 frames, 10.000 s of video in 11.53 s of wall clock, 556.3 MB, 0.47 Gbit/s,
encode 2.57 ms for each frame, which is a sixth of the budget. Apparatus and figures in
`~/Desktop/cineform-winner-1080p60-alpha.cff`.

Profiling with samply still needs doing to name the floor. `debug_symbols=yes` now builds, so
the PDB exists.
