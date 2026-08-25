"""Check `fourloops-plan.usda` against its sources, against the chart, and against itself.

WHY THIS EXISTS. Three documents describe the same four loops: the stage, the chart beside
it (`fourloops-etnf.usda`), and the code the two are about. Nothing stops them drifting
apart except something that reads all three, so this reads all three.

WHAT IT CHECKS, and why each is separate.

1. ORDER. Task `order` values are 1..N with no gaps and no repeats, and every `needs`
   target has a strictly lower order than the task that needs it. A plan written as a graph
   can still say step 3 depends on step 5; only reading the graph catches it.

2. TARGETS RESOLVE. Every relationship target is a prim path that exists in the layer. A
   typo in a `</FourLoops/Stages/...>` path composes without complaint and means nothing.

3. COUNTS ARE NOT ONLY HERE. Every integer under `/FourLoops/Quantities` is searched for in
   the sources the layer names, as a whole token with commas stripped. A number that lives
   only in the stage is a number nobody reviewed. This is the pattern
   `check-rfd-structure.py` uses for RFD 1000's state list and `check_rfd107a_plan.py` uses
   for RFD 107a's.

4. THE CHART AGREES, IN ONE DIRECTION. Every stage the plan declares must be mentioned in
   the chart. The reverse check existed while the chart was HTML and was deleted when it
   became a layer: see the note beside CODE_RE. A stage nobody described is the drift that
   remains possible.

WHAT IT DOES NOT CHECK. Whether the plan is a good plan, and whether the counts are right.
Only that the artefacts agree. A wrong number stated identically in both passes, which is
why the sources are read rather than the stage trusted.

    python check_fourloops_plan.py [stage.usda] [--self-test]

Exit code is non-zero on any failure, and on any negative control that fails to fail.
"""

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_STAGE = HERE.parent / "fourloops-plan.usda"
DEFAULT_CHART = HERE.parent / "fourloops-etnf.usda"

PRIM_RE = re.compile(r'^\s*def\s+(?:\w+\s+)?"([A-Za-z0-9_]+)"', re.M)
# A TYPELESS `def "Name"`, which is what a task is. Allowing `def Scope "Name"` here swept
# up the enclosing `def Scope "Tasks"` block, whose body starts with the first task's own
# `order`, so the first task was read under the name "Tasks" and its dependency edges
# disappeared. The negative control "a task needing one that runs later" is what found it.
ORDER_RE = re.compile(r'def\s+"([A-Za-z0-9_]+)"[^{]*\{(.*?)\n        \}', re.S)
INT_RE = re.compile(r"custom int (\w+) = (\d+)")
FLOAT_RE = re.compile(r"custom float (\w+) = ([\d.]+)")
REL_TARGET_RE = re.compile(r"</([A-Za-z0-9_/]+)>")
SOURCES_RE = re.compile(r"string\[\] sources = \[(.*?)\]", re.S)
# ONE DIRECTION SURVIVED THE CHART BECOMING A LAYER, AND THE OTHER WAS DELETED RATHER THAN
# LOOSENED. While the chart was HTML its `<code>` spans named relations, so "a name the chart
# uses that the plan does not have" was a real check. A layer has no `<code>`: reading every
# quoted lowercase token instead reported 29 problems on a clean pair -- `yaw`, `view_mean`,
# every column name -- because the two layers no longer share a namespace. The chart's prims
# are relations and the plan's are stages.
#
# What remains checkable is the direction that can still drift: a stage in the plan that the
# chart never mentions is a stage nobody described. That one is kept and its control kept
# with it.

