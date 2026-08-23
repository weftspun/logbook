# Logbook: the ANNY fit that the corpus does not need

A day was spent making ANNY reproduce another body, and the pipeline never asked for that. The
measurements are kept because three of them answer questions that outlived the goal, and the
wrong turn is kept because a reader who knows which road is a dead end is better off than one
who only knows the current answer.

## The reframe that retired it

The corpus pipeline is skeleton poses ANNY, Mitsuba renders, stylisation follows. The 104
keypoints come out of ANNY's own forward kinematics, so the label is exact by construction and
the rendered body **is** the body the keypoints describe. A skeletal disagreement between ANNY
and a pose source violates no ground truth, because no ground truth is being compared: the source
skeleton only has to supply plausible pose variety.

Everything below was measuring how closely ANNY could imitate the Kimodo gap corpus's body. That
is a question for retargeting a specific character, not for building a labelled corpus.
`sample_identities.py` confirms the separation from the other side -- identity and phenotype
variation are their own pluggable axis with their own relations, not something a pose fit solves.

## The phenotypes do not fix the head, and the eleven-axis set does not either

Bone lengths are pose-invariant, so they are what the fit targets; an earlier attempt compared
ANNY's rest pose against the corpus's crouch frame and reported a mean near 552 mm -- eight soda cans, which
is a crouch and not a skeleton -- and would have disproved a correct hypothesis. Residuals against the corpus's 76 pose-invariant lengths,
in millimetres, with a stacked penny at 1.52 mm:

| region    | n   | default body | six phenotypes | eleven, simplex |
| --------- | --- | ------------ | -------------- | --------------- |
| leg       | 10  | 16.38        | 3.59           | 3.59            |
| hand      | 50  | 1.14         | 1.64           | 1.64            |
| arm       | 6   | 4.05         | 10.56          | 10.56           |
| head/neck | 7   | 16.41        | 15.77          | 15.77           |
| overall   | 76  | 4.89         | 4.03           | 4.03            |

Three findings, none of them the one that was expected.

**Fitting trades regions against each other.** The legs improve by a factor of four and the arms
get two and a half times worse. One objective over all bones has no reason to respect anatomy,
and only `height` moved appreciably, to 0.851; the other five stayed near zero.

**The head barely moves, and eleven axes do not help.** `phenotypes="all"` loads
`cupsize`, `firmness`, `african`, `asian` and `caucasian` on top of the six. Initialising all
eleven at zero returns **NaN** on the three ethnicity axes and poisons the solve, taking the
overall mean from 4.03 mm to 12.76 mm, from under three stacked pennies to over eight. MakeHuman's ethnicity is a normalised triple, so
all-zero is nought over nought. Constraining them to the simplex through a softmax removes the
NaN and they settle at 0.336, 0.331 and 0.334, which is neutral. The head/neck residual is then
identical to the six-axis fit to two decimal places.

So those axes move face **surface** and not the joint chain, and the head gap is not a phenotype
problem. No amount of fitting closes it.

**The joint is the wrong landmark for a hat anyway.** `HeadEnd` sits 3.9 mm from the nearest
skull vertex, two and a half stacked pennies, and 21.8 mm from the crown of the head, about
fourteen. Headwear anchored on the joint sits that far below the surface it should touch, before
any skeletal disagreement is added.

## The apparatus already existed and was not looked for

`4-entities/gnm-anny-headfit` fits GNM heads into ANNY's parameter space, with a rung ladder and
a `check_readme_claims.py` that re-derives every number in its README from live code. Its README
also records the eleven-versus-six axis distinction that cost a run to rediscover here. A worse
version of it was written from scratch and has since been deleted; only the measurements above
are kept.

## What survives, and it is not nothing

**`Hips` is the body's frame and `Root` is the coordinate system's.** `BONE_MAP` and
`fbxbone_to_anny.json` both assert `Hips` maps to ANNY's `root`, unmeasured, and they are wrong:
ANNY's `root` rests at y = 0.000 m while the clip puts its target between 0.948 and 1.039 m,
about fifteen stacked soda cans up, which is pelvis height on a standing adult. The fit was asked
to place a floor bone at hip height and paid for it through the whole spine above, at a residual
of 107.7 mm, one and a half soda cans, that did not vary with the pose. A residual constant across poses is a fixed
disagreement between skeletons, not an optimiser failing to converge.

**The gap corpus is already in SOMA space.** Its 77 joints are ANNY's 78 less `Root`, under the
map corpus `k` to ANNY `k+1`, and the pose-invariant bone lengths agree at 2.5 mm mean and 1.7 mm
median -- under two stacked pennies -- with 75 of 76 inside 10 mm. So it poses ANNY with no
retarget at all, and it carries the crouches and getups that T01 found the locomotion clips
lacked.

## The renderer is not byte-reproducible on the GPU

Measured because the image differential's error floor depends on it, and because the plan records
`llvm_ad_rgb` at one thread as byte-identical while every script here calls `cuda_ad_rgb`. Two
renders of one scene at one seed, differenced:

| samples per pixel | `cuda_ad_rgb` | `llvm_ad_rgb` |
| ----------------- | ------------- | ------------- |
| 16                | identical     | identical     |
| 64                | 5.8e-11 mean  | identical     |
| 256               | 9.0e-09 mean  | identical     |
| 1024              | 1.9e-08 mean  | identical     |

The disagreement **grows** with sample count, which is the signature of a nondeterministic
reduction order in the parallel accumulation rather than a seeding bug, so passing a seed will
not fix it. Worst case at 1024 spp is 3.6e-07 against one step of an 8-bit channel at 3.9e-03 --
about one eleven-thousandth of one level, far below anything visible and fatal to a digest.

Two consequences. A render whose evidence is a sha256 is produced on `llvm_ad_rgb`, and where GPU
speed is wanted the manifest stores a tolerance rather than a hash. Worth noting `llvm_ad_rgb`
held byte-identical at every count tested **without** being pinned to one thread, which is
stronger than the claim on file.
