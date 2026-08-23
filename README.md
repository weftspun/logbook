# Logbook — moved and archived

This repository is archived. Everything it held is in
[weftspun/request-for-discussion](https://github.com/weftspun/request-for-discussion):
the working agreements in CLAUDE.md, the recurring failure modes in
PITFALLS.md, the narrative entries whose names begin `logbook-`, and the
apparatus and gates under `scripts/`.

An RFD records a decision. An entry records the measurement that justified it,
or the measurement that retracted it. They cited each other across a repository
boundary that no gate could check, and `check_rfd107a_plan.py` is the proof:
it validates a plan against RFD 107a's counts and ran as `stages: [manual]`
because CI never had both halves checked out at once. In one repository it is
an ordinary hook. CLAUDE.md there records the move and what it cost, under
"Why the logbook moved here".

The history above this commit is unchanged and stays readable. One thing lives
only here now: this repository was Apache-2.0 OR MIT, and the destination is
MIT. A reader who wants the Apache-2.0 patent grant on this material takes it
from the tree at this revision.

The cross-project engineering record: what was measured, what it cost, and
which roads turned out to be dead ends.
