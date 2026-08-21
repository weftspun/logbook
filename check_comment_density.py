# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Gate: a change must match the comment density of the code it edits.

WHY THIS EXISTS. This workspace asks for heavy comments, because a weftspun file has to
carry the measurement and the retraction that produced it. Other codebases do not ask for
that, and pushing our density into theirs makes a diff that reads as noise to the people who
maintain it.

Measured on godotengine/godot at 4.7.0-beta, over the 68 files in `servers/` with more than
200 lines:

    median   3.7 %
    mean     4.6 %
    p90      9.3 %

A first pass at `servers/movie_writer/movie_writer.cpp` took that file from 6.1 % to 10.4 %,
past the p90 of the whole directory. The content was accurate and the density was wrong.

THE RULE THIS ENFORCES. A changed file may not exceed the greater of its own density before
the change and the p90 of its peers. Peers are files with the same extension under the same
top-level directory, because a header and a renderer are not held to one number.

Run:  python check_comment_density.py <repo> [--base HEAD] [--self-test]
"""

import argparse
import os
import statistics
import subprocess
import sys

SOURCE_EXT = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".m", ".mm"}
# Vendored code is not ours and is not held to our density. Skipping it also keeps the peer
# scan from walking every third-party source in the tree, which made this take minutes.
VENDORED = ("thirdparty/", "third_party/", "external/", "vendor/", "modules/mono/glue/")
MIN_LINES = 200          # below this a single comment swings the ratio
BANNER_LINES = 31        # Godot's licence header, skipped so it does not dominate small files


def density(lines):
    """Comment lines over non-blank lines, ignoring a leading licence banner."""
    body = lines[BANNER_LINES:] if len(lines) > 40 and "/*****" in "".join(lines[:3]) else lines
    comment = code = 0
    in_block = False
    for raw in body:
        line = raw.strip()
        if not line:
            continue
        if in_block:
            comment += 1
            if "*/" in line:
                in_block = False
            continue
        if line.startswith("/*"):
            comment += 1
            in_block = "*/" not in line
        elif line.startswith("//") or line.startswith("*"):
            comment += 1
        else:
            code += 1
    total = comment + code
    return comment, code, (comment / total if total else 0.0)


def read(repo, path):
    try:
        with open(os.path.join(repo, path), encoding="utf8", errors="ignore") as fh:
            return fh.read().splitlines()
    except OSError:
        return None


def at_ref(repo, ref, path):
    out = subprocess.run(["git", "-C", repo, "show", f"{ref}:{path}"],
                         capture_output=True, text=True)
    return out.stdout.splitlines() if out.returncode == 0 else None


_PEER_CACHE = {}


def peers(repo, path):
    """Same extension, same top-level directory. A header is judged against headers."""
    ext = os.path.splitext(path)[1]
    top = path.split("/")[0]
    key = (repo, top, ext)
    if key in _PEER_CACHE:
        return [v for v in _PEER_CACHE[key]]
    out = subprocess.run(["git", "-C", repo, "ls-files", f"{top}/*{ext}"],
                         capture_output=True, text=True)
    vals = []
    for f in out.stdout.split():
        if f == path or f.replace("\\", "/").startswith(VENDORED):
            continue
        lines = read(repo, f)
        if not lines:
            continue
        comment, code, ratio = density(lines)
        if comment + code >= MIN_LINES:
            vals.append(ratio)
    _PEER_CACHE[key] = vals
    return vals


def changed(repo, base):
    """Modified files AND new ones.

    `git diff --name-only` lists neither untracked files nor staged additions, so a gate built
    on it alone silently skips every file a change introduces. That is the case it most needs
    to catch, since a new file has no prior density to be held to.
    """
    names = set()
    for args in (["diff", "--name-only", base],
                 ["diff", "--name-only", "--cached"],
                 ["ls-files", "--others", "--exclude-standard"]):
        out = subprocess.run(["git", "-C", repo] + args, capture_output=True, text=True)
        names.update(out.stdout.split())
    return sorted(f for f in names
                  if os.path.splitext(f)[1] in SOURCE_EXT
                  and not f.replace("\\", "/").startswith(VENDORED))


def check(repo, base, verbose=True):
    files = changed(repo, base)
    if not files:
        if verbose:
            print("no source files changed against %s" % base)
        return 0, []
    failures = []
    for path in files:
        now = read(repo, path)
        if not now:
            continue
        n_com, n_code, n_ratio = density(now)
        if n_com + n_code < MIN_LINES:
            continue
        peer = peers(repo, path)
        if not peer:
            continue
        p90 = sorted(peer)[int(len(peer) * 0.9)]
        med = statistics.median(peer)
        before = at_ref(repo, base, path)
        b_ratio = density(before)[2] if before else 0.0
        # A file already above its peers is not made worse by this rule, so its own prior
        # density is a floor. The rule is "do not raise it further", not "rewrite the file".
        ceiling = max(p90, b_ratio)
        ok = n_ratio <= ceiling + 1e-9
        if verbose:
            print("  %-4s %-52s %5.1f%%  was %5.1f%%  peers median %4.1f%% p90 %4.1f%%"
                  % ("ok" if ok else "FAIL", path, n_ratio * 100, b_ratio * 100,
                     med * 100, p90 * 100))
        if not ok:
            failures.append((path, n_ratio, ceiling))
    return len(files), failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--base", default="HEAD")
    ap.add_argument("--self-test", action="store_true",
                    help="prove the gate fails on a file padded with comments")
    args = ap.parse_args()

    n, failures = check(args.repo, args.base)
    if args.self_test:
        # NEGATIVE CONTROL. A gate that only ever passes has shown nothing. This pads a real
        # changed file with comment lines and asserts the gate rejects it.
        files = changed(args.repo, args.base)
        if not files:
            print("self test needs at least one changed source file")
            return 1
        target = files[0]
        full = os.path.join(args.repo, target)
        with open(full, encoding="utf8", errors="ignore") as fh:
            original = fh.read()
        try:
            padding = "\n".join("// padding line %d" % i for i in range(400))
            with open(full, "w", encoding="utf8") as fh:
                fh.write(original + "\n" + padding + "\n")
            _, padded_failures = check(args.repo, args.base, verbose=False)
            caught = any(f[0] == target for f in padded_failures)
            print("  %-4s negative control: %s padded with 400 comment lines is rejected"
                  % ("ok" if caught else "FAIL", target))
            if not caught:
                print("       the gate accepted an obviously over-commented file.")
                return 1
        finally:
            with open(full, "w", encoding="utf8") as fh:
                fh.write(original)

    print()
    if failures:
        for path, ratio, ceiling in failures:
            print("%s is %.1f%% comments, above the %.1f%% its peers allow."
                  % (path, ratio * 100, ceiling * 100))
        print("Move the reasoning into the commit message.")
        return 1
    print("%d changed source file(s) within the density of their peers." % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
