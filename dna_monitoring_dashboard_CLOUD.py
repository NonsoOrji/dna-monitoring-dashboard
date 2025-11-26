import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
import requests
import os
from io import BytesIO

st.set_page_config(page_title="DNA Concentration Monitoring", page_icon="🧬", layout="wide", initial_sidebar_state="expanded")

st.title("🧬 DNA Concentration Monitoring Dashboard")
st.markdown("Real-time monitoring of SpectraMax DNA concentration assays with Q-Plate trends & statistical analysis")

# ===== CLOUD VERSION - DOWNLOADS TOOL FILE FROM GITHUB =====
GITHUB_REPO = "NonsoOrji/dna-monitoring-dashboard"
GITHUB_RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/Tool-000011_DNA_Concentration_with_SpectraMax_Nonso_Version_Macro.xlsm"

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_data_from_github():
    """Download and load data from Tool file stored in GitHub"""
    try:
        st.info("📥 Loading data from GitHub...")
        
        # Download file from GitHub
        response = requests.get(GITHUB_RAW_URL, timeout=30)
        response.raise_for_status()
        
        # Read the Excel file from bytes
        excel_file = BytesIO(response.content)
        runs_df = pd.read_excel(excel_file, sheet_name='Run_Log_Archive')
        
        # Handle potential column name variations
        column_mapping = {
            'LHI Completion DateTime': 'lhi_completion_datetime',
            'LHI ID': 'lhi_id',
            'SpectraMax Instrument': 'instrument',
            'Std Read DateTime': 'std_read_datetime',
            'Std Δ Time (min)': 'std_delta_time_min',
            'Std-01 RFU (avg)': 'std_01_rfu',
            'Std-07 RFU (avg)': 'std_07_rfu',
            'Blank RFU (avg)': 'blank_rfu',
            'Std S/N (Std7/Blank)': 'sn_std7_blank',
        }
        
        # Rename columns if they exist
        for old_name, new_name in column_mapping.items():
            if old_name in runs_df.columns:
                runs_df.rename(columns={old_name: new_name}, inplace=True)
        
        # Ensure datetime column
        if 'lhi_completion_datetime' in runs_df.columns:
            runs_df['lhi_completion_datetime'] = pd.to_datetime(runs_df['lhi_completion_datetime'])
        
        st.success("✅ Data loaded successfully!")
        return runs_df
    
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error downloading file from GitHub: {str(e)}")
        st.info("Make sure the Tool file is uploaded to GitHub at: data/ directory")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error reading Tool file: {str(e)}")
        st.info("Ensure the file has 'Run_Log_Archive' sheet")
        return pd.DataFrame()

# Load data
runs_df = load_data_from_github()

if len(runs_df) == 0:
    st.warning("No data available. Check GitHub file and Run_Log_Archive sheet.")
