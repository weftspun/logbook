"""Gate: README.md carries no index of the files beside it.

WHY THIS EXISTS. A hand-written index of a directory is a second copy of `ls`, and the two
disagree the first time somebody adds a file and forgets the table. Nothing reports that.
The directory is the index, `git ls-files` is the index, and a table claiming to be one is
a claim that goes stale silently -- which is the same failure the `.local` rule, the
manifest rule and the submodule rule are all written against: a second place a fact lives,
visible to nothing that checks.

The immediate provocation was an agent adding two rows to this repository's README for
files it had just written. The rows were accurate that afternoon. That is exactly the
problem: an index is accurate when it is written and unpoliced afterwards, so it decays
into a confident, wrong answer about what is here.

WHAT COUNTS AS AN INDEX ROW. A markdown table row, or a list item, whose FIRST cell names
a file or a directory -- in backticks or as a link. Two shapes, both of them indexes:

    | `todo.md`  | the running logbook |
    - [todo.md](todo.md) - the running logbook

WHAT DOES NOT COUNT, and this distinction is the whole reason the check reads the first
cell rather than grepping for filenames. Prose that names a file is fine: "an entry records
what was measured" needs to be able to say `check_comment_density.py` without tripping a
gate. So does a table whose subject is something other than the file tree -- a table of
measurements with a filename in a later column stays legal.

WHETHER THE FILE EXISTS IS NOT THE TEST. A row pointing at a file that is present is an
index that will rot; a row pointing at one that is gone has rotted already. Both fail, and
for the same reason, so existence is never consulted.

Usage:
    python check_readme_no_index.py [path ...]     default: README.md in this repository
    python check_readme_no_index.py --self-test    the controls, each must FAIL

Exit code is non-zero if any index row is found, and on any control that fails to fail.
"""

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
DEFAULT = REPO / "README.md"

# A path-shaped token: `todo.md`, `scripts/`, [x](y.py). Extensions are not enumerated,
# because the next file here will have one nobody listed.
BACKTICKED = re.compile(r"^`([^`]+)`$")
LINKED = re.compile(r"^\[[^\]]*\]\(([^)]+)\)$")
PATHLIKE = re.compile(r"^[\w.\-/]+(\.\w+|/)$")


def first_cell(line):
    """The first cell of a table row, or the first token of a list item. None otherwise."""
    stripped = line.strip()
    if stripped.startswith("|"):
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        return cells[0] if cells else None
    if re.match(r"^[-*+]\s+\S", stripped):
        rest = stripped[1:].strip()
        # Up to the first separator a row uses between name and description.
        return re.split(r"\s+[-–—:]\s+|\s{2,}", rest)[0].strip()
    return None


def names_a_file(cell):
    if not cell:
        return None
    for pattern in (BACKTICKED, LINKED):
        m = pattern.match(cell)
        if m and PATHLIKE.match(m.group(1)):
            return m.group(1)
    return None


def check(paths):
    if not paths:
        print("  FAIL nothing to check. A gate over no files certifies nothing.")
        return 1
    rc = 0
    for path in paths:
        if not path.exists():
            print(f"  FAIL {path} does not exist")
            rc = 1
            continue
        found = []
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            target = names_a_file(first_cell(line))
            if target:
                found.append((n, target, line.strip()[:70]))
        if found:
            for n, target, text in found:
                print(f"  FAIL {path.name}:{n} indexes `{target}`: {text}")
            print(f"       {len(found)} index row(s). The directory is the index; delete these.")
            rc = 1
        else:
            print(f"  ok   {path.name}: no index rows")
    return rc


# --- controls -----------------------------------------------------------------------------
#
# The README passing proves the README is clean. It does not prove this would notice a row,
# which is the only claim worth making. Three must fail and two must pass -- the passing
# ones matter as much, because a gate that rejects prose about a filename is a gate people
# route around.


def self_test():
    import contextlib
    import io
    import tempfile

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="readme-gate-"))
    cases = [
        ("a table row naming a file", False,
         "# Logbook\n\n| file | what it holds |\n| ---- | ------------- |\n"
         "| `todo.md` | the running logbook |\n"),
        ("a table row naming a directory", False,
         "# Logbook\n\n| `scripts/` | the apparatus behind the entries |\n"),
        ("a list item indexing a file", False,
         "# Logbook\n\n- [todo.md](todo.md) - the running logbook\n"),
        ("a row pointing at a file that is gone", False,
         "# Logbook\n\n| `deleted-last-year.md` | nothing, any more |\n"),
        # The two that must pass. A filename in a sentence is not an index, and neither is
        # a table about something else that happens to mention one.
        ("prose naming a file", True,
         "# Logbook\n\nAn entry clips its apparatus, which is what `check_comment_density.py`\n"
         "measures.\n"),
        ("a measurements table mentioning a file", True,
         "# Logbook\n\n| measurement | source |\n| ----------- | ------ |\n"
         "| 3.7% median | `servers/` at 4.7.0-beta |\n"),
    ]

    print("controls:")
    bad = []
    for i, (label, should_pass, text) in enumerate(cases):
        # A distinct filename per case, so no case can be handed another's file.
        dst = tmp / f"case{i}-README.md"
        dst.write_text(text, encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = check([dst])
        first = next((ln.strip() for ln in buf.getvalue().splitlines() if "FAIL" in ln), "")
        passed = rc == 0
        if passed == should_pass:
            mark, detail = "ok  ", "passes, correctly" if passed else f"fails: {first[:88]}"
        else:
            mark, detail = "BAD ", ("passed and should not have" if passed else
                                    f"failed and should not have: {first[:70]}")
            bad.append(label)
        dst.unlink()
        print(f"  {mark} {label}: {detail}")

    if bad:
        print(f"\n{len(bad)} control(s) wrong. The gate is decoration until they are not.")
        return 1
    print(f"\nAll {len(cases)} controls behaved.")
    return 0


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    if "--self-test" in argv[1:] and not args:
        return self_test()
    rc = check([pathlib.Path(a) for a in args] or [DEFAULT])
    if "--self-test" in argv[1:]:
        print()
        rc |= self_test()
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
