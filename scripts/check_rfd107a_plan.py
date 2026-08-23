"""Check `rfd107a-plan.usda` against RFD 107a, and against itself.

WHY THIS EXISTS. A plan written as prose can say step 8 depends on step 9 and nobody
notices. A plan written as a graph can too, unless something reads the graph. This reads
it: every `dependsOn` target must resolve, must have a strictly lower `order`, and the
`order` values must be 1..N with no gaps and no repeats. It found one defect while being
written -- the renderer sat at order 2 depending on the bake at order 3.

AND AGAINST THE DOCUMENT. Every count under /Rfd107a/Quantities is searched for in the
source documents with commas stripped, as a whole token. The stage is not allowed to be the
only place a number lives, because then the number is unreviewed and the RFD and the plan
can drift apart silently. This is the pattern `check-rfd-structure.py` uses for RFD 1000's
state list: read the claim out of the document rather than restating it.

WHAT IT DOES NOT CHECK. Whether the plan is a good plan, and whether the counts are right
-- only that the two artefacts agree. A wrong number stated identically in both passes.

Usage:
    python check_rfd107a_plan.py [stage.usda] [--self-test]

Exit code is non-zero on any failure, and on any negative control that fails to fail.
"""

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_STAGE = HERE.parent / "rfd107a-plan.usda"
REPO = HERE.parent


def workspace_root():
    """The `repo` client root: the first ancestor holding `.repo`.

    COUNTED PARENTS TWICE AND WAS WRONG TWICE, which is why this is a search now. The
    first version said `parents[2]` and landed on `C:\\`. The fix said `parents[1]`, which
    was right for exactly as long as this repository sat at the workspace root as
    `.logbook` -- the manifest then moved it to `2-contract/logbook` and `parents[1]`
    became `2-contract`. A hard-coded depth encodes where a project happens to be checked
    out today, and the manifest is allowed to move it tomorrow. `.repo` is the thing that
    does not move.

    Returns None when there is no client above us, which is what CI sees: this repository
    checked out on its own, with no workspace and no RFD anywhere near it.
    """
    for d in (REPO, *REPO.parents):
        if (d / ".repo").is_dir():
            return d
    return None


def rfd_dir():
    """Where RFD 107a is checked out, asked of the manifest rather than guessed.

    The RFD moved in the same sync this repository did -- `.request_for_discussion` at the
    workspace root became `2-contract/request_for_discussion` -- so a second hard-coded
    path would have broken for the second time on the same afternoon. `default.xml` is the
    thing that knows: it is where the placement is decided, and the Sides rule says a
    project's side is whatever a live goal manifest says it is.
    """
    root = workspace_root()
    if root is None:
        return None
    manifest = root / ".repo" / "manifests" / "default.xml"
    if manifest.exists():
        import xml.etree.ElementTree as ET

        for project in ET.parse(manifest).getroot().iter("project"):
            if project.get("name") == "request-for-discussion":
                return root / project.get("path") / "107a-the-wholebody-gap"
    # No manifest to read: one level of search rather than a walk of the whole tree.
    for name in ("request_for_discussion", "request-for-discussion"):
        for cand in (root / name, *root.glob(f"*/{name}")):
            if cand.is_dir():
                return cand / "107a-the-wholebody-gap"
    return None


ROOT = workspace_root()
RFD_DIR = rfd_dir() or (REPO / ".request_for_discussion" / "107a-the-wholebody-gap")
# The working agreements are a source too, and not as a convenience. The holdout is 523
# images, and that count is stated in CLAUDE.md rather than in RFD 107a -- the RFD relies
# on it without restating it. Searching only the RFD reported the count as drifted when
# what had actually happened is that it lives one document over.
#
# CLAUDE.md is read from this repository rather than from the workspace root. The root copy
# is a `linkfile` pointing back here, so the two are the same bytes when the workspace
# exists, and only this one is there when the logbook is checked out on its own.
SOURCES = (RFD_DIR / "README.md", RFD_DIR / "DETAILS.md", REPO / "CLAUDE.md")
PLAN = "/Rfd107a/Plan"
QUANTITIES = "/Rfd107a/Quantities"
STATES = ("gate", "build", "measure", "exists")


def rfd_text():
    """The sources as one string, commas stripped so 19,158 finds 19158."""
    parts = []
    for path in SOURCES:
        if not path.exists():
            # A missing source is a FAIL, not a skip. A silent skip reads exactly like a
            # pass, and this check would then certify a stage nothing was compared to.
            return None, f"source document missing: {path}"
        parts.append(path.read_text(encoding="utf-8"))
    return re.sub(r"(?<=\d),(?=\d)", "", "\n".join(parts)), None


