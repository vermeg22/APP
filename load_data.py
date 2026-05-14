import pandas as pd
import numpy as np
from scipy.signal import find_peaks
from analyce_columns import analyce_columns
from plot_columns import plot_columns
from pandas.api.types import is_numeric_dtype

def load_data(file):
    """
    Loads joint angle and segment orientation data from an Excel file,
    merges them, finds peaks, and calculates summary statistics (Min, Max, Range)
    for all data columns.
    
    Args:
        file (str): The path to the Excel file.
        
    Returns:
        tuple: (data_df, all_peaks_dict, summary_dict)
    """
    try:
        df_joint_angles = pd.read_excel(file, sheet_name="Joint Angles ZXY")
        df_joint_orientations = pd.read_excel(file, sheet_name="Segment Orientation - Euler")
        df_extra_info = pd.read_excel(file, sheet_name='General Information')
    except FileNotFoundError:
        print(f"Error: File not found at {file}")
        return None, None, None
    except Exception as e:
        print(f"Error reading Excel sheets: {e}")
        return None, None, None
    
    
    frame_rate_raw = df_extra_info.iloc[3 , 1]
    frame_rate = float(str(frame_rate_raw).strip())

    # Select joint angle data
    # Select all joint angle columns plus 'Frame'
    angle_cols = ['Frame'] + list(df_joint_angles.loc[:, 'Right Hip Abduction/Adduction':'Left Ball Foot Flexion/Extension'].columns)
    angle_data = df_joint_angles.loc[:, angle_cols].copy() 
    
    # Select orientation data (Frame to L3 z)
    orientation_data = df_joint_orientations.loc[:, 'Frame':'L3 z'].copy() 

    # Merge the two dataframes on the 'Frame' column
    data = pd.merge(angle_data, orientation_data, on='Frame')
    # Add Time (s) column
    data['Time (s)'] = data['Frame'] / frame_rate

    # --- 1. Peak Finding ---
    summary = {}
    cols_to_skip = ['Frame', 'Time (s)'] 
    
    # 1. Prepare list of columns for analysis/summary generation
    columns_to_analyze = [
        col for col in data.columns 
        if col not in cols_to_skip and is_numeric_dtype(data[col]) and not data[col].isnull().all()
    ]

    print(f"Columns to analyze: {data[columns_to_analyze].columns.tolist()}")
    print(f"Columns data: {data.columns.tolist()}")
    
    # --- 2. Peak Finding (Using your new function) ---
    # We assume 'analyce_columns' is defined in this file or imported.
    # It must return the all_peaks dictionary required by plot_columns.
    try:
        right_peaks, left_peaks = analyce_columns(data)

    except NameError:
        print("Error: 'analyce_columns' function not found. Peaks will not be calculated.")
        right_peaks = {}
        left_peaks = {}
    
    # --- 3. Summary Calculation (Iterate over all analyzable columns) ---
    for column in columns_to_analyze:
        
        # Summary Calculation Logic
        min_val = data[column].min()
        max_val = data[column].max()
        range_val = max_val - min_val
        
        # Store as [Series, Min, Max, Range]
        summary[column] = [min_val, max_val, range_val]
        
    # --- 4. Cycle Analysis (Using your new function) ---
    # We assume 'plot_columns' is defined in this file or imported.
    try:
        # Pass the calculated peaks (all_peaks) and the DataFrame (data)
        avg_periods, std_devs, avg_time = plot_columns(right_peaks, left_peaks, data, columns_to_analyze)
    except NameError:
        print("Error: 'plot_columns' function not found. Averaged cycle data is empty.")
        avg_periods, std_devs, avg_time = {}, {}, {} 
    except Exception as e:
        print(f"Error during cycle analysis: {e}")
        avg_periods, std_devs, avg_time = {}, {}, {} 

    print(f"LOAD_DATA: Final summary dictionary contains {len(summary)} keys.")
    print(f"LOAD_DATA: Summary keys (first 5): {list(summary.keys())[:5]}")
    
    print("Keys found in avg_periods1:", avg_periods.keys())
 # The load_data function now returns 6 items
    return data, right_peaks, left_peaks, summary, avg_periods, std_devs, avg_time