"""Check `fourloops-etnf.usda` against itself and against the code it describes.

WHY THIS EXISTS. The ETNF layer is a design written down: which relations exist, which
columns each carries, which stage writes it, and which columns are deliberately absent
because they are derivable. A design written down and never checked is a design that was
true the afternoon somebody typed it. `check_fourloops_plan.py` reads the task graph beside
this layer; nothing read the schema, so a relation could lose its writer, a foreign key
could point at a prim that had been renamed, and the four ETNF rules the layer argues for
could each be violated by the layer itself without a word.

A relationship whose target does not exist composes without complaint -- `Usd` reports no
error for it, and `usdchecker` does not either, which is why `check_usd_valid.py` passing is
not this file passing.

WHAT IT CHECKS, and why each is separate.

1. SHAPE. Every relation declares a `kind` drawn from `relationKindVocabulary` and a
   `columns` list, and every `state` is drawn from `stateVocabulary`. A vocabulary stated in
   a layer and gated nowhere is two vocabularies.

2. TARGETS RESOLVE. Every relationship target names a prim that exists. This is the dangling
   foreign key, and composition is blind to it.

3. NO DERIVABLE COLUMN IS STORED. Every column named under `Absent` appears in no relation's
   `columns`. The fourth ETNF rule is the one that rots quietly: somebody adds `yaw` beside
   `hammersley_index` for convenience, and the layer now stores a camera it also says it
   does not store.

4. EVERY EMITTED RELATION HAS EXACTLY ONE WRITER. Every relation of kind `spine`,
   `satellite` or `measured` is the target of exactly one `writes` under `StageWrites`.
   Interned vocabularies are exempt, which is what interned means. A relation two stages
   write is a relation with no owner; one nothing writes is a relation that does not exist
   yet, however carefully its columns are described. This check is what found
   `ArmUnavailable`, which the layer described and no stage wrote.

5. COUNTS ARE NOT ONLY HERE. Every number in the layer is searched for in the sources the
   layer names, commas stripped, as a whole token. A count that lives only in the design is
   a count nobody reviewed. Same pattern as `check_fourloops_plan.py` and, before it,
   `check-rfd-structure.py` for RFD 1000.

   THE DETECTION FLOOR, stated because a check that cannot fail reads exactly like one that
   passed: integers below `SEARCH_FLOOR` are not searched, and the ones skipped are printed
   rather than omitted. `4` appears in every Python file ever written, so searching for it
   certifies nothing. Floats are searched whatever their magnitude, because `0.263` is a
   measurement where `4` is usually a row count.

WHAT IT DOES NOT CHECK. Whether the schema is a good schema, and whether any of these
relations exists in a database -- nothing builds one yet. Only that the design is
self-consistent and that its numbers came from somewhere a person can read.

    python check_fourloops_etnf.py [layer.usda] [--self-test]

Exit code is non-zero on any failure, and on any negative control that fails to fail.
"""

import pathlib
import re
import sys

from pxr import Usd

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_LAYER = HERE.parent / "fourloops-etnf.usda"

# The scopes holding relations. Naming them rather than treating every scope as relations
# keeps a prose scope from being read as a set of relations with no columns, which would
# report four failures about nothing.
RELATION_SCOPES = ("Interned", "Spine", "Satellites", "Measured")

# Kinds something else emits, and which therefore need a writing stage. `interned` is absent
# on purpose: an interned vocabulary is typed once by a person.
EMITTED_KINDS = ("spine", "satellite", "measured")

SEARCH_FLOOR = 10


def open_layer(path):
    stage = Usd.Stage.Open(str(path))
    if stage is None:
        raise SystemExit(f"{path} does not open")
    if not stage.GetDefaultPrim():
        raise SystemExit(f"{path} has no defaultPrim, so there is nothing to read")
    return stage


def section(stage, name):
    """The child prims of one scope under the default prim, in layer order."""
    scope = stage.GetDefaultPrim().GetChild(name)
    return list(scope.GetChildren()) if scope else []


def relations(stage):
    """Every relation prim, keyed by its path."""
    out = {}
    for scope in RELATION_SCOPES:
        for prim in section(stage, scope):
            out[str(prim.GetPath())] = prim
    return out


def attr(prim, name, default=None):
    a = prim.GetAttribute(name)
    return a.Get() if a and a.HasAuthoredValue() else default


def column_names(prim):
    """The bare name of each declared column: "run_id int64 FK" is run_id."""
    return [str(c).split()[0] for c in (attr(prim, "columns") or []) if str(c).strip()]