def check(path):
    from pxr import Usd

    stage = Usd.Stage.Open(str(path))
    if not stage:
        print(f"  FAIL cannot open {path}")
        return 1

    failures = []
    plan = stage.GetPrimAtPath(PLAN)
    if not plan:
        print(f"  FAIL no plan at {PLAN}")
        return 1

    tasks = list(plan.GetChildren())
    orders = {}
    for t in tasks:
        order = t.GetAttribute("order").Get()
        state = t.GetAttribute("state").Get()
        if order is None:
            failures.append(f"{t.GetName()}: no order")
            continue
        if order in orders:
            failures.append(f"{t.GetName()}: order {order} already taken by {orders[order]}")
        orders[order] = t.GetName()
        if state not in STATES:
            failures.append(f"{t.GetName()}: state {state!r} is not one of {STATES}")
        if not t.GetAttribute("measurement").Get():
            # Rule 4: a number without a baseline is not a measurement, and a step with no
            # measurement at all is an intention. Every task says what it will report.
            failures.append(f"{t.GetName()}: no measurement, so nothing says when it is done")

    expected = set(range(1, len(tasks) + 1))
    if set(orders) != expected:
        failures.append(f"orders are {sorted(orders)}, expected 1..{len(tasks)} with no gaps")

    # The dependency edges, which is the whole reason this is a stage and not a list.
    for t in tasks:
        mine = t.GetAttribute("order").Get()
        for target in t.GetRelationship("dependsOn").GetTargets():
            dep = stage.GetPrimAtPath(target)
            if not dep:
                failures.append(f"{t.GetName()}: dependsOn {target} which does not resolve")
                continue
            theirs = dep.GetAttribute("order").Get()
            if theirs is None or mine is None:
                continue
            if theirs >= mine:
                failures.append(
                    f"{t.GetName()} is order {mine} and depends on {dep.GetName()} at "
                    f"order {theirs}. The numbering disagrees with the graph."
                )
    print(f"  ok   {len(tasks)} tasks, orders 1..{len(tasks)}, every edge resolves and points back")

    text, err = rfd_text()

    # THE CRITICAL PATH, AGAINST THE GRAPH RATHER THAN AGAINST THE SENTENCE THAT STATES IT.
    #
    # DETAILS.md now says how deep the plan is and how many tasks are critical. Those are
    # derived facts, so they are read off the stage here and compared, rather than trusted:
    # a later edge that changes the slack has to change the prose or fail this.
    #
    # Unit durations, because the stage carries no estimates. That is the assumption the
    # document states, and this gate holds it to the same one.
    deps = {t.GetName(): [d.name for d in t.GetRelationship("dependsOn").GetTargets()] for t in tasks}
    rank = {t.GetName(): t.GetAttribute("order").Get() for t in tasks}

    # WALK THE ORDER RATHER THAN RECURSING, AND SAY SO WHEN IT CANNOT BE WALKED.
    #
    # The first version of this block recursed over `dependsOn`, and the backward-edge control
    # turned that into a cycle and a RecursionError -- the gate crashed instead of reporting,
    # which is worse than a false pass because the traceback buries the real finding. The
    # numbering is already checked to be topological above, so ascending `order` is a safe
    # walk. A cycle is a FAIL here, not a skipped section: an unmet precondition reads exactly
    # like a pass otherwise.
    backward = [n for n, ds in deps.items()
                if any(rank.get(d) is None or rank[d] >= rank[n] for d in ds)]
    if backward:
        failures.append(
            "critical path not computed: " + ", ".join(sorted(backward))
            + " depend on tasks at or after their own order, so the graph is not a walkable order"
        )
    else:
        by_rank = sorted(deps, key=lambda n: rank[n])
        es = {}
        for n in by_rank:
            es[n] = max([es[d] + 1 for d in deps[n]], default=0)
        depth = max(es.values()) + 1
        succ = {n: [m for m, ds in deps.items() if n in ds] for n in deps}
        lf = {}
        for n in reversed(by_rank):
            lf[n] = min([lf[s] - 1 for s in succ[n]], default=depth)
        floating = [n for n in deps if (lf[n] - 1) - es[n] > 0]
        critical = len(deps) - len(floating)

        if not err:
            want = [
                "six layers deep" if depth == 6 else f"{depth} layers deep",
                "nine of the ten tasks are critical" if (critical, len(deps)) == (9, 10)
                else f"{critical} of the {len(deps)} tasks are critical",
            ]
            missing = [c for c in want if c not in text]
            if missing:
                failures.append(
                    "DETAILS.md does not state what the graph computes: " + "; ".join(missing)
                )
            elif len(floating) != 1:
                failures.append(
                    f"the graph gives {len(floating)} tasks with slack; DETAILS.md says one"
                )
            else:
                print(f"  ok   critical path: {depth} layers, {critical} of {len(deps)} "
                      f"critical, slack only on {floating[0]}")

    # The counts, against the document rather than against memory.
    if err:
        failures.append(err)
    else:
        quantities = stage.GetPrimAtPath(QUANTITIES)
        if not quantities:
            failures.append(f"no quantities at {QUANTITIES}")
        else:
            attrs = [a for a in quantities.GetAttributes() if a.HasAuthoredValue()]
            missing = []
            for a in attrs:
                value = a.Get()
                token = f"{value:g}" if isinstance(value, float) else str(value)
                if not re.search(rf"(?<![\d.]){re.escape(token)}(?![\d.])", text):
                    missing.append(f"{a.GetName()}={token}")
            if missing:
                failures.append("not found in the source documents: " + ", ".join(missing))
            else:
                print(f"  ok   {len(attrs)} quantities, every one present in the source documents")

    if failures:
        for f in failures:
            print(f"  FAIL {f}")
        return 1
    print("\nThe plan validates. The order is a topological order, and the counts are the documents own.")
    return 0


