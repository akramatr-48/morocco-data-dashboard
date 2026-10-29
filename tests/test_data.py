"""Deterministic checks; these synthetic fixtures never feed the real app."""

import math
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
import requests

from analytics import combine_series, csv_bytes, latest_metric
from data_loader import DataUnavailable, fetch_indicator, parse_payload
from indicators import INDICATORS

CODE = INDICATORS[0].code


def payload(values, code=CODE):
    return [
        {"pages": 1, "lastupdated": "2026-01-01"},
        [
            {"date": str(year), "value": value, "indicator": {"id": code}, "countryiso3code": "MAR"}
            for year, value in values
        ],
    ]


class DataChecks(unittest.TestCase):
    def test_reverse_order_nulls_zero_and_gaps_are_preserved(self):
        result = parse_payload(payload([(2003, 0), (2002, None), (2000, -2.5)]), CODE, 2003)
        self.assertEqual(result.frame.Year.tolist(), [2000, 2001, 2002, 2003])
        self.assertEqual(result.frame.Value.iloc[0], -2.5)
        self.assertTrue(math.isnan(result.frame.Value.iloc[1]))
        self.assertTrue(math.isnan(result.frame.Value.iloc[2]))
        self.assertEqual(result.frame.Value.iloc[3], 0)

    def test_wrong_country_or_indicator_is_rejected(self):
        for field, value in [("countryiso3code", "DZA"), ("indicator", {"id": "OTHER"})]:
            response = payload([(2000, 2)])
            response[1][0][field] = value
            with self.assertRaises(DataUnavailable):
                parse_payload(response, CODE, 2001)

    def test_empty_malformed_and_incomplete_responses_are_rejected(self):
        for response in [{"message": "bad"}, [None, []], [{"pages": 2}, []], payload([(2000, None)]), [{}, []]]:
            with self.subTest(response=response), self.assertRaises(DataUnavailable):
                parse_payload(response, CODE, 2001)

    def test_invalid_numbers_and_duplicate_year_are_rejected(self):
        for values in [[(2000, "3.0")], [(2000, True)], [(2000, float("inf"))], [(2000, 2), (2000, 3)]]:
            with self.subTest(values=values), self.assertRaises(DataUnavailable):
                parse_payload(payload(values), CODE, 2001)

    def test_delta_requires_previous_calendar_year(self):
        frame = pd.DataFrame({"Year": [2000, 2001, 2002], "Value": [1.0, None, 3.0]})
        self.assertEqual(latest_metric(frame), (2002, 3.0, None))
        frame.loc[1, "Value"] = 2.25
        self.assertEqual(latest_metric(frame), (2002, 3.0, 0.75))
        self.assertIsNone(latest_metric(frame.iloc[0:0]))

    def test_csv_filters_years_keeps_precision_and_empty_cells(self):
        result = parse_payload(payload([(2000, 1.23456789), (2002, 0)]), CODE, 2002)
        table = combine_series({CODE: result}, 2001, 2002)
        self.assertEqual(table.Year.tolist(), [2001, 2002])
        text = csv_bytes(table).decode("utf-8-sig")
        self.assertIn("2001,,,", text)
        self.assertIn("2002,0.0,,", text)
        self.assertNotIn("2000,", text)
        self.assertIn("1.23456789", csv_bytes(result.frame).decode("utf-8-sig"))

    @patch("data_loader.requests.Session")
    def test_network_failure_is_a_controlled_error(self, session_cls):
        session_cls.return_value.__enter__.return_value.get.side_effect = requests.ConnectionError("offline")
        with self.assertRaises(DataUnavailable):
            fetch_indicator(CODE, 2026)

    @patch("data_loader.requests.Session")
    def test_fetch_uses_correct_country_series_and_timeout(self, session_cls):
        response = MagicMock()
        response.json.return_value = payload([(2000, 3.0)])
        session = session_cls.return_value.__enter__.return_value
        session.get.return_value = response
        result = fetch_indicator(CODE, 2026)
        args, kwargs = session.get.call_args
        self.assertEqual(args[0], f"https://api.worldbank.org/v2/country/MAR/indicator/{CODE}")
        self.assertEqual(kwargs["params"]["date"], "2000:2026")
        self.assertEqual(kwargs["timeout"], (5, 15))
        self.assertEqual(result.frame.Value.iloc[0], 3.0)
        response.raise_for_status.assert_called_once()


if __name__ == "__main__":
    unittest.main()