# The relation names the chart is allowed to mention without the stage naming them: these
# are columns and vocabularies rather than pipeline stages, and the stage is a task graph.
# Listed rather than pattern-matched, because a pattern would quietly absorb a typo.
CHART_ONLY = {
    "loops", "models", "precisions", "instructions", "repair_arms", "runs", "rounds",
    "artifacts", "scores", "view_scores", "observed_points", "fit_residuals",
    "observations", "fits", "referee_verdicts", "joint_subset", "latents",
    "arm_selections", "arm_unavailable", "generations", "omnigen2_generations",
    "cyclegan_generations", "pixal3d_generations", "score_refusals", "overall",
    "instruction_id", "artifact_id", "run_id", "round_index", "repaired_from",
    "hammersley_index", "view_count", "checkpoint_sha256", "topology_id", "vertex_id",
    "joint_id", "region_id", "coco", "extract", "arm_id", "latent_id",
}


def load(path):
    return pathlib.Path(path).read_text(encoding="utf-8")


def prim_names(text):
    return set(PRIM_RE.findall(text))


def tasks(text):
    """(name, order, [needs targets]) for every prim carrying an `int order`."""
    out = []
    for name, body in ORDER_RE.findall(text):
        match = re.search(r"custom int order = (\d+)", body)
        if not match:
            continue
        needs = re.findall(r"rel needs = (?:\[(.*?)\]|(\S+))", body, re.S)
        targets = []
        for group, single in needs:
            targets += REL_TARGET_RE.findall(group or single or "")
        out.append((name, int(match.group(1)), targets))
    return out


def check_order(text, problems):
    entries = [(n, o, t) for n, o, t in tasks(text) if n.startswith("T")]
    orders = sorted(o for _, o, _ in entries)
    if orders != list(range(1, len(orders) + 1)):
        problems.append(f"task order values are {orders}, and must be 1..{len(orders)}")
    by_leaf = {n: o for n, o, _ in entries}
    for name, order, targets in entries:
        for target in targets:
            leaf = target.rsplit("/", 1)[-1]
            if leaf in by_leaf and by_leaf[leaf] >= order:
                problems.append(
                    f"{name} at order {order} needs {leaf} at order {by_leaf[leaf]}"
                )


def graph(text):
    """(stage prims, stages each loop references, tasks each task needs)."""
    stages, loops, needs = set(), {}, {}
    for name, body in ORDER_RE.findall(text):
        refs = REL_TARGET_RE.findall(body)
        if name.startswith("L") and name[1:2].isdigit():
            loops[name] = [r.rsplit("/", 1)[-1] for r in refs if "/Stages/" in r]
        elif name.startswith("T") and name[1:2].isdigit():
            needs[name] = [r.rsplit("/", 1)[-1] for r in refs if "/Tasks/" in r]
    start = text.find('def Scope "Stages"')
    if start == -1:
        return set(), loops, needs
    end = text.find('def Scope "', start + 10)
    block = text[start:end if end != -1 else len(text)]
    stages = set(re.findall(r'def\s+"([A-Za-z0-9_]+)"', block)) - {"Stages"}
    return stages, loops, needs


def check_dag(text, problems):
    """The graph is acyclic, nothing is orphaned, and every loop has a task.

    check_targets already proves each edge lands on a prim, which is not the same as the
    graph being sound: a stage no loop uses is dead weight nobody notices, and a loop no
    task realizes is work described and unscheduled. Both compose cleanly out of edges that
    all resolve, which is why this check is separate.

    NO CYCLE DETECTOR, AND THE REASON IS THAT ONE CANNOT FIRE HERE. A cycle in `needs`
    requires two tasks each waiting on the other, and `check_order` already requires every
    `needs` target to carry a strictly lower `order`. A cycle therefore cannot survive that
    rule, and a detector for it could not be driven by any input the rule accepts. One was
    written, its negative control was rejected by the order check rather than by the cycle
    check, and it was removed: a check no control can exercise is worse than decoration,
    because it reads in the output as though something were being verified.
    """
    stages, loops, needs = graph(text)

    used = {stage for refs in loops.values() for stage in refs}
    for orphan in sorted(stages - used):
        problems.append(f"stage {orphan!r} is referenced by no loop")
    for loop, refs in sorted(loops.items()):
        if not refs:
            problems.append(f"loop {loop!r} references no stage at all")

    realized = set()
    for name, body in ORDER_RE.findall(text):
        if name.startswith("T") and name[1:2].isdigit():
            realized |= {r.rsplit("/", 1)[-1] for r in REL_TARGET_RE.findall(body) if "/Loops/" in r}
    for loop in sorted(loops):
        if loop not in realized:
            problems.append(f"loop {loop!r} is realized by no task")


