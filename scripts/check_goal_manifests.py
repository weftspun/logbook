"""Gate: every goal manifest CLAUDE.md names as live is actually live.

WHY THIS EXISTS. The Sides rule decides where a repository is placed, and it decides it by
NAMING a manifest. That name has now gone stale twice. `weftspun/weftspun` was archived and the
rule went on naming it, which `KEYPOINTS.md` records two agents fixing independently within an
hour. The replacement wording named two manifests, `weftspun-mesh-latents` was archived on
2026-08-22, and the rule went on naming that one for two days -- in a paragraph that states
exactly the test it was failing.

Twice is a class, not an instance. CLAUDE.md's own obligation covers it: where a document states
a rule, that statement should be machine-checked against live code, so drift fails a command
rather than being discovered six months later.

WHAT IT CHECKS. Every `weftspun/<name>` in the Sides rule that the prose calls live, against the
organisation's archived set. An archived repository named as live is a FAIL.

WHAT IT DOES NOT CHECK. Whether the named manifest is the RIGHT one, or whether a project inside
it is placed correctly. It answers one question -- is this name still a live manifest -- which is
the question that rotted.

Usage:
    python check_goal_manifests.py [--self-test]
"""

import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
CLAUDE_MD = HERE.parent / "CLAUDE.md"
ORG = "weftspun"


def sides_rule(text):
    """The Sides paragraph only. A manifest named in a RETRACTION is not a claim that it lives."""
    m = re.search(r"\*\*Sides\.\*\*(.*?)(?=\n\*\*[A-Z])", text, re.S)
    return m.group(1) if m else ""


def named_live(text):
    """Manifests the rule presents as live: those in the sentence naming the live manifest(s).

    A name inside a retraction paragraph is deliberately NOT collected. Those paragraphs exist to
    say a manifest is archived, and reading them as claims would make the gate fire on the very
    sentences that record the fix.
    """
    para = sides_rule(text).split("\n\n")[0]
    return sorted(set(re.findall(rf"`{ORG}/([a-z0-9._-]+)`", para)))


def archived_repos():
    out = subprocess.run(
        ["gh", "repo", "list", ORG, "--limit", "500", "--json", "name,isArchived"],
        capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        return None, out.stderr.strip().splitlines()[-1:] or ["gh failed"]
    return {r["name"] for r in json.loads(out.stdout) if r["isArchived"]}, None


def check(text=None):
    text = text if text is not None else CLAUDE_MD.read_text(encoding="utf-8")
    live = named_live(text)
    if not live:
        print("  FAIL the Sides rule names no goal manifest at all")
        return 1

    archived, err = archived_repos()
    if archived is None:
        # UNCHECKED IS A FAIL, NOT A SKIP. A gate that goes quiet when the network is down
        # reports the same thing as a gate that passed, which is the failure PITFALLS 3 names.
        print(f"  FAIL UNCHECKED: could not read {ORG}'s archived set -- {err[0]}")
        return 1

    bad = [n for n in live if n in archived]
    for n in bad:
        print(f"  FAIL the Sides rule names {ORG}/{n} as live, and it is archived")
    if bad:
        return 1
    print(f"  ok   {len(live)} goal manifest(s) named live, none archived: "
          f"{', '.join(live)}")
    return 0


def self_test():
    """Each control must make `check` fail. A gate with none certifies whatever it is given."""
    real = CLAUDE_MD.read_text(encoding="utf-8")
    archived, err = archived_repos()
    if archived is None:
        print(f"  FAIL UNCHECKED: {err[0]}")
        return 1
    victim = sorted(archived)[0]

    controls = [
        ("an archived manifest is named as live",
         real.replace("`weftspun/weftspun-keypoint`", f"`{ORG}/{victim}`", 1)),
        # MUTATE THE PARAGRAPH THE GATE READS, NOT THE FIRST MATCH IN THE FILE. The first
        # version of this control substituted with count=1 over the whole document and landed on
        # an unrelated `weftspun/...` mention hundreds of lines earlier, leaving the Sides rule
        # untouched -- so it reported green while changing nothing the gate looks at. A control
        # aimed at the wrong text is indistinguishable from a gate that cannot fail.
        ("the rule names no manifest",
         real.replace(sides_rule(real).split("\n\n")[0],
                      re.sub(rf"`{ORG}/[a-z0-9._-]+`", "the manifest",
                             sides_rule(real).split("\n\n")[0]), 1)),
    ]
    bad = []
    print("negative controls (each must FAIL):")
    for label, mutated in controls:
        import contextlib, io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = check(mutated)
        first = next((l.strip() for l in buf.getvalue().splitlines() if "FAIL" in l), "")
        if rc:
            print(f"  ok   {label}: {first}")
        else:
            print(f"  BAD  {label}: passed, so this gate certifies the defect")
            bad.append(label)
    if bad:
        print(f"\n{len(bad)} control(s) did not fire. The gate is decoration until they do.")
        return 1
    print(f"\nAll {len(controls)} controls fired.")
    return 0


if __name__ == "__main__":
    rc = check()
    if "--self-test" in sys.argv[1:]:
        print()
        rc |= self_test()
    sys.exit(rc)
