"""Small, testable transformations shared by charts, metrics and exports."""

import pandas as pd

from indicators import INDICATORS


def combine_series(results: dict, start: int, end: int) -> pd.DataFrame:
    table = pd.DataFrame({"Year": range(start, end + 1)})
    for indicator in INDICATORS:
        result = results.get(indicator.code)
        if result is not None:
            values = result.frame.set_index("Year")["Value"]
            table[indicator.column] = table["Year"].map(values)
        else:
            table[indicator.column] = float("nan")
    return table


def latest_metric(frame: pd.DataFrame) -> tuple | None:
    observed = frame.dropna(subset=["Value"]).sort_values("Year")
    if observed.empty:
        return None
    row = observed.iloc[-1]
    year, value = int(row["Year"]), float(row["Value"])
    previous = observed.loc[observed["Year"] == year - 1, "Value"]
    delta = value - float(previous.iloc[0]) if not previous.empty else None
    return year, value, delta


def csv_bytes(frame: pd.DataFrame) -> bytes:
    """Keep source precision, represent unavailable values as empty cells."""
    return frame.to_csv(index=False, na_rep="").encode("utf-8-sig")
