"""Exercise user flows through Streamlit's real AppTest runner, with test-only data."""

from pathlib import Path
import unittest
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

from data_loader import DataUnavailable, parse_payload
from indicators import INDICATORS

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def fixture_fetch(code, end_year):
    offset = [item.code for item in INDICATORS].index(code)
    return parse_payload(
        [
            {"pages": 1, "lastupdated": "2026-01-01"},
            [
                {"date": str(year), "value": value, "countryiso3code": "MAR", "indicator": {"id": code}}
                for year, value in [(2000, 1 + offset), (2001, None), (2002, 2 + offset), (2003, 3 + offset)]
            ],
        ],
        code,
        end_year,
    )


class AppChecks(unittest.TestCase):
    def setUp(self):
        st.cache_data.clear()

    @patch("data_loader.fetch_indicator", side_effect=fixture_fetch)
    def test_indicator_period_and_chart_controls(self, _fetch):
        app = AppTest.from_file(APP, default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.metric), 3)
        self.assertEqual(app.metric[0].value, "3.00%")
        app.selectbox[0].select(INDICATORS[2].code).run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Unemployment, over time" in str(element.value) for element in app.markdown))
        app.radio[0].set_value("Bars").run()
        self.assertFalse(app.exception)
        app.slider[0].set_range(2000, 2001).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "1.00%")
        exported_table = app.dataframe[0].value
        self.assertEqual(sorted(exported_table.Year.tolist()), [2000, 2001])
        app.slider[0].set_range(2001, 2001).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "—")
        self.assertTrue(any("No observations" in message.value for message in app.info))

    @patch("data_loader.fetch_indicator", side_effect=DataUnavailable("offline"))
    def test_offline_state_is_actionable_and_has_no_fabricated_metrics(self, _fetch):
        app = AppTest.from_file(APP, default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.metric), 0)
        self.assertTrue(any("could not be reached" in message.value for message in app.error))
        self.assertTrue(any("No sample values" in message.value for message in app.info))
        self.assertTrue(any(button.label == "Refresh data" for button in app.button))

    def test_one_source_failure_does_not_hide_other_series(self):
        def partial(code, end_year):
            if code == INDICATORS[1].code:
                raise DataUnavailable("offline")
            return fixture_fetch(code, end_year)

        with patch("data_loader.fetch_indicator", side_effect=partial):
            app = AppTest.from_file(APP, default_timeout=30).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.metric[1].value, "—")
            app.selectbox[0].select(INDICATORS[1].code).run()
            self.assertFalse(app.exception)
            self.assertTrue(any("Choose another indicator" in message.value for message in app.warning))


if __name__ == "__main__":
    unittest.main()
