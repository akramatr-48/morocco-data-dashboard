"""Morocco Data Dashboard — run with: python -m streamlit run app.py"""

from datetime import datetime, timezone
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from analytics import combine_series, csv_bytes, latest_metric
from data_loader import DataUnavailable, fetch_indicator
from indicators import BY_CODE, INDICATORS, START_YEAR

ROOT = Path(__file__).resolve().parent


@st.cache_data(ttl=86400, show_spinner=False)
def cached_load(code: str, end_year: int):
    return fetch_indicator(code, end_year)


def source_notes():
    st.markdown("#### Where the numbers come from")
    st.write(
        "All three annual series are retrieved from the World Bank's World "
        "Development Indicators API for Morocco (MAR). No API key is required."
    )
    for item in INDICATORS:
        with st.expander(item.column):
            st.write(item.definition)
            st.caption(item.provider)
            st.info(item.caveat)
            st.markdown(f"[View original series on World Bank Data]({item.source_url})")
            st.code(item.code, language=None)
    st.markdown(
        "**Reading this dashboard**\n\n"
        "- The year is the observation year, not the date the data was downloaded.\n"
        "- Missing observations stay empty. We never replace them with zero or interpolate them.\n"
        "- Line charts break at missing years. Cards use the latest non-missing value inside your selected period.\n"
        "- Changes are percentage points (pp) versus the previous calendar year inside the selected period.\n"
        "- ILO modeled unemployment may differ from HCP national figures.\n"
        "- Values can be revised by the source; recent observations may be estimates.\n"
        "- Retrieved data is cached for up to 24 hours. Refresh data requests a new copy.\n"
        "- Exports preserve the source's numeric precision; display values are rounded."
    )
    st.caption(
        "Data: World Bank, World Development Indicators · CC BY 4.0. "
        "The World Bank does not endorse this independent portfolio project."
    )


