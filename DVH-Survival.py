# dvh_metrics_with_cif_app.py
import streamlit as st
import pandas as pd
import numpy as np
import os
import openpyxl  # for reading .xlsx
import plotly.graph_objects as go

st.set_page_config(layout="wide")

# ---------------- Metric definitions ----------------
Dcc_values = {
    "D0.035cc": 0.035, "D0.1cc": 0.1, "D0.5cc": 0.5, "D2cc": 2, "D5cc": 5,
    "D10cc": 10, "D15cc": 15, "D20cc": 20, "D25cc": 25, "D30cc": 30,
    "D35cc": 35, "D40cc": 40, "D45cc": 45, "D50cc": 50, "D55cc": 55,
    "D60cc": 60, "D65cc": 65, "D70cc": 70, "D75cc": 75, "D80cc": 80,
    "D85cc": 85, "D90cc": 90, "D95cc": 95, "D100cc": 100,
}

D_percent_values = {
    "D2%": 0.02, "D5%": 0.05, "D10cc(Gy)%": 0.10, "D15%": 0.15, "D20%": 0.20,
    "D25%": 0.25, "D30%": 0.30, "D35%": 0.35, "D40%": 0.40, "D45%": 0.45,
    "D50%": 0.50, "D55%": 0.55, "D60%": 0.60, "D65%": 0.65, "D70%": 0.70,
    "D75%": 0.75, "D80%": 0.80, "D85%": 0.85, "D90%": 0.90, "D95%": 0.95,
    "D97%": 0.97, "D98%": 0.98, "D99%": 0.99
}

# V metrics dose grid (in cGy)
doses = [500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000,
         5500, 6000, 6500, 7000]

# ---------------- Sidebar: sample data downloads ----------------
def sample_downloads_sidebar():
    st.sidebar.header("Sample DVH datasets")
    for label, fname in [
        ("High risk sample (.xlsx)", "high_risk_sample.xlsx"),
        ("Low risk sample (.xlsx)",  "low_risk_sample.xlsx"),
    ]:
        if os.path.exists(fname):
            with open(fname, "rb") as f:
                st.sidebar.download_button(
                    label=f"Download {label}",
                    data=f,
                    file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
        else:
            st.sidebar.info(f"Place **{fname}** in the app folder to enable download.")

# ---------------- DVH processors ----------------
def process_excel(uploaded_file):
    try:
        xls = pd.ExcelFile(uploaded_file, engine='openpyxl')
        sheet_names = xls.sheet_names
        st.write(f"**Processing file:** {uploaded_file.name}")

        Dcc_metrics, D_percent_metrics, Vcc_metrics, V_percent_metrics = {}, {}, {}, {}

        for sheet_name in sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name, header=None).fillna(0)

            # Dcc
            for metric, volume in Dcc_values.items():
                diff = np.abs(df.iloc[1:, 1:].values - volume)
                if diff.size == 0:
                    st.warning(f"No data in '{sheet_name}' for '{metric}'.")
                    continue
                r, c = np.unravel_index(np.argmin(diff), diff.shape)
                dose_row, dose_col = df.iat[r + 1, 0], df.iat[0, c + 1]
                try:
                    dose = int(dose_row + dose_col)  # cGy
                except Exception:
                    st.warning(f"Non-integer dose in '{sheet_name}' for '{metric}'.")
                    continue
                Dcc_metrics[f"{metric}(Gy)"] = dose / 100.0  # cGy -> Gy

            # total volume for percentages
            total_volume = df.iat[1, 1] if (df.shape[0] > 1 and df.shape[1] > 1) else 0
            if total_volume == 0:
                st.warning(f"Insufficient data in '{sheet_name}' for total volume.")

            # D%
            for metric, pct in D_percent_values.items():
                key = f"{metric}(Gy)"
                if total_volume == 0:
                    D_percent_metrics[key] = np.nan
                    continue
                v_thresh = pct * total_volume
                diff = np.abs(df.iloc[1:, 1:].values - v_thresh)
                if diff.size == 0:
                    st.warning(f"No data in '{sheet_name}' for '{metric}'.")
                    continue
                r, c = np.unravel_index(np.argmin(diff), diff.shape)
                dose_row, dose_col = df.iat[r + 1, 0], df.iat[0, c + 1]
                try:
                    dose = int(dose_row + dose_col)
                except Exception:
                    st.warning(f"Non-integer dose in '{sheet_name}' for '{metric}'.")
                    continue
                D_percent_metrics[key] = dose / 100.0

            # Vcc / V%
            try:
                header = df.iloc[0, 1:].astype(float)
                index = df.iloc[1:, 0].astype(float)
            except ValueError:
                st.warning(f"Non-numeric headers/index in '{sheet_name}'. Skipping V metrics.")
                continue

            for d in doses:
                diff = np.abs(index.values[:, None] + header.values - d)
                if diff.size == 0:
                    st.warning(f"No data for dose {d} in '{sheet_name}'.")
                    continue
                r, c = np.unravel_index(np.argmin(diff), diff.shape)
                try:
                    vol = df.iloc[r + 1, c + 1]
                except IndexError:
                    st.warning(f"Index OOB for dose {d} in '{sheet_name}'.")
                    continue
                tag = f"V{int(d/100)}Gy"
                Vcc_metrics[f"{tag}(cc)"] = vol
                V_percent_metrics[f"{tag}(%)"] = round((vol / total_volume) * 100.0, 1) if total_volume else np.nan

        return (
            pd.DataFrame([Dcc_metrics], index=['Dcc']),
            pd.DataFrame([D_percent_metrics], index=['D%']),
            pd.DataFrame([Vcc_metrics], index=['Vcc']),
            pd.DataFrame([V_percent_metrics], index=['V%'])
        )
    except Exception as e:
        st.error(f"Error processing Excel: {e}")
        return None, None, None, None

