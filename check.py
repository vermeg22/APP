from PdfGenerator import generate_pdf
REPORT_TITLE = 'INFORME DE ANÁLISIS BIOMECÁNICO'
    
# Subject Data for Metadata Table and Header Info
test_subject_data = {
    'Subject Name': 'Maria Garcia',
    'Subject ID': 'MG-8803',
    'Date of Analysis': '2025-10-20',
    'Gender/Age': 'Femenino / 35',
    'Testing Protocol': 'Road Bike Standard'
}

# Analysis Data for Main Table (Keys MUST match joint_angles)
test_analysis_data = {
    'Right Knee Flexion/Extension': [15.2, -5.0, 20.2 ],
    'Left Knee Flexion/Extension': [16.1, -4.5, 20.6 ],
    'Pelvis x': [10.5, 0.5, 10.0],
}

# Lists for Label Mapping
joint_angles = [
    'Right Knee Flexion/Extension', 'Left Knee Flexion/Extension', 
    'Pelvis x', 'L5 z' # Using a subset for demo
]
joint_labels = [
    'FLEXIÓN/EXTENSIÓN RODILLA DERECHA', 'FLEXIÓN/EXTENSIÓN RODILLA IZQUIERDA',
    'DROP PELVIS', 'INCLINACIÓN ANTERIOR TRONCO'
]

# --- B. Execute Generation ---

try:
    generate_pdf(
        report_title=REPORT_TITLE,
        bike_measures={}, # Empty placeholder
        subject_data=test_subject_data,
        analysis_table_data=test_analysis_data,
        plots_path=PATHS['plot'],
        coment="", selected_elements="", # Empty placeholders
        joint_angles=joint_angles,
        joint_labels=joint_labels,
        logo_path=PATHS['logo'],
        background_image_path=PATHS['background'],
        cyclist_image1_path=PATHS['image1'],
        cyclist_image2_path=PATHS['image2'],
        output_filename=PATHS['output']
    )
except Exception as e:
    print(f"\n❌ A critical error occurred during PDF generation:")
    print(f"Ensure all placeholder images exist in the 'assets' folder.")
    print(f"Error details: {e}")