# Logbook

The cross-project engineering record: what was measured, what it cost, and which roads
turned out to be dead ends.

It was kept private while it carried dataset inventory paths and a credential reference.
Those are out, and the history was collapsed to a single commit rather than edited in
place, so the removed strings are not recoverable from an earlier revision. What remains
is the engineering record itself, including blocklist rationale and licensing judgements
about public datasets — a reader who knows why a source was excluded is better off than
one who only sees the exclusion.

| file | what it holds |
|---|---|
| `todo.md` | the running logbook — dated entries, queued work, standing constraints |
| `logbook-rfd0016-model-repos.md` | RFD 0016: one standalone repo per model, and the reranking |
| `PITFALLS.md` | recurring failure modes — each one a mistake actually made here, what it cost, and the mechanism that now catches it |
| `logbook-soft-renderer-and-mitsuba.md` | the soft renderer's three mis-scaled constants, and Mitsuba 3 against it |
| `logbook-cineform-movie-writer.md` | CineForm in Godot: codec precision, vendoring frictions, and what recording costs |
| `KEYPOINTS.md` | what the keypoint goal is named for, and the three things that share the name |
| `check_comment_density.py` | gate: a change must match the comment density of the code it edits |
| `scripts/` | the apparatus behind the entries, kept so a measurement can be re-run rather than believed |

## How entries are written

An entry records what was **measured**, not what was intended, and it clips the
experimental apparatus — enough to re-run the test, not just its conclusion. Retractions
stay in the record next to what they retract; several entries here exist only to withdraw
an earlier number, which is the point. Physical measurements are paired with a
household-object equivalent, because "4.3 mm" does not tell a reader whether an error
matters and "about three stacked pennies" does.

## Standing constraints recorded here

- GPU work on RunPod only, torn down after use, teardown double-checked
- Anything not in a git repo is torn down after use
- Training data only — validation and test splits strictly held out
- zstd compression, in parquet or standalone; zip and gzip are not acceptable
- zstd parquet in Essential Tuple Normal Form
- No secondary-generation training data
- No third-party pose sources
- DQS blocklisted; Delta Mush and Direct Delta Mush approved
- No runtime code in glTF — exports are pure data
