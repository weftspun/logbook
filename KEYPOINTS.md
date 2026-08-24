# Key points

The goal manifest `weftspun/weftspun-keypoint` is named for a label, not for a model and not
for a corpus. A keypoint is the annotation the whole goal converges on: 104-keypoint wholebody
detection, trained from ANNY renders, with `pose-consensus` refereeing what a pose actually
was.

Naming the goal after the label rather than after the detector is what lets unrelated-looking
projects sit in one manifest and still be one goal. `default.xml` says so in its own header:
the sinew motion-capture projects are checked out beside the corpus "because motion capture
produces keypoints, which is the same label this corpus supervises". A renderer that draws
bodies, a detector trained on them, a referee that checks them, and hardware that measures
them are four apparatus around one annotation.

The sibling goal was named the same way. `weftspun/weftspun-mesh-latents` was everything that
turned an image into geometry, and its header stated the relationship between them: "The corpus
is shared rather than copied. Both goals render from the same assets and both record into the
same logbook." The two manifests overlapped heavily and were not a fork of each other — a
project serving one goal and not the other was the exception.

**That manifest was archived on 2026-08-22, and the overlap is why the archiving cost little.**
Because the corpus was shared rather than copied, absorbing the image-to-geometry projects into
this manifest was a matter of listing them, not of moving anything: they sit here now pinned at
`refs/tags/mesh-latents/v0.1.0-dev.1`, a tag that says which goal they came from. So there is
one live goal manifest and still two goals.

## Three things carry this name and are not each other

The word is overloaded across the workspace, and one of the three is a trap:

| name                             | what it is                                                       |
| -------------------------------- | ---------------------------------------------------------------- |
| `c:\keypoint`                    | a checkout of the goal manifest — a directory, replaceable       |
| `weftspun/weftspun-keypoint`     | the goal manifest itself: what is in the goal, and on which side |
| `weftspun/rf-detr-keypoint-data` | **blocklisted for training.** Validation only                    |

The third is the one to keep straight, because it is the one whose name reads like a keypoint
training set. It is not: it carries the entire blinded holdout, and 78% of it is
licence-dirty. The blocklist entry in `CLAUDE.md` has the counts. A keypoint training set
is built, not filtered out of that one.

## 2026-08-20 — the manifest reference, fixed twice

`CLAUDE.md` pointed placement at `default.xml` in `weftspun/weftspun`. That repository is
archived; the manifest was split per goal. Two references were stale.

Two agents working the same workspace each found it and each opened a pull request, within the
same hour and without seeing each other: `logbook#9` and `logbook#10`. The work was duplicated
in full.

**The measurement, and why one of the two was wrong.** A fixed population is enumerated, not
sampled, so the sweep was an enumeration: across the keypoint checkout, `weftspun/weftspun`
appeared exactly twice outside `.repo/`, and after the fix, zero times. That number is correct
and it answered the wrong question. The sweep ran _inside one goal checkout_, so it could only
see one goal, and `#9` accordingly rewrote both references to name `weftspun/weftspun-keypoint`
alone. `#10` named both live manifests and left the rule general. The split is org-wide; a
workspace-scoped sweep cannot see that, however exhaustively it enumerates.

`#9` is closed as superseded. It is recorded here rather than deleted quietly, because the
failure is not the duplicated effort — that cost an hour — it is that an enumeration returning
a true count reads exactly like a complete answer.

**A second thing worth not repeating.** The `.logbook` checkout inside a `repo`-managed
workspace sits on a detached HEAD, and `#9` was authored by creating a branch directly in it,
in a workspace another agent was working in at the same time. A branch in a shared checkout is
not a claim anybody else can see, and an uncommitted edit in one is less than that. The fix was
a decoupled clone outside the workspace and the shared checkout restored to the detached HEAD
it was found on. State that travels between agents has to be a pushed branch or a pull request;
nothing in a working tree qualifies.
