"""Gate: every USD layer we write is valid, and survives a round trip through crate.

WHY THIS EXISTS. `rfd107a-plan.usda` opened in Python, composed without error, and read
back the ten tasks it was supposed to carry -- and it still failed usdchecker's own rules,
because it declared neither `upAxis` nor `metersPerUnit`. "It opens" is not "it is valid",
and the gap between the two is exactly where a layer that other tools reject sits looking
fine. RFD 1035 makes OpenUSD the internal format, so a layer nothing else will take is a
layer that has not been written yet.

THE THREE THINGS CHECKED, and why each is separate.

1. PARSE. `Sdf.Layer.FindOrOpen` on the file itself. A malformed layer fails here.
2. COMPOSE, then VALIDATE. `Usd.Stage.Open` reports composition errors; `UsdValidation`
   runs every registered validator, which is the machinery `usdchecker` drives. An Error
   fails the gate and a Warning is printed and counted -- named, never omitted.
3. ROUND TRIP. Export to `.usdc`, reopen, export back to `.usda`, and compare the two
   stages by content. A layer that parses but does not survive the binary format is not
   portable, and .usda is the source form here rather than the wire form.

WHAT THE ROUND-TRIP COMPARISON IGNORES, and why ignoring it is not a loophole. Exporting a
composed stage appends "Generated from Composed Stage of root layer <path>" to the layer's
documentation, so a naive string equality reports every file as broken. That line is an
artefact of the exporter, it names a temporary path, and comparing it would make the gate
fail on files that are fine. Everything else is compared: prim paths, types, specifiers,
metadata, every authored attribute name, type and value, and every relationship's targets.
The first version of this compared exported strings and reported the plan stage as
DIFFERING on nothing but that stamp.

WHERE THE TEMPORARIES GO. `.local` at the workspace root when it is there, which is what
CLAUDE.md asks for. In CI the logbook is checked out on its own and there is no workspace
root, so a temporary directory is used and the run says which it chose. A gate that cannot
run in CI is a gate nobody runs.

Usage:
    python check_usd_valid.py [path ...]      default: every USD file in the repo
    python check_usd_valid.py --self-test     the negative controls, each must FAIL

Exit code is non-zero on any invalid layer, and on any control that fails to fail.
"""

import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
SUFFIXES = (".usda", ".usdc", ".usd", ".usdz")


def scratch_dir():
    """`.local` at the workspace root, or a temporary directory when there is no root."""
    local = REPO.parent / ".local"
    if local.is_dir():
        return local, f"{local}"
    return pathlib.Path(tempfile.mkdtemp(prefix="usd-gate-")), "temporary directory (no .local)"


def discover():
    return sorted(p for p in REPO.rglob("*") if p.suffix.lower() in SUFFIXES and ".git" not in p.parts)


def snapshot(stage):
    """Everything about a stage that a round trip must preserve.

    Layer documentation is deliberately absent: `Export` appends its own provenance line to
    it, so including it would compare the exporter against itself and fail every file.
    """
    out = {
        "defaultPrim": stage.GetDefaultPrim().GetName(),
        "upAxis": stage.GetMetadata("upAxis"),
        "metersPerUnit": stage.GetMetadata("metersPerUnit"),
        "customLayerData": repr(stage.GetRootLayer().customLayerData),
        "prims": {},
    }
    for prim in stage.Traverse():
        entry = {
            "type": prim.GetTypeName(),
            "specifier": str(prim.GetSpecifier()),
            "doc": prim.GetMetadata("documentation"),
            "customData": repr(prim.GetCustomData()),
            "attrs": {},
            "rels": {},
        }
        for a in prim.GetAttributes():
            if a.HasAuthoredValue():
                entry["attrs"][a.GetName()] = (str(a.GetTypeName()), repr(a.Get()))
        for r in prim.GetRelationships():
            entry["rels"][r.GetName()] = [str(t) for t in r.GetTargets()]
        out["prims"][str(prim.GetPath())] = entry
    return out


def differences(a, b, path="stage"):
    """Every disagreement, not the first one. A gate that stops at one hides the rest."""
    diffs = []
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a:
                diffs.append(f"{path}.{key}: absent before, present after")
            elif key not in b:
                diffs.append(f"{path}.{key}: present before, absent after")
            else:
                diffs += differences(a[key], b[key], f"{path}.{key}")
    elif a != b:
        diffs.append(f"{path}: {a!r} -> {b!r}")
    return diffs


def check_one(path, scratch):
    from pxr import Sdf, Usd, UsdValidation

    name = path.name
    failures, warned = [], 0

    layer = Sdf.Layer.FindOrOpen(str(path))
    if not layer:
        print(f"  FAIL {name}: does not parse")
        return 1, 0

    stage = Usd.Stage.Open(str(path))
    for e in stage.GetCompositionErrors():
        failures.append(f"{name}: composition error: {e}")

    # The validators usdchecker drives. Loaded directly, because the console script is not
    # in the wheel -- and a check skipped for want of a binary reads exactly like a pass.
    results = UsdValidation.ValidationContext(
        UsdValidation.ValidationRegistry().GetOrLoadAllValidators()
    ).Validate(stage)
    for r in results:
        if "Error" in str(r.GetType()):
            failures.append(f"{name}: {r.GetMessage().strip()}")
        else:
            warned += 1
            print(f"  warn {name}: {r.GetMessage().strip()}")

    # Round trip. Both hops are exercised: text to binary, and binary back to text.
    crate = scratch / f"{path.stem}.roundtrip.usdc"
    back = scratch / f"{path.stem}.roundtrip.usda"
    try:
        stage.Export(str(crate))
        Usd.Stage.Open(str(crate)).Export(str(back))
        diffs = differences(snapshot(stage), snapshot(Usd.Stage.Open(str(back))))
    except Exception as exc:  # a layer that cannot be re-encoded is not portable
        diffs = [f"export raised {type(exc).__name__}: {exc}"]
    for d in diffs[:10]:
        failures.append(f"{name}: round trip changed {d}")
    for f in (crate, back):
        f.unlink(missing_ok=True)

    if failures:
        for f in failures:
            print(f"  FAIL {f}")
        return 1, warned
    print(f"  ok   {name}: parses, composes, validates, round-trips through crate unchanged")
    return 0, warned


