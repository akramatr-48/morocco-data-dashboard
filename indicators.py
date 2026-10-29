"""The dashboard's indicator catalogue and public source links."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Indicator:
    code: str
    label: str
    column: str
    color: str
    definition: str
    provider: str
    caveat: str

    @property
    def source_url(self) -> str:
        return f"https://data.worldbank.org/indicator/{self.code}?locations=MA"


COUNTRY = "MAR"
START_YEAR = 2000
INDICATORS = (
    Indicator(
        code="NY.GDP.MKTP.KD.ZG",
        label="GDP growth",
        column="GDP growth (annual %)",
        color="#147D64",
        definition="Annual change in real gross domestic product, measured at constant prices.",
        provider="National accounts, OECD and World Bank estimates, via World Development Indicators.",
        caveat="This is real economic growth, not GDP in dollars or growth in household income.",
    ),
    Indicator(
        code="FP.CPI.TOTL.ZG",
        label="Inflation",
        column="Inflation, consumer prices (annual %)",
        color="#C06A32",
        definition="Annual percentage change in the consumer price index (CPI).",
        provider="IMF International Financial Statistics, via World Development Indicators.",
        caveat="Annual inflation is not the latest monthly rate. Lower inflation does not necessarily mean falling prices.",
    ),
    Indicator(
        code="SL.UEM.TOTL.ZS",
        label="Unemployment",
        column="Unemployment, modeled ILO estimate (% of labor force)",
        color="#526FB0",
        definition="Share of the labor force without work, available for work and seeking employment (modeled ILO estimate).",
        provider="ILO modeled estimates (ILOSTAT), via World Development Indicators.",
        caveat="This internationally comparable modeled series can differ from Morocco's HCP national unemployment rate. It is not the share of the whole population.",
    ),
)
BY_CODE = {indicator.code: indicator for indicator in INDICATORS}
