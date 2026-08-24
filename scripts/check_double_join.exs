# Gate: a comparison joined twice.
#
# WHY THIS EXISTS. A comparison has one join in it -- "X along the travel axis against Y across
# it". An edit that squeezes the sentence can drop a second join into the same place, and the
# result reads past a first pass. The specimen is from
# `anny-render-corpus/check_view_selection.py` and it shipped:
#
#     "mean foot separation about five stacked soda cans along the travel axis and against three and a half across it"
#
# Neither reading works. If "and" is the join, the words after it are a loose "against ..."
# phrase with nothing to be joined to. If "against" is the join, then "and" joins one thing to
# nothing. The T01 entry it was compressing had one join and read fine: mean foot separation is
# 0.356 m along the travel axis, about five stacked soda cans, against 0.230 m across it, about
# three and a half.
#
# It happens when a sentence is shortened. Nobody writes this from scratch; it appears when a
# long sentence carrying a measurement, a household anchor and a comparison is squeezed and the
# seams are not re-read. That is the edit an agent makes most often, which is why it is a gate
# rather than a note.
#
# THE VOCABULARY IS DELIBERATELY PLAIN. An earlier draft called this a "stacked connective",
# which is a phrase that has to be decoded before the reader can act on it. A gate's message is
# read by somebody who has just been interrupted, so it says "and" and "against" rather than
# naming the parts of speech they belong to.
#
# WHAT IS CHECKED, AND WHY IT IS THIS NARROW. A first version flagged "and" in front of any
# comparison word. Run over this repository it found the defect once and fired three times on
# correct prose:
#
#     logbook-rfd0016-model-repos.md:118    "names what needs confirming and against which repo"
#     logbook-rfd107a-t01-pose-check.md:157 "And against the image corpus."
#     scripts/check_rfd107a_plan.py:1       "Check the plan against RFD 107a, and against itself."
#
# Three false alarms to one catch is a gate somebody switches off, so it carries three guards,
# each one earned by a line above:
#
#   1. What follows the comparison word must be a NUMBER -- a digit or a number word, allowing a
#      hedge like about, roughly, nearly. "and against which repo" compares no measurements, and
#      this gate is only about the ones that do.
#   2. The "and" must not START THE SENTENCE. "And against the image corpus" puts the "against"
#      phrase at the front, which is ordinary English.
#   3. No "against" or "versus" may appear EARLIER IN THE SAME SENTENCE. "against RFD 107a, and
#      against itself" is two "against" phrases joined, which is this construction done right.
#
# Two joining words in a row -- "and but", "and and" -- are flagged with no guard, because there
# is no reading in which that is right.
#
# THE DETECTION FLOOR, STATED BECAUSE IT IS WELL ABOVE ZERO. Guard 1 is what keeps the noise down
# and it is also most of the floor: the same sentence broken between two things that are not
# numbers reads exactly as badly and is not caught here. Three further known misses:
#
#   - "and rather than" and "and instead of". Both open a clause perfectly well -- "and rather
#     than assume it, we measured" -- so flagging them would fire on correct prose more often
#     than on broken prose.
#   - "against" followed by "and". "weighed against the alternative and found wanting" is fine,
#     so that order cannot be called an error from adjacency alone.
#   - Repetition that still parses. The same specimen also said "picking a front view picked by
#     hand", which is one word doing its job twice rather than a broken comparison. It reads
#     badly and it reads; this gate only claims the sentences that do not.
#
# So a pass here is not a claim that the prose is good. It is a claim that no sentence in it
# joins a comparison of two measurements twice, which is one named defect out of many.
#
# USE, NOT MENTION. The paragraphs above contain the specimen and three false alarms, so the gate
# would fail its own file if it counted every occurrence. Double-quoted spans are blanked before
# scanning -- blanked rather than deleted, so offsets and line numbers still point at the text
# the author wrote. This is the convention `check_household_units.exs` and
# `check_prose_tropes.exs` arrived at, and the specimen block above is quoted for that reason as
# well as for reading.
#
# Usage:
#     elixir scripts/check_double_join.exs [<repo>] [--base <ref>]
#     elixir scripts/check_double_join.exs --self-test
#     elixir scripts/check_double_join.exs --file <path> [<path> ...]
#
# Exit codes: 0 nothing joined twice, 1 one or more found, 2 bad usage.

