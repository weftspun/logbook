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
SHAPE = "/Rfd107a/TrainingShape"
FINDINGS = "/Rfd107a/Findings"
# The training shape's closed vocabulary. A sixth kind arrives the same way a fifth
# state would -- unannounced -- so it is enumerated here rather than inferred.
SHAPE_KINDS = ("space", "head", "loss")


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



# --- the reranked path, and the devices it runs on ---------------------------------------
#
# WHY THIS IS HERE AT ALL, GIVEN THE FILE ARGUES AGAINST IT. RFD 107a's own ordering section
# concludes that durations belong out of the graph: "Both readings are correct; they answer
# different questions, and only one of them moves when a task completes." That argument stands
# and is not deleted. What overrides it is narrower than it looks -- durations were kept out
# because nothing read them, and a count nobody reads is a count nobody reviewed. So they enter
# WITH a reader. The unit-duration path above is untouched and still checked; this is a second
# reading beside it, not a replacement for it.

DEVICES = "/Rfd107a/Devices"


def size_scale(stage):
    """The size vocabulary and its points, read out of the stage rather than restated here.

    Same rule `check-rfd-structure.py` follows for RFD 1000's state list: the document owns the
    list and the gate reads it, so the two cannot disagree. A scale hard-coded here would be a
    second place for it to live.
    """
    data = stage.GetRootLayer().customLayerData
    return dict(zip(data["sizeVocabulary"], data["sizePoints"]))


def human_span(hours):
    """A projection, said the way a person would say it.

    CLAUDE.md pairs every physical measurement with a household object because "4.3 mm" does not
    tell a reader whether an error matters. A wall-clock projection has the same problem in the
    other direction: "16.2 h" invites a precision the estimate behind it never had. So a
    RECORD stays SI -- 73.00 ms/image is an instrument reading and keeps its decimals -- and a
    PROJECTION gets a span, which is the same move as the penny and the soda can.

    Buckets deliberately do not discriminate finely. Two configurations that both land on "an
    afternoon" are not being claimed equal; they are being claimed indistinguishable at the
    resolution a plan can act on. The ms/image row is where the difference lives.
    """
    for limit, span in ((0.5, "half an hour"), (1.5, "about an hour"), (4, "an afternoon"),
                        (10, "a working day"), (20, "overnight"), (60, "a long weekend"),
                        (200, "a working week")):
        if hours < limit:
            return span
    return "a month of wall-clock"


def check_devices(stage, failures):
    """Re-derive every peak rate rather than trusting the transcription.

    `cores x lanes x 2 x clock` is arithmetic, so a typo in it is catchable and therefore has to
    be caught. 2% tolerance, because the stated teraflop figures are rounded to one decimal and
    the clocks are vendor boost numbers rather than anything measured on a desk.
    """
    scope = stage.GetPrimAtPath(DEVICES)
    if not scope:
        failures.append(f"no devices at {DEVICES}")
        return {}

    devices, assumed = {}, []
    for d in scope.GetChildren():
        a = {x.GetName(): x.Get() for x in d.GetAttributes() if x.HasAuthoredValue()}
        devices[d.GetName()] = a
        if a.get("clockAssumed"):
            assumed.append(d.GetName())
        if a.get("kind") != "gpu":
            continue
        want = a["computeUnits"] * a["lanesPerUnit"] * 2 * a["clockGhz"] / 1000.0
        got = a["fp32Tflops"]
        if abs(want - got) / want > 0.02:
            failures.append(
                f"{d.GetName()}: {a['computeUnits']} x {a['lanesPerUnit']} x 2 x "
                f"{a['clockGhz']} GHz derives {want:.1f} TF, the stage says {got}")

    live = [n for n, a in devices.items() if a.get("pluggedIn")]
    if not failures:
        # UNVERIFIED THINGS ARE NAMED AND COUNTED, NEVER OMITTED. Every clock here is a vendor
        # figure; none was read off a desk. Printing the count is what stops the table being
        # read as measured.
        print(f"  ok   {len(devices)} devices, every peak rate re-derives from its own "
              f"architecture; {len(live)} plugged in, {len(assumed)} clock(s) ASSUMED")
    return devices