else:
    with st.sidebar:
        st.header("📊 Filters & Options")
        date_from = st.date_input("From Date", value=datetime(2025, 11, 1))
        date_to = st.date_input("To Date", value=datetime.now())
        
        if 'instrument' in runs_df.columns:
            instruments = ["All Instruments"] + runs_df['instrument'].unique().tolist()
            selected_instrument = st.selectbox("Select Instrument", instruments)
        else:
            selected_instrument = "All Instruments"
        
        st.divider()
        st.info("☁️ Cloud version - data updated daily from GitHub")
        st.caption("Last data update: Check GitHub repository")
    
    # Filter by date
    if 'lhi_completion_datetime' in runs_df.columns:
        date_from_dt = pd.Timestamp(date_from)
        date_to_dt = pd.Timestamp(date_to)
        filtered_df = runs_df[
            (runs_df['lhi_completion_datetime'] >= date_from_dt) & 
            (runs_df['lhi_completion_datetime'] <= date_to_dt)
        ]
    else:
        filtered_df = runs_df
    
    # Filter by instrument
    if selected_instrument != "All Instruments":
        filtered_df = filtered_df[filtered_df['instrument'] == selected_instrument]
    
    if len(filtered_df) == 0:
        st.warning("No data available for selected filters")
    else:
        tab1, tab2, tab3, tab4 = st.tabs(["📋 By-Run Details", "📈 Trends & Analysis", "📊 Distribution Analysis", "🎯 Q-Plate Analysis"])
        
        with tab1:
            st.subheader(f"All Runs ({len(filtered_df)} total)")
            
            for idx, (_, run) in enumerate(filtered_df.iterrows()):
                with st.expander(f"🔬 {run.get('lhi_id', 'N/A')} | {run.get('lhi_completion_datetime', 'N/A')} | {str(run.get('instrument', 'N/A')).split(' - ')[-1]}", expanded=(idx==0)):
                    
                    col1, col2, col3, col4, col5 = st.columns(5)
                    
                    with col1:
                        std01 = run.get('std_01_rfu', 0)
                        status_std01 = "🟢" if 40000000 < std01 < 42000000 else "🟡" if 39000000 < std01 < 43000000 else "🔴"
                        st.metric("Std-01 RFU", f"{std01:.0f}", delta=status_std01)
                    
                    with col2:
                        std07 = run.get('std_07_rfu', 0)
                        status_std07 = "🟢" if 300000 < std07 < 400000 else "🟡" if 200000 < std07 < 450000 else "🔴"
                        st.metric("Std-07 RFU", f"{std07:.0f}", delta=status_std07)
                    
                    with col3:
                        blank = run.get('blank_rfu', 0)
                        st.metric("Blank RFU", f"{blank:.0f}")
                    
                    with col4:
                        sn = run.get('sn_std7_blank', 0)
                        status_sn = "🟢" if sn > 3.0 else "🟡" if sn > 2.5 else "🔴"
                        st.metric("S/N (Std-7/Blank)", f"{sn:.2f}", delta=status_sn)
                    
                    with col5:
                        read_time = run.get('std_delta_time_min', 0)
                        st.metric("Std Read Time", f"{read_time:.1f} min")
        
        with tab2:
            st.subheader("Standards Trends")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if 'std_01_rfu' in filtered_df.columns:
                    fig_std01 = px.line(filtered_df, x='lhi_completion_datetime', y='std_01_rfu', markers=True, 
                                       title="Standard-01 RFU Trend", color_discrete_sequence=['#1f77b4'])
                    fig_std01.add_hline(y=40000000, line_dash="dash", line_color="green", annotation_text="Target")
                    fig_std01.add_hrect(39000000, 41000000, fillcolor="green", opacity=0.1)
                    fig_std01.update_layout(hovermode='x unified', height=400, template="plotly_white")
                    st.plotly_chart(fig_std01, use_container_width=True)
            
            with col2:
                if 'std_07_rfu' in filtered_df.columns:
                    fig_std07 = px.line(filtered_df, x='lhi_completion_datetime', y='std_07_rfu', markers=True,
                                       title="Standard-07 RFU Trend", color_discrete_sequence=['#ff7f0e'])
                    fig_std07.add_hline(y=350000, line_dash="dash", line_color="green", annotation_text="Target")
                    fig_std07.update_layout(hovermode='x unified', height=400, template="plotly_white")
                    st.plotly_chart(fig_std07, use_container_width=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                if 'blank_rfu' in filtered_df.columns:
                    fig_blank = px.line(filtered_df, x='lhi_completion_datetime', y='blank_rfu', markers=True,
                                       title="Blank RFU Trend", color_discrete_sequence=['#2ca02c'])
                    fig_blank.update_layout(hovermode='x unified', height=400, template="plotly_white")
                    st.plotly_chart(fig_blank, use_container_width=True)
            
            with col2:
                if 'sn_std7_blank' in filtered_df.columns:
                    fig_sn = px.line(filtered_df, x='lhi_completion_datetime', y='sn_std7_blank', markers=True,
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
                if 'std_01_rfu' in filtered_df.columns:
                    fig_box_std01 = px.box(filtered_df, y='std_01_rfu', title="Std-01 Distribution",
                                          points="all", color_discrete_sequence=['#1f77b4'])
                    st.plotly_chart(fig_box_std01, use_container_width=True)
            
            with col2:
                if 'std_07_rfu' in filtered_df.columns:
                    fig_box_std07 = px.box(filtered_df, y='std_07_rfu', title="Std-07 Distribution",
                                          points="all", color_discrete_sequence=['#ff7f0e'])
                    st.plotly_chart(fig_box_std07, use_container_width=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                if 'sn_std7_blank' in filtered_df.columns:
                    fig_violin_sn = px.violin(filtered_df, y='sn_std7_blank', title="S/N Ratio Distribution",
                                             box=True, points="all", color_discrete_sequence=['#d62728'])
                    st.plotly_chart(fig_violin_sn, use_container_width=True)
            
            with col2:
                if 'instrument' in filtered_df.columns and 'sn_std7_blank' in filtered_df.columns:
                    inst_df = filtered_df[filtered_df['instrument'].notna()]
                    if len(inst_df) > 0:
                        fig_box_by_inst = px.box(inst_df, y='sn_std7_blank', 
                                                x='instrument', title="S/N by Instrument", color='instrument')
                        st.plotly_chart(fig_box_by_inst, use_container_width=True)
        
        with tab4:
            st.subheader("Quality Summary")
            st.info("Note: Q-Plate data from Run_Log_Archive sheet (if available)")
            
            if 'sn_std7_blank' in filtered_df.columns:
                sn_passing = len(filtered_df[filtered_df['sn_std7_blank'] > 2.0])
                sn_warning = len(filtered_df[(filtered_df['sn_std7_blank'] > 2.5) & (filtered_df['sn_std7_blank'] <= 3.0)])
                sn_excellent = len(filtered_df[filtered_df['sn_std7_blank'] > 3.0])
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("🟢 Excellent (>3.0)", sn_excellent)
                with col2:
                    st.metric("🟡 Warning (2.5-3.0)", sn_warning)
                with col3:
                    st.metric("🔴 Critical (<2.5)", sn_passing - sn_warning - sn_excellent)
