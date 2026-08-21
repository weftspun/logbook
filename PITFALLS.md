# Recurring failure modes

Each entry names a way this system goes wrong, what it costs, and the guard that catches it.
Every one holds for real code in these repos rather than in general. Most recur at three or
more sites, which is why they live here rather than in memory.

Written in the present per RFD 0025: a mode that stops applying is a line to delete rather
than a line to date. Ordered by cost.

---

## 1. Bugs live at interfaces, never inside components

Every defect in this system sits at a boundary between two things:

| boundary                                        | cost                                                |
| ----------------------------------------------- | --------------------------------------------------- |
| ANNY gender `0=male` against GNM `FEMALE=0`     | flips sex on 800k images                            |
| ANNY Z-up/metres against SOMA +Y-up/centimetres | 100x scale, or a body on its side                   |
| "local Z" against the bone's roll axis          | measures a bend and calls it a twist                |
| `rest_bone_heads` against `vertices`            | 55 mm on an adult, **500 mm on a child**            |
| `lowerarm01` / `lowerarm02` weight boundary     | the forearm twist defect                            |
| twist bones against LabRCSF's joint list        | 12 ANNY bones carry no canonical name               |
| forearm / hand mask boundary                    | mesh mean understates finger error 4x               |
| train / val split                               | contamination                                       |
| BVH bind orientation against ANNY's             | 29.6 deg per-limb offset; blocks the poses relation |

Components get tested because they are easy to name. Interfaces belong to nobody.

**Guard:** `interface_audit.py` names 17 interfaces. Each resolves to
`OK`, `HAZARD`, or `UNCHECKED` — never absent.

---

## 2. A check that passes on known-broken input certifies the defect

The forearm-twist gate reaches honesty on its third form. The first two pass on a rig that
does not transmit twist:

1. a dominance-share proxy — passes outright
2. a distal-band reading driven from the twist bone — 66.9 deg of an ideal 78.8, passes, and
   measures an interface nothing crosses: capture supplies the wrist, never a twist bone
3. a distal-band reading driven from the wrist — still lenient, because a dispersed stock rig
   reads 67 deg near the wrist while its mid-forearm stays flat

Scoring the profile's **linearity** separates all three: stock 52.8, dispersed 24.0,
shipping 3.6.

**Guard:** every gate carries a negative control asserting that broken input fails.
`test_preflight.py` red-tests 10 corruptions. `check_readme_claims.py` answers its own red
test — falsifying two claims trips exactly those two.

---

## 3. A silent skip reads exactly like a pass

Three checks in this system produce no output and look clean while doing nothing:

- split-contamination nested under `if "scenes" in tables`, so it sits out identity
  generation — the phase that creates contamination
- dimorphism, when both sex subgroups come out empty
- child stature, when the sample holds no children

**Guard:** an unmet precondition fails rather than skipping. `interface_audit.py` counts
`UNCHECKED` and names each. `check_readme_claims.py` reports an unregistered claim as
`UNVERIFIED` and counts it against the total.

---

## 4. The convenient proxy lies

Five pairs, where the left column is the one that is easy to read:

| proxy                                          | measurement that settles it             |
| ---------------------------------------------- | --------------------------------------- |
| joints.csv **name coverage**                   | silhouette survival                     |
| Godot's **API surface**                        | the source                              |
| phenotype **parameter percentiles**            | decoded stature in metres               |
| **centroid** limb direction (thigh "+9.7 deg") | recovered **joint angle** (2.2 deg)     |
| joint-**position** residual (BVH "153 mm")     | limb **direction**, which is scale-free |

---

## 5. A number without a baseline is not a measurement

A 153 mm BVH retarget residual reads as damning until a control scores **two rest skeletons
at 139.7 mm**: the posed figure sits 13 mm above an unmeasured floor. The verdict drawn from
it does not hold.

The thigh figure has the same shape — 19.7 deg raw, of which 10.0 deg is static body-shape
difference, so the raw number overstates by 2x.

**Guard:** the floor appears first, in the same table. `bvh_retarget_probe.py` prints the
rest-vs-rest control above its results.

---

## 6. A sampled check claims more than it sees unless it states its floor

A sample of `n` catches defects larger than roughly `3/n`. At `--sample 300` that floor sits
at **10,000 ppm**: nothing below 1 identity in 100 is certified, a defect touching 23
identities (800 of 800k images) escapes 95% of the time, and the audit prints all-PASS.

A full decode of 23,000 identities costs **95 seconds**.

For a _fixed_ population, enumeration replaces estimation. Estimation belongs to unbounded
streams.

**Guard:** `preflight_audit.py` prints its detection floor and fails when asked to certify
below what its sample resolves.

---

## 7. A denominator that does not track reality flatters the result

Whole-mesh mean error reads 9.2 mm during a forearm pronation, because 1,356 torso vertices
sit at exactly 0.00 mm and dilute it, while the fingers sit a golf ball out. The average
understates the part that matters **4x**.

The shape matches a dashboard counting 500s against a fixed denominator: the quiet
datacentre looks healthy because traffic sleeps, not because the failure rate moves.

**Guard:** `corpus_defect_rate.py` reports an exceedance **rate against a stated tolerance**,
over the region that moves, against a baseline. A rate without a threshold is not a
measurement; an absolute rate without a reference does not interpret.

---

## 8. Conventions are data — parse them

- BVH channel order is per-joint and declared. 100STYLE writes `Yrotation Xrotation
Zrotation`; a positional read transposes every rotation.
- ANNY's `local-ref` rotation axes are world-aligned. The local-to-world map is the identity,
  so "local Z" is _world_ Z, 55 deg off the forearm.
- An identity `pose_parameters` is not the rest pose.
- `rest_bone_heads` pairs with `rest_vertices`, never with `vertices`.
- Up axis and units differ per model and per rig.

**Guard:** rotation axes come from probing — rotate 10 deg about each local axis, read the
world axis the skin turns about, invert. The probe reads **descendant** vertices, because a
bone's own vertices blend under LBS and fitting them displaces the recovered rotation centre
by 33 mm.

---

## 9. Documentation rots silently, and rotted documentation misleads worse than none

Two live examples in this system:

- a README headline asserting Godot's twist disperser as the solution, while the shipping
  answer is zero twist bones — a reader following the headline builds the wrong thing
- a docstring asserting Delta Mush is "available here", where `grep` finds zero occurrences

**Guard:** README numbers are tagged claims that `check_readme_claims.py` re-derives from
live code, so drift fails a command. Superseded findings occupy a **SUPERSEDED** section
rather than vanishing under an edit, so dead ends stay visible.

---

## 10. Retractions belong beside what they retract

Claims in this system that do not hold: the twist ratio sweep and its "no ratio works"
conclusion; the soma/game_engine "frame hazard"; the 9.7 deg thigh error; the "neither BVH
formulation transfers the pose" verdict; the claim that Delta Mush is implemented in
`anny_rig`.

Each sits next to the thing it corrects. A reader who knows the dead ends is better off than
one who knows only the current answer, which is the reason this file exists.