def check_targets(text, problems):
    known = prim_names(text) | {"FourLoops"}
    for target in set(REL_TARGET_RE.findall(text)):
        for part in target.split("/"):
            if part and part not in known:
                problems.append(f"relationship target </{target}> names no prim {part!r}")
                break


QUANTITIES_RE = re.compile(r'def Scope "Quantities"\s*\{(.*?)\n    \}', re.S)


def quantities(text):
    """Only the block under /FourLoops/Quantities.

    Scanning the whole layer for `custom int` swept up every task's `order`, and an order
    is not a measurement of anything outside this file. The first run of this self-test
    caught it: the clean case failed with "quantity order = 1 appears in no source".
    """
    match = QUANTITIES_RE.search(text)
    return match.group(1) if match else ""


def check_counts(text, root, problems):
    match = SOURCES_RE.search(text)
    if not match:
        problems.append("the layer states no sources, so no count can be checked")
        return
    corpus = []
    for line in match.group(1).splitlines():
        name = line.strip().strip(",").strip('"')
        if not name:
            continue
        path = pathlib.Path(root) / name
        if not path.is_file():
            problems.append(f"source {name} does not exist, so nothing checks against it")
            continue
        corpus.append(path.read_text(encoding="utf-8", errors="ignore").replace(",", ""))
    joined = "\n".join(corpus)
    block = quantities(text)
    for name, value in INT_RE.findall(block):
        if not re.search(rf"(?<![\d.]){re.escape(value)}(?![\d.])", joined):
            problems.append(f"quantity {name} = {value} appears in no source")
    # A float is matched with trailing zeros allowed, because USD prints 8.60 as 8.6 and
    # the source that measured it wrote "8.60 GiB". Requiring the exact characters made the
    # gate report a drift that was a print format, which is the convenient proxy rather
    # than the quantity.
    for name, value in FLOAT_RE.findall(block):
        pattern = rf"(?<![\d.]){re.escape(value)}0*(?![\d.])"
        if not re.search(pattern, joined):
            problems.append(f"quantity {name} = {value} appears in no source")


def check_chart(text, chart_text, problems):
    for prim in sorted(prim_names(text)):
        if prim in {"FourLoops", "Quantities", "Stages", "Loops", "Tasks"}:
            continue
        if prim.startswith("T") and prim[1:2].isdigit():
            continue
        if prim.startswith("L") and prim[1:2].isdigit():
            continue
        if prim.lower() not in chart_text.lower():
            problems.append(f"the stage has prim {prim!r} and the chart never mentions it")


def check(stage_path=DEFAULT_STAGE, chart_path=DEFAULT_CHART, root=None):
    problems = []
    text = load(stage_path)
    check_order(text, problems)
    check_targets(text, problems)
    check_dag(text, problems)
    if root is not None:
        check_counts(text, root, problems)
    chart = pathlib.Path(chart_path)
    if chart.is_file():
        check_chart(text, chart.read_text(encoding="utf-8"), problems)
    else:
        problems.append(f"{chart_path} is missing, and the chart is half of this pair")
    return problems


def workspace_root():
    """The `repo` client root: the first ancestor holding `.repo`.

    A search rather than a parent count, for the reason `check_rfd107a_plan.py` records:
    a hard-coded depth encodes where a project happens to sit today, and the manifest
    moves projects.
    """
    for candidate in [HERE, *HERE.parents]:
        if (candidate / ".repo").is_dir():
            return candidate
    return None