def pert(stage, devices, failures, text):
    """The duration-weighted path, by RFD 204d's formulas.

        TE = (O + 4M + P) / 6        sigma^2 = ((P - O) / 6)^2

    Reported beside the unit-duration reading rather than instead of it. A task with no
    durations authored is a FAIL and not a zero: an unmet precondition that scores zero would
    quietly shorten the path, which is the same shape as a silent skip reading like a pass.
    """
    plan = stage.GetPrimAtPath(PLAN)
    scale = size_scale(stage)
    te, var, deps, gpu, done = {}, {}, {}, {}, []
    for task in plan.GetChildren():
        n = task.GetName()
        if task.GetAttribute("completed").Get():
            # Counted and named, never quietly folded in as a zero.
            done.append(n)
            te[n] = var[n] = 0.0
            gpu[n] = False
            deps[n] = [d.name for d in task.GetRelationship("dependsOn").GetTargets()]
            continue
        toks = [task.GetAttribute(k).Get()
                for k in ("optimisticSize", "mostLikelySize", "pessimisticSize")]
        if any(v is None for v in toks):
            failures.append(f"{n}: no sizes, so the reranked path cannot include it")
            return None
        bad = [v for v in toks if v not in scale]
        if bad:
            failures.append(f"{n}: size(s) {bad} outside the vocabulary {sorted(scale)}")
            return None
        o, m, pe = (scale[v] for v in toks)
        if not (o <= m <= pe):
            failures.append(
                f"{n}: sizes are not ordered, {toks[0]} <= {toks[1]} <= {toks[2]} is false")
            return None
        te[n] = (o + 4 * m + pe) / 6.0
        var[n] = ((pe - o) / 6.0) ** 2
        gpu[n] = bool(task.GetAttribute("gpuBound").Get())
        deps[n] = [d.name for d in task.GetRelationship("dependsOn").GetTargets()]

    # THE FORWARD PASS WALKS `order` AND TRUSTS IT, SO IT HAS TO CHECK IT FIRST. A backward or
    # dangling edge is already a failure above, but this walked the graph anyway and died on a
    # KeyError -- a traceback instead of a verdict, which is worse than either. Found by the
    # backward-edge control, which is the argument for having controls at all.
    order = sorted(te, key=lambda n: plan.GetChild(n).GetAttribute("order").Get())
    seen = set()
    for n in order:
        if any(d not in seen for d in deps[n]):
            failures.append(
                f"{n}: the reranked path cannot be computed while the graph is not a walkable "
                f"order. The edge check above says why.")
            return None
        seen.add(n)

    es, ef = {}, {}
    for n in order:
        es[n] = max([ef[d] for d in deps[n]], default=0.0)
        ef[n] = es[n] + te[n]
    finish = max(ef.values())

    succ = {n: [m for m, ds in deps.items() if n in ds] for n in te}
    lf, ls = {}, {}
    for n in reversed(order):
        lf[n] = min([ls[s] for s in succ[n]], default=finish)
        ls[n] = lf[n] - te[n]
    slack = {n: round(ls[n] - es[n], 3) for n in te}

    chain = [n for n in order if slack[n] <= 1e-6 and te[n] > 0]
    heaviest = max(te, key=lambda n: te[n])

    # THE SCARCE RESOURCE, WHICH THE GRAPH CANNOT SEE. Tasks marked `gpuBound` all want the one
    # plugged-in 24 GiB card, and the dependency graph has no edge saying so. Their summed TE is
    # the serial floor that contention imposes independently of any ordering.
    live_gpu = [n for n, a in devices.items()
                if a.get("kind") == "gpu" and a.get("pluggedIn") and a.get("bf16Native")]
    contended = sorted([n for n in te if gpu[n]], key=lambda n: -te[n])
    contention = sum(te[n] for n in contended)

    # POINTS, NOT DAYS. They order tasks against each other and convert to no calendar.
    print(f"  ok   reranked path: {finish:.1f} size points over {len(chain)} tasks, "
          f"heaviest {heaviest} at {te[heaviest]:.1f} "
          f"({te[heaviest] / finish * 100:.0f}% of the path); {len(done)} complete")
    print(f"  ok   contention: {len(contended)} gpuBound task(s) sum to {contention:.1f} points "
          f"on {len(live_gpu)} live bf16 card(s) -- {', '.join(live_gpu) or 'none'}")

    # THE LEVER, PRICED RATHER THAN ARGUED. The 4090 sits in the stage with `pluggedIn = 0`, so
    # what it is worth is arithmetic: scale every gpuBound task by the ratio of derived peak
    # rates and recompute. Peak-rate scaling is a RANKING and not a budget -- it assumes a task
    # is compute-bound and perfectly portable, and neither is measured here.
    off = [a for a in devices.values()
           if a.get("kind") == "gpu" and not a.get("pluggedIn") and a.get("fp32Tflops")]
    if off and live_gpu:
        best_live = max(devices[n]["fp32Tflops"] for n in live_gpu)
        ratio = best_live / max(a["fp32Tflops"] for a in off)
        e2, f2 = {}, {}
        for n in order:
            s = max([f2[d] for d in deps[n]], default=0.0)
            f2[n] = s + (te[n] * ratio if gpu[n] else te[n])
        saved = finish - max(f2.values())
        print(f"  ok   plugging in the unplugged card: {max(f2.values()):.1f} points, "
              f"{saved:.1f} saved ({saved / finish * 100:.0f}%), a RANKING and not a budget")

    want = f"{finish:.1f} size points"
    if text is not None and want not in text:
        failures.append(f"DETAILS.md does not state the reranked total: {want}")
    return {"finish": finish, "chain": chain, "te": te, "var": var, "slack": slack}


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

    # THE BRAKE ON THE TRAINING SHAPE.
    #
    # Every component must name the finding that motivated it, and that finding must exist.
    # This is the whole mechanism: a finding records a measurement rather than an intention
    # (the logbook rule), so a head, tier or loss cannot enter the shape on the strength of a
    # conversation. It has to be preceded by something somebody measured.
    #
    # Written because the shape expanded five times in one session and nothing was counting.
    # It cannot stop a bad measurement; it stops expansion with none at all.
    shape = stage.GetPrimAtPath(SHAPE)
    if not shape:
        # An absent scope is a FAIL rather than a skip: a silent skip reads exactly like a
        # pass, and this check going quiet is how the brake would come off unnoticed.
        failures.append(f"no training shape at {SHAPE}: the brake cannot be checked")
    else:
        components = list(shape.GetChildren())
        if not components:
            failures.append("the training shape declares no components")
        for c in components:
            kind = c.GetAttribute("kind").Get()
            if kind not in SHAPE_KINDS:
                failures.append(
                    f"{c.GetName()}: kind {kind!r} is outside {SHAPE_KINDS}")
            targets = c.GetRelationship("justifiedBy").GetTargets()
            if not targets:
                failures.append(
                    f"{c.GetName()}: no justifiedBy. A component of the training shape "
                    "needs a finding behind it, which needs a measurement behind it.")
            for target in targets:
                if not str(target).startswith(FINDINGS + "/"):
                    failures.append(
                        f"{c.GetName()}: justifiedBy {target} is not a finding")
                elif not stage.GetPrimAtPath(target):
                    failures.append(
                        f"{c.GetName()}: justifiedBy {target} which does not resolve")
        # ONE FINDING, ONE COMPONENT.
        #
        # `justifiedBy` resolving is not enough, and L04 is why: a consistency term was
        # added citing F10, which measures the body/scene split and says nothing about a
        # consistency term. The citation resolved, so the check passed, and the component
        # was riding a finding it had borrowed.
        #
        # A finding is one measurement. If it is backing two components, at least one of
        # them is stretched over evidence that was not gathered for it. This is the cheapest
        # mechanical proxy for relevance there is -- it does not read the finding, it just
        # refuses to let one be spent twice.
        backing = {}
        for c in components:
            for target in c.GetRelationship("justifiedBy").GetTargets():
                backing.setdefault(str(target), []).append(c.GetName())
        for target, users in sorted(backing.items()):
            if len(users) > 1:
                failures.append(
                    f"{target.rsplit('/', 1)[-1]} justifies {len(users)} components "
                    f"({', '.join(sorted(users))}). One finding is one measurement; at "
                    "least one of these is borrowing it.")

        if not [f for f in failures if "training shape" in f or "justifiedBy" in f
                or "kind" in f or "borrowing it" in f]:
            print(f"  ok   training shape: {len(components)} components, every one "
                  f"justified by a finding that exists")

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

    if not err:
        devices = check_devices(stage, failures)
        pert(stage, devices, failures, text)

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
                # WHAT THIS CATCHES, AND WHAT IT DOES NOT. It is a presence test: the number
                # must appear somewhere in the three documents. It cannot tell that the number
                # appears *as this quantity* rather than in an unrelated sentence, so its power
                # falls as those documents grow -- a drifted value that happens to collide with
                # any other figure in them passes. Binding each quantity to its own phrase would
                # fix that and is not done here; the limit is recorded rather than implied.
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
        """Change one quantity. The RFD then says something the plan does not.

        THE VALUE IS CHOSEN AT RUN TIME, AND THE REASON IS A REAL LIMIT OF THE CHECK ABOVE.
        This control used to set 15, and it stopped firing: the quantity test asks whether a
        number appears anywhere in the source documents, and CLAUDE.md grew a sentence about a
        model dropping "15 mtp tensors". A coincidence in unrelated prose silently turned the
        control green, which is the failure mode negative controls exist to expose -- and it
        was the control that caught it, not the check.

        So the mutation now searches for an integer that appears in none of the sources, which
        keeps the control honest as those documents keep growing.
        """
        text, err = rfd_text()
        assert not err, err
        n = 15
        while re.search(rf"(?<![\d.]){n}(?![\d.])", text):
            n += 1
        stage.GetPrimAtPath(QUANTITIES).GetAttribute("sharedKeypoints").Set(n)

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

    def _unjustified_component(stage):
        """Add a component to the training shape with nothing behind it.

        This is the expansion this brake exists to catch: a new loss term that sounded
        right in conversation, pointing at a finding nobody wrote."""
        from pxr import Usd, Sdf
        prim = stage.DefinePrim(f"{SHAPE}/L99_SomethingWeAgreedTo", "")
        prim.CreateAttribute("kind", Sdf.ValueTypeNames.Token,
                             custom=True, variability=Sdf.VariabilityUniform).Set("loss")
        prim.CreateRelationship("justifiedBy").SetTargets(
            [f"{FINDINGS}/F99_AFindingNobodyWrote"])

    def _borrowed_finding(stage):
        """Point a second component at a finding that already backs another one.

        This is the defect that got through the first version of the brake: the citation
        resolves, so a resolve-only check passes, and the component is justified by evidence
        gathered for something else."""
        rel = stage.GetPrimAtPath(f"{SHAPE}/L03_HeadsAreParallelOnOneQuery").GetRelationship("justifiedBy")
        rel.SetTargets([f"{FINDINGS}/F10_BodyAndSceneAreTwoLatents"])

    def _pert_sizes_missing(stage):
        """Strip one task's sizes. A path that silently drops it would be shorter and would
        still print a number, which is the shape a silent skip always takes."""
        prim = stage.GetPrimAtPath(f"{PLAN}/T08_MaskedTraining")
        for k in ("optimisticSize", "mostLikelySize", "pessimisticSize"):
            prim.GetAttribute(k).Clear()

    def _pert_sizes_unordered(stage):
        """Optimistic above pessimistic. TE still evaluates, so nothing downstream notices."""
        stage.GetPrimAtPath(f"{PLAN}/T05_StrengthWindow").GetAttribute(
            "optimisticSize").Set("XL")

    def _size_outside_vocabulary(stage):
        """A size the scale does not define. Reading the vocabulary out of the stage is only
        worth doing if something rejects a token that is not in it."""
        stage.GetPrimAtPath(f"{PLAN}/T03_PbrBake").GetAttribute("mostLikelySize").Set("XXL")

    def _device_arithmetic_drifts(stage):
        """Move a clock and leave the teraflop figure behind it. This is the transcription
        error the derivation exists to catch, and it is invisible to any reader."""
        stage.GetPrimAtPath(f"{DEVICES}/RTX3090").GetAttribute("clockGhz").Set(2.9)

    def _reranked_total_drifts(stage):
        """Grow a task ON the critical path. The stage then states a total DETAILS.md does not.

        THIS CONTROL STOPPED FIRING ONCE AND THE REASON IS WORTH KEEPING. It grew T06, chosen
        when T06 had 5.7 slack and XL would have swamped it. Correcting the render measurement
        moved T02 onto the critical path, which pushed T06's slack to 7.3 -- just past the 7
        points XL adds -- so the mutation stopped changing the answer and the control went
        green while proving nothing.

        A mutation sized against a graph is a mutation that expires when the graph moves. T10 is
        terminal and on the path by construction, so growing it always moves the finish, whatever
        happens upstream."""
        prim = stage.GetPrimAtPath(f"{PLAN}/T10_Evaluate")
        for k in ("optimisticSize", "mostLikelySize", "pessimisticSize"):
            prim.GetAttribute(k).Set("XL")

    controls = [
        ("a component with no finding behind it", _unjustified_component),
        ("two components share one finding", _borrowed_finding),
        ("a task depends on a later task", _backward_edge),
        ("a dependency points at nothing", _dangling_edge),
        ("a count drifts from the RFD", _drift_a_count),
        ("a task states no measurement", _drop_a_measurement),
        ("a state outside the vocabulary", _unknown_state),
        ("the last slack in the plan disappears", _slack_vanishes),
        ("a task carries no sizes", _pert_sizes_missing),
        ("optimistic exceeds pessimistic", _pert_sizes_unordered),
        ("a size outside the vocabulary", _size_outside_vocabulary),
        ("a device clock drifts from its peak rate", _device_arithmetic_drifts),
        ("the reranked total drifts from DETAILS.md", _reranked_total_drifts),
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