def walk(stage):
    for prim in stage.Traverse():
        yield prim


def check_shape(stage, problems):
    layer = stage.GetRootLayer().customLayerData
    kinds = set(layer.get("relationKindVocabulary", []))
    states = set(layer.get("stateVocabulary", []))
    for path, prim in sorted(relations(stage).items()):
        kind = attr(prim, "kind")
        if kind is None:
            problems.append(f"{path} declares no kind")
        elif str(kind) not in kinds:
            problems.append(f"{path} has kind {str(kind)!r}, which is not in relationKindVocabulary")
        if not attr(prim, "columns"):
            problems.append(f"{path} declares no columns")
    for prim in walk(stage):
        state = attr(prim, "state")
        if state is not None and str(state) not in states:
            problems.append(
                f"{prim.GetPath()} has state {str(state)!r}, which is not in stateVocabulary"
            )


def check_targets(stage, problems):
    for prim in walk(stage):
        for rel in prim.GetRelationships():
            for target in rel.GetTargets():
                if not stage.GetPrimAtPath(target):
                    problems.append(
                        f"{prim.GetPath()}.{rel.GetName()} targets <{target}>, which is no prim"
                    )


def check_derivable_not_stored(stage, problems):
    stored = {}
    for path, prim in relations(stage).items():
        for name in column_names(prim):
            stored.setdefault(name, path)
    for prim in section(stage, "Absent"):
        for name in attr(prim, "columns") or []:
            if str(name) in stored:
                problems.append(
                    f"{prim.GetPath()} says {str(name)!r} is absent because derivable, "
                    f"and {stored[str(name)]} stores it"
                )


def check_writers(stage, problems):
    written = {}
    for prim in section(stage, "StageWrites"):
        rel = prim.GetRelationship("writes")
        for target in (rel.GetTargets() if rel else []):
            written.setdefault(str(target), []).append(prim.GetName())
    for path, prim in sorted(relations(stage).items()):
        if str(attr(prim, "kind")) not in EMITTED_KINDS:
            continue
        writers = written.get(path, [])
        if not writers:
            problems.append(f"{path} is emitted and no stage writes it")
        elif len(writers) > 1:
            problems.append(f"{path} is written by {len(writers)} stages: {', '.join(writers)}")


def numbers(stage):
    """(where, printed value, is_int) for every authored number in the layer.

    A bool is an int in Python and is skipped: `confirmed = 1` is a flag, and searching the
    sources for "1" would pass against any file at all.
    """
    found = []
    for prim in walk(stage):
        for a in prim.GetAttributes():
            if not a.HasAuthoredValue():
                continue
            value = a.Get()
            where = f"{prim.GetPath()}.{a.GetName()}"
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                found.append((where, str(value), True))
            elif isinstance(value, float):
                found.append((where, repr(round(value, 6)).rstrip("0").rstrip("."), False))
    return found


def check_counts(stage, root, problems):
    named = list(stage.GetRootLayer().customLayerData.get("sources", []))
    if not named:
        problems.append("the layer states no sources, so no count can be checked")
        return
    corpus = []
    for name in named:
        path = pathlib.Path(root) / str(name)
        if not path.is_file():
            problems.append(f"source {name} does not exist, so nothing checks against it")
            continue
        corpus.append(path.read_text(encoding="utf-8", errors="ignore").replace(",", ""))
    joined = "\n".join(corpus)
    skipped = []
    for where, value, is_int in numbers(stage):
        if value.startswith("-"):
            continue
        if is_int and int(value) < SEARCH_FLOOR:
            skipped.append(f"{where.rsplit('/', 1)[-1]}={value}")
            continue
        # Trailing zeros are allowed on a float because USD prints 8.60 as 8.6 and the
        # source that measured it wrote "8.60 GiB". Requiring the exact characters made the
        # plan gate report a print format as a drift, which is the convenient proxy rather
        # than the quantity.
        pattern = rf"(?<![\d.]){re.escape(value)}{'' if is_int else '0*'}(?![\d.])"
        if not re.search(pattern, joined):
            problems.append(f"{where} = {value} appears in no source")
    if skipped:
        print(f"  below the search floor of {SEARCH_FLOOR}, not searched: {', '.join(skipped)}")


def check(layer_path=DEFAULT_LAYER, root=None):
    problems = []
    stage = open_layer(layer_path)
    check_shape(stage, problems)
    check_targets(stage, problems)
    check_derivable_not_stored(stage, problems)
    check_writers(stage, problems)
    if root is not None:
        check_counts(stage, root, problems)
    return problems


