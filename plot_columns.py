def plot_columns(right_peaks, left_peaks, data, columns_to_analyce):
    import numpy as np
    from scipy.interpolate import interp1d
    tasks = []
    
    for column in columns_to_analyce:
        # 1. LATERAL VARIABLES (Right) - Use IF
        if column.startswith('Right '):
            tasks.append((column, right_peaks))
            
        # 2. LATERAL VARIABLES (Left) - Use ELIF
        elif column.startswith('Left '):
            tasks.append((column, left_peaks))
            
        # 3. NON-LATERAL VARIABLES (Trunk, Pelvis, etc.) - The final ELSE
        else:
            # Analyze using Right-side cycles, creating a unique key
            tasks.append((f"{column} (R-Cycle)", right_peaks))
            
            # Analyze using Left-side cycles, creating a unique key
            tasks.append((f"{column} (L-Cycle)", left_peaks))
    
    
    period_subsets_all_columns = {}
    
    # --- 2. EXTRACT CYCLE SUBSETS (Using the unique column_key for storage) ---
    for column_key, peaks in tasks:
        period_subsets = []
    
        if len(peaks) < 2:
            period_subsets_all_columns[column_key] = []
            continue
    
        # Extract the original column name from the key 
        # (e.g., 'L3 z' from 'L3 z (R-Cycle)')
        original_column = column_key.split(" (")[0]

        print("ORIGINAL COLUMN:", avg_periods.keys())
            
        for i in range(1, len(peaks)):
            start_index = peaks[i-1]
            end_index = peaks[i]
    
            time_subset = data['Time (s)'].iloc[start_index:end_index+1]
            angle_subset = data[original_column].iloc[start_index:end_index+1]
            
            period_subsets.append({'time': time_subset, 'angle': angle_subset})
        
        # Store using the UNIQUE key
        period_subsets_all_columns[column_key] = period_subsets
    
    
    # --- 3. INTERPOLATE AND AVERAGE CYCLES (CRITICAL FIX IS HERE) ---
    average_periods_all_columns = {}
    std_deviations_all_columns = {}
    average_time_all_columns = {}
    
    for column_key, period_subsets in period_subsets_all_columns.items():
        if not period_subsets:
            average_periods_all_columns[column_key] = None
            std_deviations_all_columns[column_key] = None
            average_time_all_columns[column_key] = None
            continue
    
        average_period_length = 100 
        resampled_angles = []
        
        # Interpolate each cycle to 100 points based on percentage of cycle
        for period in period_subsets:
            period_percent_cycle = np.linspace(0, 100, len(period['time']))
            interp_func = interp1d(period_percent_cycle, period['angle'])
            resampled_percent_cycle = np.linspace(0, 100, average_period_length)
            resampled_angle = interp_func(resampled_percent_cycle)
            resampled_angles.append(resampled_angle)
    
        resampled_angles = np.array(resampled_angles)
        average_angle = np.mean(resampled_angles, axis=0)
        std_deviation = np.std(resampled_angles, axis=0)
    
        # FIX: Ensure we use the local loop variable 'column_key' for storage, 
        # not the stale 'column' variable from the outer scope.
        average_periods_all_columns[column_key] = average_angle
        std_deviations_all_columns[column_key] = std_deviation
        average_time_all_columns[column_key] = resampled_percent_cycle
    
    return (average_periods_all_columns, std_deviations_all_columns, average_time_all_columns)