# --- negative controls ------------------------------------------------------------------
#
# `check` passing proves the current file is consistent. It does not prove a broken one
# would be caught, which is the only property worth having. Each control breaks the stage a
# different way in a copy, and each must make `check` fail.


def self_test(path):
    import contextlib
    import io

    from pxr import Usd

    def _backward_edge(stage):
        """Make the renderer depend on the loop that consumes it.

        Renumbering would test this too, and badly: setting T02's order to 9 collides with
        T09 and the uniqueness check fires first, so the control passes while proving
        nothing about the direction of edges. Mutate the edge itself instead."""
        rel = stage.GetPrimAtPath(f"{PLAN}/T02_Renderer").GetRelationship("dependsOn")
        rel.SetTargets([f"{PLAN}/T07_VerificationLoop"])

    def _dangling_edge(stage):
        """Point a dependency at a prim that is not there."""
        rel = stage.GetPrimAtPath(f"{PLAN}/T09_GgufAndHead").GetRelationship("dependsOn")
        rel.SetTargets([f"{PLAN}/T99_DoesNotExist"])

    def _drift_a_count(stage):
        """Change one quantity. The RFD then says something the plan does not."""
        stage.GetPrimAtPath(QUANTITIES).GetAttribute("sharedKeypoints").Set(15)

    def _drop_a_measurement(stage):
        """Remove what a step will report, leaving an intention."""
        stage.GetPrimAtPath(f"{PLAN}/T10_Evaluate").GetAttribute("measurement").Set("")

    def _unknown_state(stage):
        """A state outside the vocabulary, which is how a fifth one arrives unannounced."""
        stage.GetPrimAtPath(f"{PLAN}/T05_StrengthWindow").GetAttribute("state").Set("done")

    def _slack_vanishes(stage):
        """Make the schema step feed the loop, which removes the only float in the plan.

        DETAILS.md says one task has slack. Add this edge and none does, so the sentence is
        wrong while every existing check still passes -- which is exactly the drift the
        critical-path block above exists to catch."""
        rel = stage.GetPrimAtPath(f"{PLAN}/T07_VerificationLoop").GetRelationship("dependsOn")
        rel.SetTargets(list(rel.GetTargets()) + [f"{PLAN}/T06_SchemaCompletion"])

    controls = [
        ("a task depends on a later task", _backward_edge),
        ("a dependency points at nothing", _dangling_edge),
        ("a count drifts from the RFD", _drift_a_count),
        ("a task states no measurement", _drop_a_measurement),
        ("a state outside the vocabulary", _unknown_state),
        ("the last slack in the plan disappears", _slack_vanishes),
    ]

    print("negative controls (each must FAIL):")
    bad = []
    for i, (label, mutate) in enumerate(controls):
        # A unique path per control. USD caches stages by identifier, so reusing one
        # filename hands the next control the previous one's mutated stage -- the hm08
        # exporter's self-test was wrong that way once, and every control still printed
        # FAIL while three of them reported the second one's defect.
        tmp = pathlib.Path(f"{path}.control{i}.usda")
        tmp.unlink(missing_ok=True)
        Usd.Stage.Open(str(path)).Export(str(tmp))
        st = Usd.Stage.Open(str(tmp))
        mutate(st)
        st.GetRootLayer().Save()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = check(tmp)
        tmp.unlink(missing_ok=True)
        first = next((ln.strip() for ln in buf.getvalue().splitlines() if "FAIL" in ln), "")
        if rc:
            print(f"  ok   {label}: {first}")
        else:
            print(f"  BAD  {label}: passed, so this check certifies the defect")
            bad.append(label)

    if bad:
        print(f"\n{len(bad)} control(s) did not fire. The gate is decoration until they do.")
        return 1
    print(f"\nAll {len(controls)} controls fired.")
    return 0


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    path = pathlib.Path(args[0]) if args else DEFAULT_STAGE
    print(f"checking {path}")
    rc = check(path)
    if "--self-test" in argv[1:]:
        print()
        rc |= self_test(path)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