def workspace_root():
    """The `repo` client root: the first ancestor holding `.repo`.

    A search rather than a parent count, for the reason `check_rfd107a_plan.py` records: a
    hard-coded depth encodes where a project happens to sit today, and the manifest moves
    projects.
    """
    for candidate in [HERE, *HERE.parents]:
        if (candidate / ".repo").is_dir():
            return candidate
    return None


GOOD = """#usda 1.0
(
    defaultPrim = "Etnf"
    metersPerUnit = 1
    upAxis = "Z"
    customLayerData = {
        string[] sources = ["src.txt"]
        string[] relationKindVocabulary = ["interned", "spine", "satellite", "measured"]
        string[] stateVocabulary = ["exists", "stub"]
    }
)

def Scope "Etnf"
{
    def Scope "Interned"
    {
        def "Joints"
        {
            custom uniform token kind = "interned"
            custom string[] columns = ["joint_id int8 PK"]
            custom int rowCount = 17
        }
    }

    def Scope "Measured"
    {
        def "Scores"
        {
            custom uniform token kind = "measured"
            custom string[] columns = ["joint_id int8 FK", "overall float32"]
            rel foreignKeys = </Etnf/Interned/Joints>
        }
    }

    def Scope "Absent"
    {
        def "ScoreDelta"
        {
            custom string[] columns = ["delta"]
            custom string derivedFrom = "overall minus baseline"
            rel wouldHaveSatOn = </Etnf/Measured/Scores>
        }
    }

    def Scope "StageWrites"
    {
        def "EditScore"
        {
            custom uniform token state = "exists"
            rel writes = </Etnf/Measured/Scores>
        }
    }
}
"""
GOOD_SOURCE = "the detector emits 17 joints\n"

SECOND_WRITER = """
        def "Referee"
        {
            custom uniform token state = "exists"
            rel writes = </Etnf/Measured/Scores>
        }
"""


def self_test():
    import shutil
    import tempfile

    cases = [
        ("a clean layer passes", {}, False),
        ("a relationship target that names no prim",
         {"layer": GOOD.replace("</Etnf/Interned/Joints>", "</Etnf/Interned/Nope>")}, True),
        ("a derivable column stored anyway",
         {"layer": GOOD.replace('"overall float32"', '"overall float32", "delta float32"')}, True),
        ("an emitted relation nothing writes",
         {"layer": GOOD.replace("rel writes = </Etnf/Measured/Scores>", "custom int spare = 0")}, True),
        ("an emitted relation two stages write",
         {"layer": GOOD.replace('        def "EditScore"', SECOND_WRITER + '        def "EditScore"')}, True),
        ("a kind outside the vocabulary",
         {"layer": GOOD.replace('kind = "measured"', 'kind = "emitted"')}, True),
        ("a state outside the vocabulary",
         {"layer": GOOD.replace('state = "exists"', 'state = "shipped"')}, True),
        ("a relation with no columns",
         {"layer": GOOD.replace('custom string[] columns = ["joint_id int8 PK"]\n', "")}, True),
        ("a count that appears in no source",
         {"source": "the detector emits some joints\n"}, True),
        ("a source that does not exist",
         {"layer": GOOD.replace('"src.txt"', '"missing.txt"')}, True),
    ]

    ok = True
    print("self-test: each known-bad input must be rejected")
    for label, kw, should_fail in cases:
        tmp = tempfile.mkdtemp()
        try:
            root = pathlib.Path(tmp)
            (root / "layer.usda").write_text(kw.get("layer", GOOD), encoding="utf-8")
            (root / "src.txt").write_text(kw.get("source", GOOD_SOURCE), encoding="utf-8")
            found = check(root / "layer.usda", root)
            failed = bool(found)
            if failed != should_fail:
                ok = False
            mark = "ok " if failed == should_fail else "BAD"
            detail = found[0] if found else ""
            print(f"  {mark} {label}: {'rejected' if failed else 'accepted'} {detail[:64]}")
        finally:
            shutil.rmtree(tmp)
    return 0 if ok else 1


def main(argv):
    if "--self-test" in argv:
        return self_test()
    layer = pathlib.Path(argv[1]) if len(argv) > 1 else DEFAULT_LAYER
    found = check(layer, workspace_root())
    for line in found:
        print(line)
    print(f"{len(found)} problems")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