defmodule DoubleJoin do
  # "and" glued to a comparison word whose object is a number.
  #
  # THE WORD BOUNDARY GOES INSIDE EACH ALTERNATIVE, and the first version put one after the
  # group instead. `vs.` ends on a period, so the position after it has a non-word character on
  # both sides and `\b` does not hold -- the abbreviation the gate was written to catch was the
  # one form it let through. A control asserts it.
  @hedge "(?:about|roughly|some|nearly|around|only|just|barely|under|over)\\s+"
  @number "(?:\\d|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|" <>
            "fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|" <>
            "sixty|seventy|eighty|ninety|hundred|thousand|half|a\\s+half|a\\s+third|a\\s+quarter)"
  @joined_twice Regex.compile!(
                  "\\b(?:and|or|but)\\s+(?:against\\b|versus\\b|vs\\.?(?=[\\s,;:])|" <>
                    "as\\s+against\\b|as\\s+opposed\\s+to\\b)\\s+(?:#{@hedge})?#{@number}\\b",
                  "i"
                )

  # Two joining words in a row. "and/or" is written with a slash and does not match; "and, or"
  # has a comma between and does not match either, because the comma is the author choosing.
  @doubled ~r/\b(?:and|or|but)\s+(?:and|or|but)\b/i

  # A comparison word already spent earlier in the sentence, which makes the "and" legitimate.
  @already ~r/\b(?:against|versus|vs\.?)\b/i

  # Where a sentence starts: a full stop followed by a space, a blank line, or a line that opens
  # a markdown block. A single newline is NOT a boundary -- prose here is hard-wrapped, so
  # treating one as a sentence break would hide the earlier "against" that guard 3 looks for. A
  # full stop inside a decimal is not one either, because it has no space after it.
  @boundary ~r/(?<=[.!?])["'\)\]]?\s|\n\s*\n|\n\s*(?=[-*#>|]|\d+\.\s)/

  @quoted ~r/"[^"\n]*"/

  @exts [".md", ".py", ".ex", ".exs", ".usda", ".txt"]

  @doc """
  Sentences joined twice: `{line_number, matched_phrase}` for each one.

  Quoted spans are blanked to the same width rather than removed, so a line number is a count of
  newlines in the text the author wrote.
  """
  def joined_twice(text) do
    scrubbed = Regex.replace(@quoted, text, fn m -> String.duplicate(" ", byte_size(m)) end)

    guarded =
      Regex.scan(@joined_twice, scrubbed, return: :index) |> Enum.filter(&keep?(scrubbed, &1))

    plain = Regex.scan(@doubled, scrubbed, return: :index)

    (guarded ++ plain)
    |> Enum.map(fn [{o, len} | _] -> {line_of(scrubbed, o), binary_part(text, o, len)} end)
    |> Enum.sort()
  end

  # Guards 2 and 3, both read off the sentence so far. A match with nothing but punctuation
  # before it starts the sentence; a match with "against" before it is the second of two
  # "against" phrases that were joined on purpose.
  defp keep?(text, [{offset, _} | _]) do
    prefix =
      text
      |> binary_part(0, offset)
      |> then(&List.last(Regex.split(@boundary, &1)))
      |> Kernel.||("")

    String.replace(prefix, ~r/[^\p{L}\p{N}]/u, "") != "" and not Regex.match?(@already, prefix)
  end

  defp line_of(text, offset) do
    text |> binary_part(0, offset) |> :binary.matches("\n") |> length() |> Kernel.+(1)
  end

  def git(repo, args) do
    case System.cmd("git", ["-C", repo | args], stderr_to_stdout: true) do
      {out, 0} -> out
      _ -> nil
    end
  end

  def check(repo, base) do
    changed =
      (git(repo, ["diff", "--name-only", base]) || "")
      |> String.split("\n", trim: true)
      |> Enum.filter(fn f -> Enum.any?(@exts, &String.ends_with?(f, &1)) end)

    if changed == [] do
      IO.puts("no prose files changed against #{base}")
      0
    else
      bad = Enum.reduce(changed, 0, fn p, acc -> acc + score(repo, p) end)

      if bad == 0 do
        IO.puts("\nNo comparison is joined twice in #{length(changed)} changed file(s).")
        0
      else
        IO.puts("\n#{bad} file(s) join a comparison twice.")
        IO.puts("Drop one of the two. One join reads: X along A, against Y across B.")
        1
      end
    end
  end

  defp score(repo, path) do
    full = Path.join(repo, path)

    if File.exists?(full) do
      case joined_twice(File.read!(full)) do
        [] ->
          IO.puts("  ok   #{path}")
          0

        hits ->
          IO.puts("  FAIL #{path}: #{length(hits)} sentence(s) joined twice")
          Enum.take(hits, 5) |> Enum.each(fn {n, m} -> IO.puts("        #{path}:#{n}  #{m}") end)
          1
      end
    else
      # The file left the tree between the diff and the read. Named and counted, because an
      # unchecked file that prints nothing reads exactly like a passing one.
      IO.puts("  gone #{path} (in the diff, not on disk -- not checked)")
      0
    end
  end

  # Controls. The positives must FAIL, or the gate certifies the defect it was written for; the
  # negatives must PASS, or it fires on the correct prose beside it and gets switched off. The
  # three marked `observed` are real lines from this repository that the unguarded version hit.
  def self_test do
    cases = [
      {"the sentence that shipped",
       "picking a front view picked by hand caused mean foot separation about five stacked soda cans along the travel axis and against three and a half across it.",
       1},
      {"the same defect wrapped across a line",
       "mean foot separation is five stacked soda cans along the travel\naxis and against three and a half across it.",
       1},
      {"the T01 sentence it was compressing",
       "mean foot separation is 0.356 m along the travel axis, about five stacked soda cans, against 0.230 m across it, three and a half.",
       0},
      {"or in front of versus", "the peak is 8.60 GiB or versus 6.75 GiB at 512.", 1},
      {"vs with a full stop is caught", "the peak is 8.60 GiB and vs. 6.75 GiB.", 1},
      {"two joining words in a row", "the weights and but not the vision tokens", 1},
      # Guard 1: what follows is not a number.
      {"observed: and against which repo",
       "each one names exactly what needs confirming and against which upstream repo.", 0},
      # Guard 2: it starts the sentence.
      {"observed: And against the image corpus",
       "The next view is inconsistent in 3D.\n\n**And against 12 corpora.** It holds photographs.",
       0},
      # Guard 3: the comparison word is already spent.
      {"observed: against RFD 107a, and against itself",
       "Check the plan against RFD 107a, and against 3 of its own invariants.", 0},
      {"guard 3 holds for two joined measurements",
       "measured against 0.230 m across it and against 0.356 m along it.", 0},
      {"guard 3 survives a hard wrap",
       "measured against 0.230 m\nacross it and against 0.356 m along it.", 0},
      {"one join is fine", "8.60 GiB peak against a 6.75 GiB budget.", 0},
      {"and with something real on both sides is fine",
       "It is 0.230 m across the stride and 0.356 m along it.", 0},
      {"and/or is a slash, not a double join",
       "the licence permits commercial and/or derivative use.", 0},
      {"a comma between joining words is the author choosing",
       "it is measured, and, or so the entry claims, reproducible.", 0},
      # The four known misses, asserted as misses so the floor is checked rather than described.
      {"MISS: and rather than, because it opens clauses legally",
       "the residual is 107.7 mm and rather than the pose it tracks the rig", 0},
      {"MISS: against followed by and", "weighed against the alternative and found wanting", 0},
      {"MISS: repetition that still parses", "picking a front view picked by hand", 0},
      {"MISS: the same break between two things that are not numbers",
       "the licence fails on the operator and against the corpus.", 0},
      # Use, not mention.
      {"a quoted specimen does not count",
       ~s(The broken form reads "the axis and against three and a half" and is fixed above.), 0},
      {"versus inside a word is not a comparison word",
       "the adversus branch and the other one", 0}
    ]

    IO.puts("controls:")

    bad =
      Enum.reduce(cases, [], fn {label, text, want}, acc ->
        got = length(joined_twice(text))
        ok = got == want
        IO.puts("  #{if ok, do: "ok  ", else: "BAD "} #{label} (found #{got}, wanted #{want})")
        if ok, do: acc, else: [label | acc]
      end)

    # Blanking a quoted span must not move the line numbers of what follows it, and a count of
    # hits cannot show that -- the blanked span contributes no hit either way. Asserted directly.
    # Assembled from pieces so no line of THIS file carries the pattern outside quotes -- the
    # same use-not-mention problem the docs above solve by quoting, solved here by splitting.
    line_case = ~s(a "quoted and against five" span here
the axis ) <> "and against" <> " three across it."
    line_bad = if joined_twice(line_case) == [{2, "and against three"}], do: [], else: ["blanking keeps line numbers"]
    IO.puts("  #{if line_bad == [], do: "ok  ", else: "BAD "} blanking a quote keeps the line number of the next line")

    bad = bad ++ line_bad

    if bad == [] do
      IO.puts("\nAll #{length(cases) + 1} controls behaved.")
      0
    else
      IO.puts("\n#{length(bad)} control(s) failed.")
      1
    end
  end
end

case System.argv() do
  ["--self-test"] ->
    System.halt(DoubleJoin.self_test())

  # One path or many. prek hands a hook the changed files as a bare list, so the plural form is
  # what CI actually calls; the singular is what a person types.
  ["--file" | paths] when paths != [] ->
    bad =
      Enum.reduce(paths, 0, fn path, acc ->
        case DoubleJoin.joined_twice(File.read!(path)) do
          [] ->
            acc

          hits ->
            IO.puts("FAIL #{path}: #{length(hits)} sentence(s) joined twice")
            Enum.each(hits, fn {n, m} -> IO.puts("      #{path}:#{n}  #{m}") end)
            acc + 1
        end
      end)

    if bad == 0 do
      IO.puts("ok   #{length(paths)} file(s): nothing joined twice")
      System.halt(0)
    else
      IO.puts("
Drop one of the two. One join reads: X along A, against Y across B.")
      System.halt(1)
    end

  args ->
    {opts, rest, _} = OptionParser.parse(args, strict: [base: :string])
    System.halt(DoubleJoin.check(List.first(rest) || ".", opts[:base] || "HEAD"))
end
