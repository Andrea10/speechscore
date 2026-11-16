import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from speechscore import analyse  # noqa: E402


def make_words(text, mid_after=(), boundary_gap=0.5, mid_gap=0.7, long_after=()):
    """Build synthetic word timings: 0.3 s per word, 0.08 s gaps by default."""
    out, t = [], 0.0
    for w in text.split():
        out.append({"w": w, "s": round(t, 2), "e": round(t + 0.3, 2)})
        t += 0.38
        if w in mid_after:
            t += mid_gap
        if w.endswith((".", ",")):
            t += boundary_gap
        if w in long_after:
            t += 1.1
    return out


TEXT = ("So the main point is that we should, um, prioritise the settlement layer. "
        "Because the cost of the the integration is high and we need to move fast. "
        "I think we should start with stablecoins, which are cheaper for cross-border "
        "payments, and then expand.")


class TestAnalyse(unittest.TestCase):
    def setUp(self):
        words = make_words(TEXT, mid_after=("prioritise", "of"), long_after=("um,",))
        self.m, self.d = analyse(words, "en")

    def test_detects_midclause_pauses(self):
        self.assertEqual(self.m["midclause_pauses"], 2)

    def test_boundary_pauses_not_counted_as_mid(self):
        self.assertGreater(self.m["boundary_pauses"], self.m["midclause_pauses"])

    def test_fillers(self):
        self.assertEqual(self.m["fillers"], 1)
        self.assertEqual(self.d["filler_words"], ["um"])

    def test_repetition(self):
        self.assertEqual(self.m["repetitions"], 1)

    def test_long_pause(self):
        self.assertEqual(self.m["long_pauses_1s"], 1)

    def test_articulation_faster_than_overall(self):
        self.assertGreater(self.m["articulation_wpm"], self.m["wpm"])

    def test_italian_fillers(self):
        words = make_words("Allora eh diciamo che il progetto, cioè, funziona bene.")
        m, d = analyse(words, "it")
        self.assertEqual(sorted(d["filler_words"]), ["cioè", "diciamo", "eh"])


if __name__ == "__main__":
    unittest.main()
