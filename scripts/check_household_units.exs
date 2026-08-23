# Gate: a physical measurement without a household equivalent.
#
# WHY THIS EXISTS. CLAUDE.md, under "How measurements are reported", says to pair every physical
# measurement with a household object, because "4.3 mm" does not tell a reader whether an error
# matters and "about three stacked pennies" does. It also says that where a script prints
# measurements repeatedly, it should carry a helper rather than rely on recall.
#
# Recall duly failed. Across one working session the rule was broken at least three times in
# prose that reported a pixel error, a quantisation step of about a sixtieth of a credit card,
# and a stride gap of some five soda cans, each time bare, by an author who had read the rule
# that morning. A habit that survives knowing about it needs a gate.
#
# WHAT COUNTS AS PAIRED. A number with a length unit is paired when a household anchor appears
# within the same sentence or the one after it. The anchors are CLAUDE.md's own list, which is
# the point: the gate reads the vocabulary from the agreements rather than keeping a second
# copy that can drift.
#
#     credit card 0.76 mm    penny 1.52 mm     pencil 7 mm       AAA 10.5 mm
#     AA 14.5 mm             nickel 21.2 mm    golf ball 42.7 mm wrist 57 mm
#     soda can 66 mm
#
# WHAT IT DELIBERATELY DOES NOT CATCH. Sizes in bytes, durations, counts, versions, money, and
# coordinates in pixels unless a physical unit is attached. The rule is about physical extent,
# and widening it to every number would make the gate noise and get it switched off.
#
# THE DETECTION FLOOR, STATED BECAUSE IT EXCEEDS ZERO. An anchor phrased in words the list does
# not contain -- "the width of a hair", "a grain of rice" -- reads as unpaired here. That is a
# false alarm rather than a miss, which is the safer direction for a gate to be wrong in, and
# adding the phrase to CLAUDE.md fixes it in both places at once.
#
# Usage:
#     elixir scripts/check_household_units.exs [<repo>] [--base <ref>]
#     elixir scripts/check_household_units.exs --self-test
#     elixir scripts/check_household_units.exs --file <path>
#
# Exit codes: 0 every measurement is paired, 1 one or more are bare, 2 bad usage.

