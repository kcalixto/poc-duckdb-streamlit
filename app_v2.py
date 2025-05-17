import pandas as pd
import duckdb
import streamlit as st
import altair as alt
from statsmodels.tsa.statespace.sarimax import SARIMAX

# SQL aggregation by month + raw category
query = """
WITH data AS (
    SELECT
        date_trunc('month', TRY_CAST(Date AS DATE)) AS month,
        category,
        value
    FROM read_csv_auto('data_2_fixed.csv', delim=';', header=True)
    WHERE value < 0
),
agg AS (
    SELECT
        month,
        category,
        SUM(value) AS total
    FROM data
    GROUP BY month, category
)
SELECT
    month,
    category,
    total
FROM agg
ORDER BY month ASC
"""

# Load and preprocess
df = duckdb.query(query).to_df()
df['month'] = pd.to_datetime(df['month'])
df = df[df['month'].notnull()]
df['month'] = df['month'].dt.to_period('M').dt.to_timestamp()

# Top 3 categories
top_categories = ['Fun', 'Necessities']
df['type'] = df['category'].apply(
    lambda c: c if c in top_categories else 'Others')

# Aggregate adjusted types
df = df.groupby(['month', 'type'], as_index=False)['total'].sum()

# Forecasting
future_frames = []
forecast_end = '2025-12-31'

for group_type in df['type'].unique():
    sub = df[df['type'] == group_type].sort_values('month')

    if len(sub) < 12:
        continue

    ts = sub.set_index('month')['total'].resample('MS').sum().fillna(0)

    try:
        model = SARIMAX(ts, order=(1, 1, 1), seasonal_order=(1, 0, 1, 12),
                        enforce_stationarity=False, enforce_invertibility=False)
        model_fit = model.fit(disp=False)

        forecast_periods = 12  # number of future months
        future_months = pd.date_range(
            sub['month'].max() + pd.offsets.MonthBegin(), periods=forecast_periods, freq='MS'
        )

        predictions = model_fit.predict(
            start=future_months[0], end=future_months[-1])

        future_df = pd.DataFrame({
            'month': future_months,
            'type': group_type,
            'total': predictions
        })

        future_frames.append(future_df)

    except Exception as e:
        st.warning(f"Forecasting failed for type '{group_type}': {e}")
        continue

# Combine historical + forecasted
historical_df = df[['month', 'type', 'total']].copy()
historical_df['source'] = 'historical'

for f in future_frames:
    f['source'] = 'forecast'

forecast_df = pd.concat([historical_df] + future_frames)
forecast_df = forecast_df.sort_values(['type', 'month'])

# Streamlit output
st.dataframe(forecast_df)

# Get forecast boundary for visual marker
transition_month = historical_df['month'].max()

# Line chart with distinction for forecast vs historical
chart = alt.Chart(forecast_df).mark_line(strokeWidth=3).encode(
    x='month:T',
    y='total:Q',
    color='type:N',
    tooltip=['type', 'month', 'total', 'source']
)

# Add vertical rule at forecast boundary
rule = alt.Chart(pd.DataFrame({'month': [transition_month]})).mark_rule(
    color='red', strokeWidth=2
).encode(
    x='month:T'
)

# Combine and render
final_chart = (chart + rule).properties(
    width=700,
    height=400,
    title='Historical + Forecasted Totals by Type (Fun, Necessities, Others)'
)

st.altair_chart(final_chart, use_container_width=True)