def process_csv(csv_file):
    try:
        st.write(f"**Processing file:** {csv_file.name}")
        df = pd.read_csv(csv_file, header=None)
        if df.empty:
            st.error("Uploaded CSV is empty.")
            return None, None, None, None
        df = df.fillna(0)

        Dcc_metrics, D_percent_metrics, Vcc_metrics, V_percent_metrics = {}, {}, {}, {}

        # Dcc
        for metric, volume in Dcc_values.items():
            diff = np.abs(df.iloc[1:, 1:].values - volume)
            if diff.size == 0:
                st.warning(f"No data for '{metric}'.")
                continue
            r, c = np.unravel_index(np.argmin(diff), diff.shape)
            dose_row, dose_col = df.iat[r + 1, 0], df.iat[0, c + 1]
            try:
                dose = int(dose_row + dose_col)
            except Exception:
                st.warning(f"Non-integer dose for '{metric}'.")
                continue
            Dcc_metrics[f"{metric}(Gy)"] = dose / 100.0

        # total volume
        total_volume = df.iat[1, 1] if (df.shape[0] > 1 and df.shape[1] > 1) else 0
        if total_volume == 0:
            st.warning("Insufficient data for total volume.")

        # D%
        for metric, pct in D_percent_values.items():
            key = f"{metric}(Gy)"
            if total_volume == 0:
                D_percent_metrics[key] = np.nan
                continue
            v_thresh = pct * total_volume
            diff = np.abs(df.iloc[1:, 1:].values - v_thresh)
            if diff.size == 0:
                st.warning(f"No data for '{metric}'.")
                continue
            r, c = np.unravel_index(np.argmin(diff), diff.shape)
            dose_row, dose_col = df.iat[r + 1, 0], df.iat[0, c + 1]
            try:
                dose = int(dose_row + dose_col)
            except Exception:
                st.warning(f"Non-integer dose for '{metric}'.")
                continue
            D_percent_metrics[key] = dose / 100.0

        # Vcc / V%
        try:
            header = df.iloc[0, 1:].astype(float)
            index = df.iloc[1:, 0].astype(float)
        except ValueError:
            st.warning("Non-numeric headers/index. Skipping V metrics.")
            header = pd.Series(dtype=float)
            index = pd.Series(dtype=float)

        for d in doses:
            diff = np.abs(index.values[:, None] + header.values - d)
            if diff.size == 0:
                st.warning(f"No data for dose {d}.")
                continue
            r, c = np.unravel_index(np.argmin(diff), diff.shape)
            try:
                vol = df.iloc[r + 1, c + 1]
            except IndexError:
                st.warning(f"Index OOB for dose {d}.")
                continue
            tag = f"V{int(d/100)}Gy"
            Vcc_metrics[f"{tag}(cc)"] = vol
            V_percent_metrics[f"{tag}(%)"] = round((vol / total_volume) * 100.0, 1) if total_volume else np.nan

        return (
            pd.DataFrame([Dcc_metrics], index=['Dcc']),
            pd.DataFrame([D_percent_metrics], index=['D%']),
            pd.DataFrame([Vcc_metrics], index=['Vcc']),
            pd.DataFrame([V_percent_metrics], index=['V%'])
        )
    except Exception as e:
        st.error(f"Error processing CSV: {e}")
        return None, None, None, None

# ---------------- Risk flag (D10cc only) ----------------
def determine_risk_group(Dcc_df):
    """
    High risk if D10cc(Gy) > 59.2 (derived from the cited article).
    """
    is_high_risk, messages = False, []
    if 'D10cc(Gy)' in Dcc_df.columns:
        v = Dcc_df.at['Dcc', 'D10cc(Gy)']
        if pd.notnull(v) and v > 59.2:
            is_high_risk = True
            messages.append("D10cc(Gy) > 59.2")
    return is_high_risk, messages

