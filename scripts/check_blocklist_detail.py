#!/usr/bin/env python3
"""Gate: a blocklist row without its argument, or an argument without its row.

WHY THIS EXISTS. `CLAUDE.md` used to carry the blocklist table and 592 lines of reasoning
behind it in one document, which put the argument for excluding FLUX.1 between a reader and
the next working agreement. The reasoning now lives in `BLOCKLIST.md`, one section per row.

Splitting a document creates the failure this gate is written against. A row can lose its
argument -- somebody adds an entry, writes "see below", and no section follows. An argument can
outlive its row -- somebody lifts an entry from the table and the section defending it stays,
so the next reader finds a case for a rule that no longer exists. Neither shows up in a diff of
the file you are editing, because the other file is the one that changed.

WHAT IS CHECKED, in both directions:

1. Every table row saying "see below" resolves to a section in `BLOCKLIST.md`.
2. Every section in `BLOCKLIST.md` corresponds to a row in the table.

MATCHING IS ON SUBJECT, NOT ON TITLE, and that is the whole difficulty. A row reads
`**Qwen-Image-Edit** (2509/2511)` and its section reads "Qwen-Image-Edit corrupts at the only
precision this desk can run it". The titles are prose and will never equal the cells. So a row
is matched by asking whether its distinctive tokens appear in some section title -- which is
loose, and the detection floor below says what that costs.

THE DETECTION FLOOR. A section whose title shares no token with its row is reported as
unmatched even when a human would pair them; that is a false alarm, and the fix is to name the
subject in the title, which is worth doing anyway. Two rows whose subjects share tokens can
match the same section, so a duplicated argument is not caught. The gate is a wire, not a
proof.

Usage:
    python scripts/check_blocklist_detail.py [<dir>]
    python scripts/check_blocklist_detail.py --self-test

Exit codes: 0 the two agree, 1 they do not, 2 bad usage.
"""
from __future__ import annotations

import pathlib
import re
import sys

#: Words too common to identify a subject. Matching on these pairs anything with anything.
# FUNCTION WORDS ONLY. A first version also excluded corpus, generator, model, source and
# weights as "too common", and those are precisely the words that distinguish these rows --
# it left `hosted-API generators as a corpus source` unable to match `A corpus generator must
# be a checkpoint we hold`, which is its section. Domain words stay; matching is tightened by
# stemming instead.
STOPWORDS = {
    "a", "an", "and", "as", "at", "the", "is", "it", "its", "for", "from", "in", "into", "no",
    "not", "of", "on", "or", "to", "with", "that", "this", "which", "why", "what", "we",
    "use", "only", "here", "own", "are", "was", "were", "must", "be", "has", "have", "than",
}


def tokens(text):
    """Distinctive lowercase stems, markdown stripped.

    STEMS, NOT WORDS. The table says `abliterated weights` and the section says "Abliteration
    is blocked"; those share no whole word. Truncating to six characters pairs them without
    dragging in a stemmer, and short tokens are kept whole so `uv` and `flux` still match.
    """
    text = re.sub(r"[*_`]", " ", text.lower())
    raw = [t for t in re.findall(r"[a-z0-9][a-z0-9.\-]{2,}", text) if t not in STOPWORDS]
    return {t[:6] for t in raw}


def table_rows(claude_md):
    """Rows of the blocklist table that promise an argument elsewhere.

    Only rows saying "see below" are required to have one; a row whose one-line reason is the
    whole reason -- `CMU mocap | provenance` -- needs no section and is not asked for one.
    """
    rows = []
    for line in claude_md.split("\n"):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2 or set(cells[0]) <= set("- "):
            continue
        if cells[0].lower().startswith("source"):
            continue
        if "see below" in line.lower():
            rows.append((cells[0], tokens(cells[0])))
    return rows


def detail_sections(blocklist_md):
    return [(m, tokens(m)) for m in re.findall(r"^### (.+)$", blocklist_md, re.M)]


