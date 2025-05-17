import streamlit as st
import duckdb
import pandas as pd
import altair as alt

st.title("Interactive Finance Dashboard (SQL + Chart Config)")

# Editable SQL query input
default_query = """
SELECT
*

FROM read_csv_auto('data_fixed.csv', delim=';', header=True)
"""
query = st.text_area("SQL Query", value=default_query, height=200)

try:
    # Run the SQL query
    df = duckdb.query(query).to_df()

    # Normalize month column if present
    if 'month' in df.columns:
        df['month'] = pd.to_datetime(df['month'], errors='coerce')
        df = df[df['month'].notnull()]
        df['month'] = df['month'].dt.to_period('M').astype(str)

    st.dataframe(df)

    # Dynamic chart configuration
    if not df.empty:
        chart_type = st.selectbox(
            "Chart Type", ["None", "Bar", "Line", "Area"])
        x_options = list(df.columns)
        num_y_options = list(df.select_dtypes(include='number').columns)

        if chart_type != "None" and x_options and num_y_options:
            x_col = st.selectbox("X-Axis", x_options)
            y_cols = st.multiselect(
                "Y-Axis", num_y_options, default=num_y_options[:1])

            if x_col and y_cols:
                chart_data = df[[x_col] + y_cols].set_index(x_col)

                # Altair custom chart for proportional monthly bars
                if 'month' in df.columns and 'type' in df.columns and 'percent_share' in df.columns:
                    type_selection = alt.selection_multi(
                        fields=['type'], bind='legend')

                    chart = alt.Chart(df).mark_bar().encode(
                        x=alt.X('month:N', sort=None),
                        y='percent_share:Q',
                        color='type:N',
                        tooltip=['type', 'percent_share'],
                        opacity=alt.condition(
                            type_selection, alt.value(1), alt.value(0.1))
                    ).add_selection(
                        type_selection
                    ).properties(
                        width=700,
                        height=400,
                        title='Share of Each Type by Month (%)'
                    )

                    st.altair_chart(chart, use_container_width=True)

                if chart_type == "Bar" and len(y_cols) > 0:
                    chart_data = chart_data.sort_values(
                        by=y_cols[0], ascending=False)
                if chart_type == "Bar":
                    st.bar_chart(chart_data)
                elif chart_type == "Line":
                    st.line_chart(chart_data)
                elif chart_type == "Area":
                    st.area_chart(chart_data)

except Exception as e:
    st.error(f"Query failed: {e}")