# ---------------- Reconstructed CIF (Fig 1A: ORN1–4, High vs Low) ----------------
def cif_series_figure_1A():
    # times in months
    t = [0, 6, 12, 18, 24, 30, 36, 42, 48, 54, 60, 72, 84, 96, 108, 114]
    # High-risk (red): 11.7% @60m; 18.8% @114m
    y_high = [0.000, 0.010, 0.030, 0.055, 0.072, 0.085, 0.095, 0.102,
              0.108, 0.113, 0.117, 0.125, 0.135, 0.155, 0.175, 0.188]
    # Low-risk (blue): 3.5% @60m; 5.8% @114m
    y_low  = [0.000, 0.002, 0.008, 0.012, 0.016, 0.020, 0.024, 0.028,
              0.031, 0.034, 0.035, 0.040, 0.045, 0.052, 0.056, 0.058]
    return t, y_high, y_low

def plot_cif_figure_1A():
    t, y_high, y_low = cif_series_figure_1A()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=t, y=y_high, mode="lines", name="ORN (ClinRad:1–4) - High risk",
        line=dict(color="red", width=2),
        hovertemplate="Time: %{x} months<br>CIF: %{y:.3f}<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=t, y=y_low, mode="lines", name="ORN (ClinRad:1–4) - Low risk",
        line=dict(color="blue", width=2),
        hovertemplate="Time: %{x} months<br>CIF: %{y:.3f}<extra></extra>"
    ))
    fig.update_layout(
        title="Cumulative Incidence Functions by Risk Group in Princess Margaret Cancer Center",
        xaxis_title="Time (months)",
        yaxis_title="Cumulative Incidence",
        hovermode="x unified",
        width=1000, height=500,
        xaxis=dict(range=[0, 114], showspikes=True, spikemode="across"),
        yaxis=dict(range=[0, 0.41]),
        margin=dict(l=40, r=20, t=60, b=60),
        legend_title_text=None,
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------------- UI ----------------
def main():
    st.title("DVH Metrics Calculator & Risk Flag")

    st.write(
        "Upload a CSV or Excel file containing a **cumulative DVH table** "
        "Synthetic example data files for both low-risk and high-risk patients are provided in the left sidebar. Users can download these files and upload them to the tool to test its functionality. "
        "The app computes Dcc(Gy), D%(Gy), VGy(cc), and VGy(%) and flags whether the person "
        "is **high-risk** or **low-risk**. "
        "Risk classification is based **only on D10cc (Gy)** with a cut-off of **59.2 Gy**, "
        "as described in the referenced article: "
        "[ScienceDirect article](https://www.sciencedirect.com/science/article/pii/S0167814025045001)."
    )

    # Sidebar download buttons
    sample_downloads_sidebar()

    uploaded_file = st.file_uploader("Choose a CSV or Excel file", type=['csv', 'xlsx', 'xls'])

    if uploaded_file is not None:
        uploaded_file.seek(0)

        if uploaded_file.name.endswith(('.xlsx', '.xls')):
            Dcc_df, D_percent_df, Vcc_df, V_percent_df = process_excel(uploaded_file)
        elif uploaded_file.name.endswith('.csv'):
            Dcc_df, D_percent_df, Vcc_df, V_percent_df = process_csv(uploaded_file)
        else:
            st.error("Unsupported file type. Please upload a CSV or Excel file.")
            return

        if all(x is not None for x in [Dcc_df, D_percent_df, Vcc_df, V_percent_df]):
            st.subheader("Dcc (Gy)")
            st.dataframe(Dcc_df, use_container_width=True)

            st.subheader("D% (Gy)")
            st.dataframe(D_percent_df, use_container_width=True)

            st.subheader("VGy (cc)")
            st.dataframe(Vcc_df, use_container_width=True)

            st.subheader("VGy (%)")
            st.dataframe(V_percent_df, use_container_width=True)

            # Risk assessment (D10cc only)
            is_high_risk, msgs = determine_risk_group(Dcc_df)
            st.subheader("Risk Group")
            if is_high_risk:
                st.error(f"**High-risk** — {'; '.join(msgs) if msgs else 'D10cc(Gy) > 59.2'}")
            else:
                st.success("**Low-risk** — does not meet the D10cc(Gy) > 59.2 criterion.")

            # ----- Interactive CIF figure (always shown at the end) -----
            st.markdown("---")
            st.subheader("Cumulative Incidence Functions (interactive)")
            plot_cif_figure_1A()

if __name__ == "__main__":
    main()