GOOD = """#usda 1.0
(
    defaultPrim = "FourLoops"
    customLayerData = {
        string[] sources = [
            "src.txt",
        ]
    }
)

def Scope "FourLoops"
{
    def Scope "Quantities"
    {
        custom int cocoKeypoints = 17
    }

    def Scope "Stages"
    {
        def "EditScore"
        {
            custom uniform token kind = "scorer"
        }
    }

    def Scope "Loops"
    {
        def "L1Only"
        {
            custom int order = 1
            rel score = </FourLoops/Stages/EditScore>
        }
    }

    def Scope "Tasks"
    {
        def "T01First"
        {
            custom int order = 1
            rel produces = </FourLoops/Stages/EditScore>
            rel realizes = </FourLoops/Loops/L1Only>
        }

        def "T02Second"
        {
            custom int order = 2
            rel needs = </FourLoops/Tasks/T01First>
        }
    }
}
"""
GOOD_CHART = "<p>editscore and <code>scores</code></p>\n"
GOOD_SOURCE = "the detector emits 17 joints\n"


def self_test():
    import shutil
    import tempfile

    def build(tmp, stage=GOOD, chart=GOOD_CHART, source=GOOD_SOURCE):
        root = pathlib.Path(tmp)
        (root / "stage.usda").write_text(stage, encoding="utf-8")
        (root / "chart.html").write_text(chart, encoding="utf-8")
        (root / "src.txt").write_text(source, encoding="utf-8")
        return root

    cases = [
        ("a clean pair passes", {}, False),
        ("an order that repeats",
         {"stage": GOOD.replace("custom int order = 2", "custom int order = 1")}, True),
        ("an order with a gap",
         {"stage": GOOD.replace("custom int order = 2", "custom int order = 3")}, True),
        ("a task needing one that runs later",
         {"stage": GOOD.replace("custom int order = 1", "custom int order = 9")
                      .replace("custom int order = 2", "custom int order = 1")
                      .replace("custom int order = 9", "custom int order = 2")}, True),
        ("a relationship target that names no prim",
         {"stage": GOOD.replace("</FourLoops/Stages/EditScore>", "</FourLoops/Stages/Nope>")}, True),
        ("a count that appears in no source",
         {"source": "the detector emits some joints\n"}, True),
        ("a source that does not exist",
         {"stage": GOOD.replace('"src.txt"', '"missing.txt"')}, True),
        ("a stage no loop references",
         {"stage": GOOD.replace("rel score = </FourLoops/Stages/EditScore>", "custom int spare = 0")}, True),
        ("a loop no task realizes",
         {"stage": GOOD.replace("rel realizes = </FourLoops/Loops/L1Only>", "custom int spare = 1")}, True),
        ("a stage prim the chart never mentions",
         {"chart": "a chart that mentions nothing"}, True),
    ]

    ok = True
    print("self-test: each known-bad input must be rejected")
    for label, kw, should_fail in cases:
        tmp = tempfile.mkdtemp()
        try:
            root = build(tmp, **kw)
            found = check(root / "stage.usda", root / "chart.html", root)
            failed = bool(found)
            if failed != should_fail:
                ok = False
            mark = "ok " if failed == should_fail else "BAD"
            detail = found[0] if found else ""
            print(f"  {mark} {label}: {'rejected' if failed else 'accepted'} {detail[:60]}")
        finally:
            shutil.rmtree(tmp)
    return 0 if ok else 1


def main(argv):
    if "--self-test" in argv:
        return self_test()
    stage = pathlib.Path(argv[1]) if len(argv) > 1 else DEFAULT_STAGE
    found = check(stage, DEFAULT_CHART, workspace_root())
    for line in found:
        print(line)
    print(f"{len(found)} problems")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
