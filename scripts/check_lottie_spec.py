"""Does the animation this workspace writes actually conform to Lottie?

WHY THIS EXISTS. `keypoint_render.py` emits a file and calls it Lottie, which is a claim about
somebody else's specification and therefore exactly the kind of statement that should fail a
command rather than be discovered by a player refusing to open it. It did not conform when
first written: 207 errors, one per shape layer, and the two defects behind them are the controls
below.

THE SCHEMA IS VENDORED, WITH ITS PROVENANCE. Fetched 2026-08-23 from

    https://lottie.github.io/lottie-spec/1.0/lottie.schema.json

built by the spec's own Makefile from `schema/root.json`. A copy rather than a fetch because a
gate that needs the network fails for reasons that have nothing to do with the file under test.
Re-fetch deliberately when the spec version moves; the version is in the path.

WHAT PLAYERS TOLERATE IS NOT WHAT THE SPEC ALLOWS, which is the whole reason this is worth
running. Both defects it caught render correctly in lottie-web.
"""
import json
import pathlib
import sys

SCHEMA = pathlib.Path(__file__).with_name("lottie.schema.json")


def errors(doc, schema):
    from jsonschema.validators import validator_for
    return list(validator_for(schema)(schema).iter_errors(doc))


def check(path, schema):
    doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    errs = errors(doc, schema)
    if errs:
        from jsonschema.exceptions import best_match
        print(f"  FAIL {path}: {len(errs)} error(s)")
        for e in errs[:5]:
            bm = best_match([e])
            print(f"        {'/'.join(str(x) for x in bm.absolute_path)}: {bm.message[:110]}")
        return 1, doc
    print(f"  ok   {path}: conforms, {len(doc['layers'])} layers, {len(doc.get('assets', []))} assets")
    return 0, doc


def self_test(doc, schema):
    """Each control reintroduces a defect this gate found, and must fail.

    A validator that cannot fail certifies nothing, and these two are not hypothetical: they are
    what the first version of the writer produced.
    """
    import copy

    def drop_terminal_value(d):
        """lottie-web writes a bare {"t": n} terminator; the spec requires `s` on every keyframe."""
        for lay in d["layers"]:
            for it in lay.get("shapes", [{}])[0].get("it", []):
                if it.get("ty") == "el" and isinstance(it["p"].get("k"), list):
                    it["p"]["k"][-1].pop("s", None)
                    return d
        raise AssertionError("no ellipse keyframe to break")

    def unwrap_scalar(d):
        """A scalar keyframe's `s` is an array even for one number."""
        for lay in d["layers"]:
            for it in lay.get("shapes", [{}])[0].get("it", []):
                if it.get("ty") == "fl" and isinstance(it["o"].get("k"), list):
                    it["o"]["k"][0]["s"] = it["o"]["k"][0]["s"][0]
                    return d
        raise AssertionError("no scalar keyframe to break")

    controls = [("a keyframe with no value", drop_terminal_value),
                ("a scalar keyframe not wrapped in an array", unwrap_scalar)]
    print("negative controls (each must FAIL):")
    bad = []
    for label, mutate in controls:
        broken = mutate(copy.deepcopy(doc))
        n = len(errors(broken, schema))
        if n:
            print(f"  ok   {label}: rejected, {n} error(s)")
        else:
            print(f"  BAD  {label}: accepted, so this gate certifies the defect")
            bad.append(label)
    return 1 if bad else 0


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    if not args:
        print("usage: check_lottie_spec.py <animation.json> [--self-test]")
        return 2
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    rc, doc = check(args[0], schema)
    if "--self-test" in argv[1:]:
        print()
        rc |= self_test(doc, schema)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
