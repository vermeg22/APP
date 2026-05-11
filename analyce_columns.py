def analyce_columns(data):
      import numpy as np
      import matplotlib.pyplot as plt
      from scipy.signal import find_peaks
    
      time = data["Time (s)"].to_numpy()
    
      # all_peaks = {}
    
      # for column in columns_to_analyze:
      #        angle_data = data[column].to_numpy()
             
      #        # --- IMPROVED PEAK LOGIC ---
      #        if 'Pelvis' in column or 'T8' in column or 'L5' in column or 'L3' in column:
      #            # Very low prominence for torso/pelvis orientation (subtle movements)
      #            peaks, _ = find_peaks(angle_data, prominence=0.1) 
      #        elif 'Ball Foot' in column or 'Internal/External Rotation' in column:
      #            # Lower prominence for subtle foot and rotational movements
      #            peaks, _ = find_peaks(angle_data, prominence=1)
      #        else:
      #            # Standard prominence for major sagittal joints (Hip, Knee, Ankle F/E)
      #            peaks, _ = find_peaks(angle_data, prominence=4) 
                 
      #        all_peaks[column] = peaks

      # return all_peaks
      
      left_angle_data = data['Left Knee Flexion/Extension'].to_numpy()
      left_peaks, _ = find_peaks(left_angle_data, prominence = 4)
      right_angle_data = data['Right Knee Flexion/Extension'].to_numpy()
      right_peaks, _ = find_peaks(right_angle_data, prominence = 4)
      return right_peaks, left_peaks