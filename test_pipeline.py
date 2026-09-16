"""Run with python -m unittest -v; entirely synthetic and offline."""
import tempfile
import unittest
from pathlib import Path

from linkage import candidates, evaluate, extract, find_matches, normalise, read_csv
from synthetic import make_dataset


class PipelineChecks(unittest.TestCase):
    def test_end_to_end_and_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = make_dataset(temp)
            records, issues = extract(root / "pages")
            self.assertEqual((len(records), len(issues)), (320, 16))
            for row in records:
                line = (root / "pages" / row["source_file"]).read_text(encoding="utf-8").splitlines()[row["source_line"] - 1]
                self.assertEqual(row["raw_text"], line)
            pairs = candidates(records)
            decisions = find_matches(records, pairs)
            truth = read_csv(root / "truth.csv")
            metrics = evaluate(decisions, pairs, truth)
            self.assertEqual((metrics["baseline"], metrics["true_links"]), (160, 128))
            self.assertEqual(metrics["accepted"] + metrics["review"] + metrics["unmatched"], 160)
            # Known migrants make within-town blocking incomplete, independent of scoring.
            self.assertEqual(metrics["candidate_recall"], 112 / 128)
            accepted = [r for r in decisions if r["status"] == "accepted"]
            self.assertEqual(len(accepted), len({r["right_id"] for r in accepted}))
            self.assertGreater(len(accepted), 0)
            self.assertGreater(metrics["review"], 0)
            truth_map = {r["left_id"]: r["right_id"] for r in truth}
            correct = sum(r["right_id"] == truth_map[r["left_id"]] for r in accepted)
            self.assertEqual(metrics["precision"], correct / len(accepted))
            self.assertEqual(metrics["recall"], correct / 128)
            self.assertEqual(metrics["coverage"], len(accepted) / 160)
            # Reordering records/candidates cannot resolve a tie differently.
            reversed_decisions = find_matches(list(reversed(records)), list(reversed(pairs)))
            self.assertEqual({r["left_id"]: r for r in decisions}, {r["left_id"]: r for r in reversed_decisions})
            with self.assertRaises(ValueError):
                candidates(records + [records[0]])
            with self.assertRaises(ValueError):
                find_matches(records, pairs + [pairs[0]])
            with self.assertRaises(ValueError):
                find_matches(records, pairs, threshold=float("nan"))
            with self.assertRaises(ValueError):
                evaluate(decisions[1:], pairs, truth)
            # A distinct real person with indistinguishable evidence stays unresolved.
            twins = [r for r in records if r["given"] == "emil" and r["surname"] == "meyer" and not r["birth"]]
            tied_ids = {r["record_id"] for r in twins if r["year"] == 1920}
            self.assertTrue(all(r["status"] != "accepted" for r in find_matches(records, pairs, .55, 0) if r["left_id"] in tied_ids))
            no_links = find_matches(records, [], threshold=1.)
            self.assertIsNone(evaluate(no_links, [], truth)["precision"])
            self.assertEqual(evaluate(no_links, [], truth)["recall"], 0.)
            before = {p.name: p.read_bytes() for p in (root / "pages").glob("*.txt")}
            self.assertTrue(all(b"\r" not in content for content in before.values()))
            make_dataset(root)
            self.assertEqual(before, {p.name: p.read_bytes() for p in (root / "pages").glob("*.txt")})

    def test_missingness_and_rejections(self):
        self.assertEqual(normalise("Müller"), normalise("Mueller"))
        with tempfile.TemporaryDirectory() as temp:
            page = Path(temp) / "example.txt"
            page.write_text("SYNTHETIC\nMunicipality: Testtown\nYear: 1920\n\n"
                            "01 | Meyer, Anna | b. ? | clerk | ?\n"
                            "02 | Meyer, Otto | b. 2010 | clerk | ?\n"
                            "03 | , | b. 1880 | clerk | ?\n", encoding="utf-8")
            records, issues = extract(temp)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["birth"], "")
            self.assertEqual({r["reason"] for r in issues}, {"invalid_birth_year", "missing_name"})


if __name__ == "__main__":
    unittest.main()
