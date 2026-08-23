"""Gate: a document carries no index of the files beside it.

WHY THIS EXISTS. A hand-written index of a directory is a second copy of `ls`, and the two
disagree the first time somebody adds a file and forgets the table. Nothing reports that. The
rows were accurate the afternoon they were written, which is exactly what turns a stale index
into a confident, wrong answer about what is here.

WHAT COUNTS AS AN INDEX ROW. A table row or a list item whose FIRST cell names a file or a
directory, in backticks or as a link:

    | `todo.md`  | the running logbook |
    - [todo.md](todo.md) - the running logbook

Prose that names a file is fine, and so is a table whose subject is something other than the
file tree: a measurement table with a filename in a later column stays legal.

WHETHER THE FILE EXISTS IS NOT THE TEST. A row pointing at a present file is an index that will
rot; a row pointing at a missing one has rotted already. Both fail for the same reason, so
existence is never consulted.

REWRITTEN TWICE, AND BOTH REASONS ARE WORTH KEEPING.

First, it parsed by hand -- `line.strip().startswith("|")`, a regex to split cells, another to
find list markers -- while `check-rfd-structure.py` next door already parsed markdown with
markdown-it. A gate that reasons about table structure should use the parser rather than
approximate it, and this one now walks the CommonMark token stream: rows come from `tr_open`,
cells from `th_open`/`td_open`, and a first cell is a file reference only when its inline
content is a single code span or link.

Second, and this is the one that caused a false accusation: the old pattern was
`^[\\w.\\-/]+(\\.\\w+|/)$`, which reads any dotted token as a filename. It flagged `foot.R`, an
ANNY bone in a residual table, as an index row -- and the author rewrote a perfectly good table
into prose to satisfy it rather than fixing the gate. A dot is not an extension. The extension
must be one this workspace actually uses, or the name must carry a path separator.

Third, a slash was treated as sufficient evidence of a path, so `head/neck` -- a body region
in a residual table -- was read as a two-segment filename. That is the `foot.R` mistake with a
different separator. A path now has to start at a side, the digit-prefixed top-level
directories, or carry a known extension, or end in a separator.

DETECTION FLOOR. An index row naming a file whose extension is absent from the list below reads
as legal. That is a miss rather than a false alarm, and the fix is to add the extension when a
new kind of file arrives, which is a visible edit rather than a silent drift.
"""
import pathlib
import re
import sys

from markdown_it import MarkdownIt

# Tables are GFM rather than CommonMark, so the preset has to include them.
MD = MarkdownIt("commonmark").enable("table")

# Extensions this workspace writes. A dotted token whose suffix is absent here is a name that
# happens to contain a dot -- `foot.R`, `spine02.L`, `v1.0` -- and not a file.
EXTENSIONS = {
    "md", "rst", "txt", "py", "ex", "exs", "eex", "sh", "bash", "ps1",
    "usda", "usdc", "usdz", "json", "toml", "lock", "xml", "yaml", "yml", "cff",
    "parquet", "csv", "png", "jpg", "jpeg", "exr", "psb", "psd", "svg", "glb", "gltf",
    "bvh", "pt", "pth", "safetensors", "gguf", "so", "dll", "cpp", "h", "hpp", "rs", "go",
}


def names_a_file(text):
    """True when `text` is a path or a filename with an extension we recognise."""
    t = text.strip().strip("`")
    if not t or " " in t:
        return False
    if t.endswith("/"):
        return True
    if "/" in t and re.match(r"^[\w.\-/]+$", t):
        # `head/neck` is one of this workspace's body regions, and the first version of this
        # branch read it as a two-segment path, flagging a residual table exactly as `foot.R`
        # once did. What identifies a path here is where it starts or how it ends: a side, the
        # digit-prefixed top-level directories, or a known extension, or a trailing separator.
        # Two ordinary words joined by a slash have none of those.
        head = t.split("/")[0]
        if re.match(r"^\d-[a-z][a-z_\-]*$", head):
            return True
        return bool(re.search(r"\.([A-Za-z0-9]+)$", t)
                    and t.rsplit(".", 1)[1].lower() in EXTENSIONS)
    m = re.match(r"^[\w.\-]+\.([A-Za-z0-9]+)$", t)
    return bool(m and m.group(1).lower() in EXTENSIONS)