def check(claude_md, blocklist_md):
    """Returns a list of problems. Empty means the two documents agree."""
    rows = table_rows(claude_md)
    sections = detail_sections(blocklist_md)
    problems = []

    if not rows:
        problems.append(
            "no blocklist row says 'see below' -- either the table lost its promises or this "
            "gate is looking at the wrong document, and both are worth stopping for"
        )
    if not sections:
        problems.append("BLOCKLIST.md has no ### sections; the detail document is empty")

    # BEST MATCH, ONE TO ONE, and a first version took the first match instead. Several rows
    # share the stem `genera`, so `hosted-API generators as a corpus source` claimed the depth
    # conditioning section and the section that was actually its own was reported orphaned.
    # Pairs are scored by how many stems they share and assigned strongest first, each section
    # spoken for once.
    scored = sorted(
        (
            (len(row_tokens & sec_tokens), r, i)
            for r, (_, row_tokens) in enumerate(rows)
            for i, (_, sec_tokens) in enumerate(sections)
            if row_tokens & sec_tokens
        ),
        reverse=True,
    )

    matched, claimed_by = set(), {}
    for _score, r, i in scored:
        if r in claimed_by or i in matched:
            continue
        claimed_by[r] = i
        matched.add(i)

    for r, (label, _) in enumerate(rows):
        if r not in claimed_by:
            problems.append(
                "row %r says 'see below' and no unclaimed section in BLOCKLIST.md shares a "
                "word with it" % label
            )

    for i, (title, _) in enumerate(sections):
        if i not in matched:
            problems.append(
                "section %r matches no blocklist row -- either the row was lifted and its "
                "argument left behind, or the title names no subject" % title
            )
    return problems


def self_test():
    """Controls. Each broken input must FAIL, or the gate certifies the drift."""
    good_table = (
        "| source | reason |\n| --- | --- |\n"
        "| **Blender** | renders are not reproducible -- see below |\n"
        "| CMU mocap | provenance |\n"
    )
    good_detail = "### Blender is blocklisted, and reproducibility is why\n\nbody\n"

    cases = [
        ("a row with its section, and a row needing none", good_table, good_detail, True),
        (
            "a row promising an argument that does not exist",
            good_table + "| **Krea 2** | revenue-gated -- see below |\n",
            good_detail,
            False,
        ),
        (
            "a section whose row was lifted from the table",
            good_table,
            good_detail + "\n### Krea 2 is revenue-gated, and that propagates\n\nbody\n",
            False,
        ),
        (
            "a row matched only by a stopword must NOT count as matched",
            "| source | reason |\n| --- | --- |\n| **the model** | see below |\n",
            "### Blender is blocklisted, and reproducibility is why\n",
            False,
        ),
        ("an empty detail document", good_table, "", False),
        ("a table with no promises at all", "| source | reason |\n| --- | --- |\n", good_detail, False),
    ]

    print("controls:")
    bad = 0
    for label, table, detail, want_ok in cases:
        problems = check(table, detail)
        ok = (problems == []) == want_ok
        print("  %s %s" % ("ok  " if ok else "BAD ", label))
        if problems and not want_ok is False:
            pass
        if not ok:
            bad += 1
            print("        got: %s" % (problems[:1] or "no problems"))
    print("\n%d control(s) wrong" % bad)
    return 1 if bad else 0


def main(argv):
    if "--self-test" in argv:
        return self_test()

    root = pathlib.Path(argv[1] if len(argv) > 1 else ".")
    claude, block = root / "CLAUDE.md", root / "BLOCKLIST.md"
    for p in (claude, block):
        if not p.exists():
            print("FAIL: %s does not exist" % p)
            return 1

    problems = check(claude.read_text(encoding="utf-8"), block.read_text(encoding="utf-8"))
    if not problems:
        rows = len(table_rows(claude.read_text(encoding="utf-8")))
        secs = len(detail_sections(block.read_text(encoding="utf-8")))
        print("ok   %d rows promising an argument, %d sections, and they agree" % (rows, secs))
        return 0

    print("FAIL: the blocklist and its reasoning disagree")
    for p in problems:
        print("  " + p)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