def check(paths):
    scratch, where = scratch_dir()
    if not paths:
        print("  FAIL no USD files found. A gate over nothing certifies nothing.")
        return 1
    print(f"  ..   {len(paths)} file(s), scratch in {where}")
    rc, warned = 0, 0
    for p in paths:
        r, w = check_one(p, scratch)
        rc |= r
        warned += w
    if warned:
        print(f"  ..   {warned} warning(s) above, counted and not treated as failures")
    return rc


# --- negative controls --------------------------------------------------------------------
#
# Every file passing proves the files are fine. It does not prove this would notice if they
# were not, which is the only claim worth making. Each control breaks a copy a different way
# and each must make `check` fail.


def self_test():
    import contextlib
    import io

    from pxr import Usd

    scratch, where = scratch_dir()
    source = REPO / "rfd107a-plan.usda"
    if not source.exists():
        print(f"  FAIL self-test needs {source.name}, which is not here")
        return 1
    text = source.read_text(encoding="utf-8")

    def _syntax_error(dst):
        dst.write_text(text.replace('def Scope "Plan"', 'def Scope Plan"'), encoding="utf-8")

    def _no_up_axis(dst):
        """Drop `upAxis`. This is the defect that started the gate, so it is a control."""
        dst.write_text(text.replace('    upAxis = "Z"\n', ""), encoding="utf-8")

    def _no_meters_per_unit(dst):
        dst.write_text(text.replace("    metersPerUnit = 1\n", ""), encoding="utf-8")

    def _dangling_default_prim(dst):
        """Name a defaultPrim that is not in the layer."""
        dst.write_text(text.replace('defaultPrim = "Rfd107a"', 'defaultPrim = "NotHere"'),
                       encoding="utf-8")

    controls = [
        ("a syntax error", _syntax_error),
        ("no upAxis", _no_up_axis),
        ("no metersPerUnit", _no_meters_per_unit),
        ("a defaultPrim naming nothing", _dangling_default_prim),
    ]

    print("negative controls (each must FAIL):")
    bad = []
    for i, (label, mutate) in enumerate(controls):
        # A distinct filename per control. USD caches layers by identifier, so reusing one
        # hands the next control the previous one's layer -- `export_hm08_usd.py`'s
        # self-test was wrong that way, and every control still printed FAIL while three
        # of them were reporting the second one's defect.
        dst = scratch / f"control{i}.usda"
        dst.unlink(missing_ok=True)
        mutate(dst)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                rc = check([dst])
        except Exception as exc:
            # A raise is a rejection too, as long as it is the layer being rejected.
            rc, buf = 1, io.StringIO(f"  FAIL raised {type(exc).__name__}")
        dst.unlink(missing_ok=True)
        first = next((ln.strip() for ln in buf.getvalue().splitlines() if "FAIL" in ln), "")
        if rc:
            print(f"  ok   {label}: {first[:150]}")
        else:
            print(f"  BAD  {label}: passed, so this gate certifies the defect")
            bad.append(label)

    # The round-trip arm has no file-shaped control, because a layer that parses and then
    # changes under export is exactly the bug this looks for and cannot be written to order.
    # So the comparison is exercised directly: change one value and it must be reported.
    stage = Usd.Stage.Open(str(source))
    before = snapshot(stage)
    stage.GetPrimAtPath("/Rfd107a/Plan/T01_PoseLibraryPlausibility").GetAttribute("order").Set(4)
    if differences(before, snapshot(stage)):
        print("  ok   round-trip comparison notices a changed value")
    else:
        print("  BAD  round-trip comparison notices nothing, so the arm certifies anything")
        bad.append("round-trip comparison")

    # WHAT NONE OF THIS CATCHES, recorded because the control that was here first assumed
    # otherwise. Writing `custom int order = 1.5` does not fail: USD's text parser truncates
    # it to 1 silently, and `= 10` mangled the same way also becomes 1. The layer then
    # parses, validates and round-trips perfectly while carrying two tasks numbered 1.
    # Value corruption is invisible at the USD level by construction, which is the division
    # of labour with `check_rfd107a_plan.py` -- this gate says the layer is well formed, and
    # that one says the content means what it claims. It catches the duplicate.

    # And one positive control: an untouched copy must still pass, or the controls above
    # are firing on the copying rather than on the defect.
    clean = scratch / "control-clean.usda"
    clean.write_text(text, encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = check([clean])
    clean.unlink(missing_ok=True)
    if rc:
        print(f"  BAD  positive control: an unmodified copy failed -- {buf.getvalue().strip()}")
        bad.append("positive control")
    else:
        print("  ok   positive control: an unmodified copy still passes")

    if bad:
        print(f"\n{len(bad)} control(s) wrong. The gate is decoration until they are not.")
        return 1
    print(f"\nAll {len(controls) + 1} controls behaved.")
    return 0


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    if "--self-test" in argv[1:] and not args:
        return self_test()
    paths = [pathlib.Path(a) for a in args] or discover()
    print(f"checking {len(paths)} USD file(s)")
    rc = check(paths)
    if "--self-test" in argv[1:]:
        print()
        rc |= self_test()
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