def trend_chart(frame: pd.DataFrame, item, style: str):
    plot = frame.copy()
    # Separate line segments so a missing year never implies an observation.
    plot["Segment"] = plot["Value"].isna().cumsum()
    observed = plot.dropna(subset=["Value"])
    base = alt.Chart(observed).encode(
        x=alt.X(
            "Year:Q",
            title=None,
            axis=alt.Axis(format="d", tickMinStep=1, grid=False, labelAngle=0),
            scale=alt.Scale(domain=[int(frame.Year.min()) - 0.4, int(frame.Year.max()) + 0.4]),
        ),
        y=alt.Y("Value:Q", title="Percent (%)", scale=alt.Scale(zero=True)),
        tooltip=[
            alt.Tooltip("Year:Q", title="Year", format="d"),
            alt.Tooltip("Value:Q", title=item.label + " (%)", format=".2f"),
        ],
    )
    zero = alt.Chart(pd.DataFrame({"zero": [0]})).mark_rule(
        color="#CCD5D9", strokeDash=[4, 4]
    ).encode(y="zero:Q")
    if style == "Bars":
        chart = zero + base.mark_bar(color=item.color, cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
    else:
        area = base.mark_area(color=item.color, opacity=0.08).encode(detail="Segment:N")
        line = base.mark_line(color=item.color, strokeWidth=3).encode(detail="Segment:N")
        dots = base.mark_circle(color=item.color, size=45)
        chart = zero + area + line + dots
    return (
        chart.properties(height=330)
        .configure_view(strokeWidth=0)
        .configure_axis(
            labelColor="#637785",
            titleColor="#637785",
            gridColor="#EAF0F2",
            domain=False,
            labelFontSize=12,
            titleFontSize=12,
            titlePadding=15,
        )
    )


def main():
    st.set_page_config(
        page_title="Morocco Data Dashboard",
        page_icon="🇲🇦",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(f"<style>{(ROOT / 'assets' / 'style.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

    with st.sidebar:
        st.markdown(
            '<div class="brand"><span class="brand-mark">✦</span>'
            '<div>MOROCCO<span>DATA DASHBOARD</span></div></div>',
            unsafe_allow_html=True,
        )
        st.caption("A small window into a changing economy.")
        st.divider()
        st.markdown("##### Explore the data")
        code = st.selectbox(
            "Economic indicator",
            options=list(BY_CODE),
            format_func=lambda value: BY_CODE[value].label,
        )
        st.caption("Country · Morocco (MAR)\n\nFrequency · Annual\n\nCoverage · From 2000")

    st.markdown(
        '<div class="eyebrow">MOROCCO / ECONOMIC OBSERVATORY</div>'
        '<h1>A clearer view of Morocco’s economy.</h1>'
        '<p class="intro">Growth, prices and employment. Explore the numbers '
        'behind the story, with open data from the World Bank.</p>',
        unsafe_allow_html=True,
    )

    current_year = datetime.now(timezone.utc).year
    results, failures = {}, {}
    with st.spinner("Retrieving Morocco's economic indicators…"):
        for item in INDICATORS:
            try:
                results[item.code] = cached_load(item.code, current_year)
            except DataUnavailable as exc:
                failures[item.code] = str(exc)

    with st.sidebar:
        refresh = st.button("Refresh data", icon=":material/refresh:", width="stretch")
        if refresh:
            cached_load.clear()
            st.rerun()
        st.caption("Source responses are cached for up to 24 hours.")
        st.divider()
        st.markdown("[View project on GitHub](https://github.com/akramatr-48/morocco-data-dashboard)")
        st.caption("Independent open-source portfolio project.")

    if not results:
        st.error("The World Bank data service could not be reached. Check your connection, then select Refresh data.")
        st.info("No sample values are substituted. Your dashboard will display real observations when the source is available.")
        with st.expander("Data sources and definitions"):
            source_notes()
        st.stop()

    last_year = max(
        int(result.frame.dropna(subset=["Value"])["Year"].max())
        for result in results.values()
    )
    with st.sidebar:
        if last_year > START_YEAR:
            start, end = st.slider(
                "Year range",
                START_YEAR,
                last_year,
                (START_YEAR, last_year),
                step=1,
            )
        else:
            start = end = START_YEAR
            st.caption(f"Available period: {START_YEAR}")

    st.markdown(
        f'<div class="period-strip"><span class="status-dot"></span>'
        f' WORLD BANK · ANNUAL DATA <span class="period-range">{start} — {end}</span></div>',
        unsafe_allow_html=True,
    )
    for failed_code in failures:
        st.warning(f"{BY_CODE[failed_code].label} is temporarily unavailable. Other series are still shown.")

    columns = st.columns(3, gap="medium")
    for col, item in zip(columns, INDICATORS):
        with col:
            result = results.get(item.code)
            frame = None if result is None else result.frame.query("@start <= Year <= @end")
            metric = None if frame is None else latest_metric(frame)
            with st.container(border=True):
                st.markdown(f'<div class="metric-label" style="color:{item.color}">{item.label.upper()}</div>', unsafe_allow_html=True)
                if metric is None:
                    st.metric("Latest in selected period", "—", label_visibility="collapsed")
                    st.caption("No observation in selected period")
                else:
                    year, value, delta = metric
                    st.metric(
                        "Latest in selected period",
                        f"{value:.2f}%",
                        delta=None if delta is None else f"{delta:+.2f} pp vs {year - 1}",
                        delta_color="off",
                        label_visibility="collapsed",
                    )
                    st.caption(f"Latest in selected period · {year}")
                if item.label == "Unemployment":
                    st.caption("Modeled ILO estimate · % of labor force")
                else:
                    st.caption("Annual percentage change")

    st.caption("Each card can refer to a different year. pp = percentage points; changes compare consecutive calendar years in the selected period.")
    table = combine_series(results, start, end)
    explore_tab, data_tab, sources_tab = st.tabs(["Explore trends", "Data & export", "Sources & methods"])
    selected = BY_CODE[code]

    with explore_tab:
        with st.container(border=True):
            heading, controls = st.columns([3, 1])
            with heading:
                st.markdown(f"### {selected.label}, over time")
                st.caption(selected.definition)
            with controls:
                style = st.radio("Chart style", ["Line", "Bars"], horizontal=True)

            if code not in results:
                st.warning("This series is unavailable. Choose another indicator or refresh the data.")
            else:
                selected_frame = results[code].frame.query("@start <= Year <= @end").copy()
                observed = selected_frame.dropna(subset=["Value"])
                if observed.empty:
                    st.info("No observations in this period. Select a wider year range.")
                else:
                    st.altair_chart(trend_chart(selected_frame, selected, style), width="stretch")
                    count = len(observed)
                    missing = len(selected_frame) - count
                    st.caption(f"{count} observations · {missing} missing years · Missing values are not interpolated")
                    left, right = st.columns([3, 1])
                    with left:
                        st.markdown(f"[Source: World Bank · {selected.code}]({selected.source_url})")
                    with right:
                        export = selected_frame.rename(columns={"Value": selected.column})
                        st.download_button(
                            "Download this series ↓",
                            csv_bytes(export),
                            file_name=f"morocco_{selected.code}_{start}_{end}.csv",
                            mime="text/csv",
                            width="stretch",
                        )
        st.info(selected.caveat)

    with data_tab:
        st.markdown("### The numbers behind the charts")
        st.caption("All three indicators for the selected period. A dash means unavailable; exported CSV cells stay empty.")
        st.dataframe(
            table.sort_values("Year", ascending=False),
            hide_index=True,
            width="stretch",
            column_config={
                "Year": st.column_config.NumberColumn("Year", format="%d"),
                **{item.column: st.column_config.NumberColumn(item.label + " (%)", format="%.2f") for item in INDICATORS},
            },
        )
        st.download_button(
            "Download all indicators · CSV",
            csv_bytes(table),
            file_name=f"morocco_economic_indicators_{start}_{end}.csv",
            mime="text/csv",
            type="primary",
        )
        st.caption("Data attribution: World Bank, World Development Indicators (CC BY 4.0). Unemployment uses modeled ILO estimates.")

    with sources_tab:
        source_notes()
        st.markdown("#### Source response details")
        metadata_rows = [
            {
                "Indicator": item.label,
                "Source last updated": results[item.code].source_updated,
                "Retrieved (UTC)": results[item.code].retrieved_utc,
            }
            for item in INDICATORS
            if item.code in results
        ]
        st.dataframe(pd.DataFrame(metadata_rows), hide_index=True, width="stretch")
        st.caption("Source last updated is the date reported in the API response; it may describe the dataset rather than this individual series.")

    st.divider()
    st.markdown(
        '<div class="footer"><strong>MOROCCO DATA DASHBOARD</strong>'
        '<span>Open data. Clearer perspective.</span></div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