def first_cells(src):
    """Every first-cell inline token run: table rows and list items, from the AST."""
    tokens = MD.parse(src)
    out, depth, cell_index, capture = [], 0, 0, None
    for i, tok in enumerate(tokens):
        if tok.type == "tr_open":
            cell_index = 0
        elif tok.type in ("th_open", "td_open"):
            cell_index += 1
            capture = cell_index == 1
        elif tok.type in ("th_close", "td_close"):
            capture = None
        elif tok.type == "list_item_open":
            capture = True
        elif tok.type == "inline" and capture:
            out.append((tok.map[0] + 1 if tok.map else 0, tok))
            capture = None
    return out


def cell_reference(tok):
    """The filename a first cell names, if the cell IS that reference and not prose about it."""
    kids = [c for c in (tok.children or []) if c.type != "text" or c.content.strip()]
    if not kids:
        return None
    head = kids[0]
    if head.type == "code_inline":
        return head.content if names_a_file(head.content) else None
    if head.type == "link_open":
        href = dict(head.attrs).get("href", "")
        label = "".join(c.content for c in kids[1:] if c.type == "text")
        for candidate in (href, label):
            if names_a_file(candidate):
                return candidate
    # A list item that begins with a bare filename, no backticks and no link.
    if head.type == "text":
        first = head.content.strip().split()[0] if head.content.strip() else ""
        return first if names_a_file(first) else None
    return None


def check(path):
    src = pathlib.Path(path).read_text(encoding="utf-8", errors="ignore")
    bad = []
    for line, tok in first_cells(src):
        ref = cell_reference(tok)
        if ref:
            bad.append((line, ref))
    if bad:
        print(f"  FAIL {path}: {len(bad)} index row(s). The directory is the index; delete these.")
        for line, ref in bad[:5]:
            print(f"        line {line}: {ref}")
        return 1
    print(f"  ok   {path}: no index rows")
    return 0


def self_test():
    cases = [
        ("a table row naming a file", "| `todo.md` | the log |\n| --- | --- |\n", 1),
        ("a list item linking a file", "- [todo.md](todo.md) - the log\n", 1),
        ("a directory row", "| `scripts/` | the apparatus |\n| --- | --- |\n", 1),
        # The false accusation that prompted the rewrite: an ANNY bone, not an R script.
        ("a bone name is not a file", "| `foot.R` | 5.8 mm | 4 |\n| --- | --- | --- |\n", 0),
        ("a version is not a file", "| `v1.0` | shipped |\n| --- | --- |\n", 0),
        ("a filename in a later column is legal",
         "| target | file |\n| --- | --- |\n| root | `plan.usda` |\n", 0),
        ("prose naming a file is legal", "An entry records what `check_usd_valid.py` measures.\n", 0),
        ("a measurement row is legal", "| `spine02` | 45.9 mm | 30 |\n| --- | --- | --- |\n", 0),
        # `head/neck` names a region of the body, and the earlier pattern read its slash as a
        # path separator -- the same false accusation `foot.R` produced one rewrite ago.
        ("a region name is not a path", "| head/neck | 15.77 mm | 10 |\n| --- | --- | --- |\n", 0),
        ("a side-rooted path is still an index row",
         "| `2-contract/logbook` | the log |\n| --- | --- |\n", 1),
        ("a path with a known extension is still an index row",
         "| `common/assets/bodytags_v3.json` | the tags |\n| --- | --- |\n", 1),
    ]
    print("controls:")
    bad = []
    for label, src, want in cases:
        got = len([1 for _, t in first_cells(src) if cell_reference(t)])
        ok = got == want
        print(f"  {'ok  ' if ok else 'BAD '} {label} (found {got}, wanted {want})")
        if not ok:
            bad.append(label)
    if bad:
        print(f"\n{len(bad)} control(s) failed.")
        return 1
    print(f"\nAll {len(cases)} controls behaved.")
    return 0


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    if "--self-test" in argv[1:]:
        return self_test()
    if not args:
        print("usage: check_readme_no_index.py <file.md> [...] [--self-test]")
        return 2
    return max(check(a) for a in args)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
