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

      # Imprimir los índices de los picos
      print(f"Índices de picos Izquierda: {left_peaks}")
      print(f"Índices de picos Derecha: {right_peaks}")

      # Obtener los valores reales en esos picos
      valores_izq = left_angle_data[left_peaks]
      valores_der = right_angle_data[right_peaks]
      print(f"Ángulos máximos Izquierda (°): {valores_izq}")
      print(f"Ángulos máximos Derecha (°): {valores_der}")

      return right_peaks, left_peaks