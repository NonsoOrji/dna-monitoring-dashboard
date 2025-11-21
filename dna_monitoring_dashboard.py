import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

st.set_page_config(page_title="DNA Concentration Monitoring", page_icon="🧬", layout="wide", initial_sidebar_state="expanded")

st.title("🧬 DNA Concentration Monitoring Dashboard")
st.markdown("Real-time monitoring of SpectraMax DNA concentration assays with statistical analysis")

def get_db_connection():
    return sqlite3.connect('C:/DNA_Monitoring_Data/dna_monitoring.db', check_same_thread=False)

conn = get_db_connection()

with st.sidebar:
    st.header("📊 Filters & Options")
    date_from = st.date_input("From Date", value=datetime(2025, 11, 1))
    date_to = st.date_input("To Date", value=datetime.now())
    
    instruments_df = pd.read_sql_query("SELECT DISTINCT instrument FROM runs WHERE instrument IS NOT NULL", conn)
    if len(instruments_df) > 0:
        instruments = ["All Instruments"] + instruments_df['instrument'].unique().tolist()
        selected_instrument = st.selectbox("Select Instrument", instruments)
    else:
        selected_instrument = "All Instruments"
    
    st.divider()
    st.info("📊 Real-time dashboard - updates every sync")

date_from_str = str(date_from)
date_to_str = str(date_to)

instrument_filter = "" if selected_instrument == "All Instruments" else f" AND instrument = '{selected_instrument}'"

runs_query = f"""
SELECT run_id, lhi_id, lhi_completion_datetime, instrument, std_read_datetime, std_delta_time_min,
       std_01_rfu, std_07_rfu, blank_rfu, sn_std7_blank, 
       (SELECT COUNT(*) FROM qplates q WHERE q.run_id = r.run_id AND q.lhi_id = r.lhi_id AND q.lhi_completion_datetime = r.lhi_completion_datetime) as qplate_count
FROM runs r
WHERE lhi_completion_datetime >= '{date_from_str}' AND lhi_completion_datetime <= '{date_to_str}'{instrument_filter}
ORDER BY lhi_completion_datetime DESC
"""

qplates_query = f"""
SELECT run_id, lhi_id, lhi_completion_datetime, qplate_number, qhigh_conc_ng_ul, qlow_conc_ng_ul, 
       qblank_conc_ng_ul, sn_qplate, overall_plate_qc, read_datetime, delta_time_min, instrument
FROM qplates
WHERE lhi_completion_datetime >= '{date_from_str}' AND lhi_completion_datetime <= '{date_to_str}'{instrument_filter}
ORDER BY lhi_completion_datetime DESC
"""

stats_query = "SELECT metric_name, instrument, mean_value, min_value, max_value, std_value, p25_value, p50_value, p75_value, p95_value FROM statistics"

runs_df = pd.read_sql_query(runs_query, conn)
qplates_df = pd.read_sql_query(qplates_query, conn)
stats_df = pd.read_sql_query(stats_query, conn)

if len(runs_df) == 0:
    st.warning("No data available for selected date range")
else:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 By-Run Details", "📈 Trends & Analysis", "📊 Distribution Analysis", "🎯 Q-Plate Analysis", "📉 Statistical Summary"])
    
    with tab1:
        st.subheader(f"All Runs ({len(runs_df)} total)")
        
        for idx, run in runs_df.iterrows():
            with st.expander(f"🔬 {run['lhi_id']} | {run['lhi_completion_datetime']} | {run['instrument'].split(' - ')[-1]}", expanded=(idx==0)):
                
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    status_std01 = "🟢" if 40000000 < run['std_01_rfu'] < 42000000 else "🟡" if 39000000 < run['std_01_rfu'] < 43000000 else "🔴"
                    st.metric("Std-01 RFU", f"{run['std_01_rfu']:.0f}", delta=status_std01)
                
                with col2:
                    status_std07 = "🟢" if 300000 < run['std_07_rfu'] < 400000 else "🟡" if 200000 < run['std_07_rfu'] < 450000 else "🔴"
                    st.metric("Std-07 RFU", f"{run['std_07_rfu']:.0f}", delta=status_std07)
                
                with col3:
                    st.metric("Blank RFU", f"{run['blank_rfu']:.0f}")
                
                with col4:
                    status_sn = "🟢" if run['sn_std7_blank'] > 3.0 else "🟡" if run['sn_std7_blank'] > 2.5 else "🔴"
                    st.metric("S/N (Std-7/Blank)", f"{run['sn_std7_blank']:.2f}", delta=status_sn)
                
                with col5:
                    st.metric("Std Read Time", f"{run['std_delta_time_min']:.1f} min")
                
                st.divider()
                
                run_qplates = qplates_df[(qplates_df['run_id'] == run['run_id']) & 
                                         (qplates_df['lhi_id'] == run['lhi_id']) & 
                                         (qplates_df['lhi_completion_datetime'] == run['lhi_completion_datetime'])]
                
                st.write(f"**Q-Plates ({len(run_qplates)} plates)**")
                
                if len(run_qplates) > 0:
                    for qidx, qplate in run_qplates.iterrows():
                        qcol1, qcol2, qcol3, qcol4, qcol5 = st.columns(5)
                        
                        with qcol1:
                            st.metric(f"Q{qplate['qplate_number']} High", f"{qplate['qhigh_conc_ng_ul']:.2f} ng/uL")
                        with qcol2:
                            st.metric(f"Q{qplate['qplate_number']} Low", f"{qplate['qlow_conc_ng_ul']:.3f} ng/uL")
                        with qcol3:
                            st.metric(f"Q{qplate['qplate_number']} Blank", f"{qplate['qblank_conc_ng_ul']}")
                        with qcol4:
                            st.metric(f"Q{qplate['qplate_number']} S/N", f"{qplate['sn_qplate']:.2f}")
                        with qcol5:
                            qc_status = "🟢 PASS" if qplate['overall_plate_qc'] == "PASS" else "🟡 WARNING" if qplate['overall_plate_qc'] == "WARNING" else "🔴 FAIL"
                            st.metric(f"Q{qplate['qplate_number']} QC", qc_status)
    
    with tab2:
        st.subheader("Trends Over Time")
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig_std01 = px.line(runs_df, x='lhi_completion_datetime', y='std_01_rfu', markers=True, 
                               title="Standard-01 RFU Trend", color_discrete_sequence=['#1f77b4'])
            fig_std01.add_hline(y=40000000, line_dash="dash", line_color="green", annotation_text="Target")
            fig_std01.add_hrect(39000000, 41000000, fillcolor="green", opacity=0.1)
            fig_std01.update_layout(hovermode='x unified', height=400, template="plotly_white")
            st.plotly_chart(fig_std01, use_container_width=True)
        
        with col2:
            fig_std07 = px.line(runs_df, x='lhi_completion_datetime', y='std_07_rfu', markers=True,
                               title="Standard-07 RFU Trend", color_discrete_sequence=['#ff7f0e'])
            fig_std07.add_hline(y=350000, line_dash="dash", line_color="green", annotation_text="Target")
            fig_std07.update_layout(hovermode='x unified', height=400, template="plotly_white")
            st.plotly_chart(fig_std07, use_container_width=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig_blank = px.line(runs_df, x='lhi_completion_datetime', y='blank_rfu', markers=True,
                               title="Blank RFU Trend", color_discrete_sequence=['#2ca02c'])
            fig_blank.update_layout(hovermode='x unified', height=400, template="plotly_white")
            st.plotly_chart(fig_blank, use_container_width=True)
        
        with col2:
            fig_sn = px.line(runs_df, x='lhi_completion_datetime', y='sn_std7_blank', markers=True,
                            title="S/N Ratio Trend", color_discrete_sequence=['#d62728'])
            fig_sn.add_hline(y=3.0, line_dash="dash", line_color="green", annotation_text="Target (3.0)")
            fig_sn.add_hline(y=2.5, line_dash="dash", line_color="orange", annotation_text="Warning (2.5)")
            fig_sn.add_hline(y=2.0, line_dash="dash", line_color="red", annotation_text="Critical (2.0)")
            fig_sn.update_layout(hovermode='x unified', height=400, template="plotly_white")
            st.plotly_chart(fig_sn, use_container_width=True)
    
    with tab3:
        st.subheader("Distribution Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig_box_std01 = px.box(runs_df, y='std_01_rfu', title="Std-01 Distribution",
                                  points="all", color_discrete_sequence=['#1f77b4'])
            st.plotly_chart(fig_box_std01, use_container_width=True)
        
        with col2:
            fig_box_std07 = px.box(runs_df, y='std_07_rfu', title="Std-07 Distribution",
                                  points="all", color_discrete_sequence=['#ff7f0e'])
            st.plotly_chart(fig_box_std07, use_container_width=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig_violin_sn = px.violin(runs_df, y='sn_std7_blank', title="S/N Ratio Distribution",
                                     box=True, points="all", color_discrete_sequence=['#d62728'])
            st.plotly_chart(fig_violin_sn, use_container_width=True)
        
        with col2:
            if len(runs_df[runs_df['instrument'].notna()]) > 0:
                fig_box_by_inst = px.box(runs_df[runs_df['instrument'].notna()], y='sn_std7_blank', 
                                        x='instrument', title="S/N by Instrument", color='instrument')
                st.plotly_chart(fig_box_by_inst, use_container_width=True)
    
    with tab4:
        st.subheader("Q-Plate Control Analysis")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            qhigh_data = qplates_df[qplates_df['qhigh_conc_ng_ul'].notna()]
            if len(qhigh_data) > 0:
                fig_qhigh = px.box(qhigh_data, y='qhigh_conc_ng_ul', title="QHigh Distribution",
                                  points="all", color_discrete_sequence=['#1f77b4'])
                st.plotly_chart(fig_qhigh, use_container_width=True)
        
        with col2:
            qlow_data = qplates_df[qplates_df['qlow_conc_ng_ul'].notna()]
            if len(qlow_data) > 0:
                fig_qlow = px.box(qlow_data, y='qlow_conc_ng_ul', title="QLow Distribution",
                                 points="all", color_discrete_sequence=['#ff7f0e'])
                st.plotly_chart(fig_qlow, use_container_width=True)
        
        with col3:
            qsn_data = qplates_df[qplates_df['sn_qplate'].notna()]
            if len(qsn_data) > 0:
                fig_qsn = px.box(qsn_data, y='sn_qplate', title="Q-Plate S/N Distribution",
                                points="all", color_discrete_sequence=['#2ca02c'])
                st.plotly_chart(fig_qsn, use_container_width=True)
        
        st.subheader("Q-Plate QC Status")
        qc_counts = qplates_df['overall_plate_qc'].value_counts()
        fig_qc = px.pie(values=qc_counts.values, names=qc_counts.index, title="QC Status Distribution",
                       color_discrete_map={"PASS": "#27AE60", "WARNING": "#F39C12", "FAIL": "#E74C3C"})
        st.plotly_chart(fig_qc, use_container_width=True)
    
    with tab5:
        st.subheader("Statistical Summary")
        
        if len(stats_df) > 0:
            for metric in stats_df['metric_name'].unique():
                st.write(f"**{metric.upper()}**")
                metric_stats = stats_df[stats_df['metric_name'] == metric]
                
                for _, row in metric_stats.iterrows():
                    col1, col2, col3, col4, col5, col6 = st.columns(6)
                    
                    with col1:
                        st.metric(f"{row['instrument']} Mean", f"{row['mean_value']:.1f}")
                    with col2:
                        st.metric(f"Min", f"{row['min_value']:.1f}")
                    with col3:
                        st.metric(f"Max", f"{row['max_value']:.1f}")
                    with col4:
                        st.metric(f"StdDev", f"{row['std_value']:.1f}")
                    with col5:
                        st.metric(f"Median", f"{row['p50_value']:.1f}")
                    with col6:
                        st.metric(f"P95", f"{row['p95_value']:.1f}")
                
                st.divider()
        else:
            st.info("No statistics available yet. Run sync first.")

conn.close()