defmodule HouseholdUnits do
  # A number with a length unit attached. Bytes, seconds and pixels are absent on purpose.
  #
  # CASE MATTERS FOR THE SHORT UNITS, and the first version ignored it: `$1M` of revenue in
  # CLAUDE.md was read as one metre. Lowercase m, mm and cm only; the spelled-out words stay
  # case-insensitive because a sentence may begin with one. A leading currency symbol is
  # rejected outright, since "$5 m" is money however it is capitalised.
  @measure ~r/(?<![$\w])\d+(?:\.\d+)?(?:e-?\d+)?\s?(?:mm|cm|m)\b|\b\d+(?:\.\d+)?\s?(?:metres|meters|millimetres|millimeters)\b/
  # Sentence-ish spans, so an anchor in the next sentence still counts as pairing.
  #
  # A PERIOD SOMETIMES SITS INSIDE A NUMBER. Splitting on every one cut "0.02 m" into "02 m" and
  # then reported the fragment as unpaired while the anchor sat in the half that was thrown
  # away. A stop is a period with no digit on both sides of it.
  @sentence ~r/(?:[^.!?\n]|(?<=\d)\.(?=\d))+[.!?]?/
  @anchors ~w(card penny pennies pencil AAA AA nickel golf wrist can cans coin)
  @exts [".md", ".py", ".ex", ".exs", ".usda"]

  def anchors, do: @anchors

  # USE, NOT MENTION, the same rule check_prose_tropes.exs arrived at by rejecting itself. A
  # gate for unpaired measurements must contain unpaired measurements: its controls are
  # specimens, and its documentation quotes the anchor table. Counting those made this file fail
  # its own check seven times while every document it polices passed.
  @quoted ~r/"[^"\n]*"/

  # A TABLE IS ONE SPAN, NOT A ROW PER SENTENCE. A residual table pairs its numbers with a
  # `pennies` column, and the anchor sits in the header where a row-by-row window cannot see it.
  # Scoring rows separately flagged five paired measurements and pushed the author into
  # rewriting a good table as prose -- the same mistake the index gate caused with `foot.R`.
  # Contiguous pipe-led lines are joined so the header travels with its rows.
  defp fold_tables(text) do
    text
    |> String.split("\n")
    |> Enum.chunk_by(&String.starts_with?(String.trim_leading(&1), "|"))
    |> Enum.map(fn chunk ->
      if String.starts_with?(String.trim_leading(hd(chunk)), "|"),
        do: Enum.join(chunk, " ") <> ".",
        else: Enum.join(chunk, "\n")
    end)
    |> Enum.join("\n")
  end

  @doc "Bare measurements in a text: {line_hint, matched_measure} for each unpaired one."
  def bare(text) do
    text = text |> fold_tables() |> then(&Regex.replace(@quoted, &1, " "))
    spans = Regex.scan(@sentence, text) |> Enum.map(fn [s] -> s end)

    spans
    |> Enum.with_index()
    |> Enum.flat_map(fn {s, i} ->
      # The sentence, the one before it and the one after. The first version looked forward
      # only and flagged two readings whose anchor sat in the preceding sentence -- "a penny is
      # 1.52 mm and thirteen of those is 19.8 mm" reads as bare if you cannot see the first
      # half. Pairing is allowed to arrive before the number.
      window =
        Enum.at(spans, i - 1, "") <> " " <> s <> " " <> Enum.at(spans, i + 1, "")

      case Regex.run(@measure, s) do
        nil -> []
        [m] -> if anchored?(window), do: [], else: [{String.trim(s), m}]
      end
    end)
  end

  defp anchored?(window) do
    low = String.downcase(window)
    Enum.any?(@anchors, fn a -> String.contains?(low, String.downcase(a)) end)
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
      IO.puts("no measured files changed")
      0
    else
      bad = Enum.reduce(changed, 0, fn p, acc -> acc + score(repo, p) end)

      if bad == 0 do
        IO.puts("\nEvery physical measurement carries a household equivalent.")
        0
      else
        IO.puts("\n#{bad} file(s) report a length with nothing to compare it to.")
        IO.puts("Pair it: #{Enum.join(Enum.take(@anchors, 6), ", ")}, or add the anchor to CLAUDE.md.")
        1
      end
    end
  end

  defp score(repo, path) do
    full = Path.join(repo, path)

    if File.exists?(full) do
      case bare(File.read!(full)) do
        [] ->
          IO.puts("  ok   #{path}")
          0

        hits ->
          IO.puts("  FAIL #{path}: #{length(hits)} bare measurement(s)")
          Enum.take(hits, 3) |> Enum.each(fn {s, m} ->
            IO.puts("        #{m} in \"#{String.slice(s, 0, 74)}\"")
          end)
          1
      end
    else
      0
    end
  end

  # Controls. A gate that cannot fail certifies the habit, and this one has two halves that
  # fail apart: finding a measurement, and deciding whether it was paired.
  def self_test do
    cases = [
      {"a bare millimetre reading is caught", "The error is 0.012 mm across the span.", 1},
      {"the same reading paired is accepted",
       "The error is 0.012 mm, about a sixtieth of a credit card.", 0},
      {"an anchor in the next sentence still pairs",
       "The gap is 0.356 m along the stride. That is roughly five soda cans end to end.", 0},
      {"bytes are not a physical measurement", "The file is 90876 bytes on disk.", 0},
      {"a duration is not a physical measurement", "It ran for 220 s per image.", 0},
      {"two bare readings are both reported",
       "One is 4.3 mm. Another is 57 m. Neither is explained.", 2},
      {"pixels alone are ignored", "Worst coordinate error 5.00e-05 px over the frame.", 0},
      # Both of these came from running the gate on the tree and reading what it flagged.
      {"currency is not a length", "Free below $1M company-wide annual revenue.", 0},
      {"a decimal is not a sentence boundary",
       "At TOL = 0.02 m, about thirteen credit cards, the rest pose reports 14 of 104.", 0},
      {"a decimal reading with no anchor is still caught",
       "At TOL = 0.02 m the rest pose reports 14 of 104 joints.", 1},
      # Found by running the gate on the tree: the anchor had arrived one sentence early.
      {"an anchor in the previous sentence still pairs",
       "A penny is 1.52 mm. Thirteen of those is 19.8 mm.", 0},
      {"i - 1 does not wrap to the end of the file",
       "The span is 4.3 mm and nothing explains it.", 1},
      # A table pairs through its header, which a row-by-row window cannot see.
      {"a table header pairs every row",
       "| target | residual | pennies |
| --- | --- | --- |
| root | 107.7 mm | 71 |
", 0},
      {"a table with no anchor anywhere still fails",
       "| target | residual |
| --- | --- |
| root | 107.7 mm |
", 1}
    ]

    IO.puts("controls:")

    bad =
      Enum.reduce(cases, [], fn {label, text, want}, acc ->
        got = length(bare(text))
        ok = got == want
        IO.puts("  #{if ok, do: "ok  ", else: "BAD "} #{label} (found #{got}, wanted #{want})")
        if ok, do: acc, else: [label | acc]
      end)

    if bad == [] do
      IO.puts("\nAll #{length(cases)} controls behaved.")
      0
    else
      IO.puts("\n#{length(bad)} control(s) failed.")
      1
    end
  end
end

case System.argv() do
  ["--self-test"] ->
    System.halt(HouseholdUnits.self_test())

  ["--file", path] ->
    case HouseholdUnits.bare(File.read!(path)) do
      [] ->
        IO.puts("ok   #{path}: every measurement is paired")
        System.halt(0)

      hits ->
        IO.puts("FAIL #{path}: #{length(hits)} bare measurement(s)")
        Enum.each(hits, fn {s, m} -> IO.puts("      #{m} in \"#{String.slice(s, 0, 78)}\"") end)
        System.halt(1)
    end

  args ->
    {opts, rest, _} = OptionParser.parse(args, strict: [base: :string])
    System.halt(HouseholdUnits.check(List.first(rest) || ".", opts[:base] || "HEAD"))
end
