import unittest
from decimal import Decimal
from diagnostics.kyoto_cancel_odds_classifier import classify_odds_cell, split_market_cells

class TestMarketCellClassification(unittest.TestCase):
    def test_valid_and_original_preserved(self):
        for raw, expected in [("14.6", "14.6"), ("1,234.5", "1234.5"), (" １２.３ ", "12.3")]:
            cell = classify_odds_cell(raw)
            self.assertEqual(cell.state, "VALID")
            self.assertEqual(cell.odds, Decimal(expected))
            self.assertEqual(cell.original, raw)

    def test_cancel_is_not_numeric(self):
        for raw in ["取消", "出走取消", "競走除外", "除外", " 取 消 "]:
            cell = classify_odds_cell(raw)
            self.assertEqual(cell.state, "CANCELLED")
            self.assertIsNone(cell.odds)

    def test_unavailable(self):
        for raw in ["", "-", "未発売", "発売前", "締切", "発売終了"]:
            self.assertEqual(classify_odds_cell(raw).state, "UNAVAILABLE")

    def test_invalid_fails_closed(self):
        for raw in [None, "NaN", "Infinity", "0", "-1", "12abc", "1,23.4", "--"]:
            self.assertEqual(classify_odds_cell(raw).state, "INVALID")

    def test_both_market_groups(self):
        for market in ("馬連", "枠連"):
            groups = split_market_cells({"1-2": "14.6", "1-3": "取消", "2-3": "未発売", "3-4": "broken"})
            self.assertEqual([len(groups[x]) for x in ("VALID", "CANCELLED", "UNAVAILABLE", "INVALID")], [1, 1, 1, 1], market)
            self.assertIsNone(groups["CANCELLED"]["1-3"].odds)

if __name__ == "__main__":
    unittest.main()
