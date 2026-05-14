
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

import sqlite3
import json 
import os
from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QPushButton,
                             QLabel, QVBoxLayout, QStackedWidget, QFileDialog,
                             QHBoxLayout, QTableWidget, QTableWidgetItem,
                             QCheckBox, QLineEdit, QGroupBox, QMessageBox,
                             QDialog, QFormLayout, QDialogButtonBox, QComboBox) 
from PyQt6.QtCore import Qt
# --- FIX: QDoubleValidator MUST be imported from QtGui ---
from PyQt6.QtGui import QFont, QDoubleValidator
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
# --- Placeholder/Mock for load_data.py (Used if external file is missing) ---
# This block attempts to import your real backend function. 
try:
    from load_data import load_data
except ImportError:
    print("Warning: 'load_data.py' module not found. Using mock functions.")
    
    # Mock data structure, including a CONSTANT value (Min=Max, Range=0) 
    MOCK_SUMMARY = {
        # Format: [Min, Max, Range]
        'Right Hip Abduction/Adduction': [10.0, 25.0, 15.0], # Normal movement
        'L3 z': [10.0, 10.0, 0.0],                          # Constant value (0 range)
        'Pelvis x': [15.0, 30.0, 15.0],
        'Left Knee Flexion/Extension': [45.0, 95.0, 50.0],
    }
    
    def load_data_mock(file_path):
        """
        Mocks the successful loading and analysis of data, returning df, peaks, and summary.
        """
        if file_path:
            # Create a mock df with Time column and several angle columns
            time = np.arange(0, 10, 0.1)
            data = pd.DataFrame({
                'Time (s)': time,
                'Right Hip Abduction/Adduction': 15 + 10 * np.sin(time),
                'L3 z': 10.0, # Constant column
                'Pelvis x': 20 + 10 * np.sin(time * 0.5),
                'Left Knee Flexion/Extension': 70 + 25 * np.cos(time),
            })
            peaks = {k: np.array([15, 75]) for k in MOCK_SUMMARY.keys()}
            avg_periods = {k: data[k].values for k in MOCK_SUMMARY.keys()}
            std_devs = {k: np.full_like(data[k].values, 0.5) for k in MOCK_SUMMARY.keys()}
            avg_time = {k: time for k in MOCK_SUMMARY.keys()}
            # Returns mock summary data
            return data, peaks, MOCK_SUMMARY, avg_periods, std_devs, avg_time
        return None, None, None, None, None, None  # Must return 6 Nones on failure
# --------------------------------------------------------------------------

class SubjectDatabase:
    """
    Manages subject data using a local SQLite file. The database file is located
    in the user's public Documents folder inside a dedicated application subdirectory.
    """
    def __init__(self, db_filename='subjects.db'):
        
        # 1. Define the cross-platform path to the database file:
        # e.g., /Users/user/Documents/BikeFittingData/subjects.db
        home_dir = Path.home()
        db_folder = home_dir / "Documents" / "BikeFittingData"
        db_path = db_folder / db_filename

        # 2. Ensure the application directory exists. 'exist_ok=True' ensures 
        # it does not fail if the folder already exists.
        try:
            db_folder.mkdir(parents=True, exist_ok=True)
            print(f"Database folder ensured at: {db_folder}")
        except OSError as e:
            print(f"Error creating database folder: {e}")
            # Fallback to current directory if Documents path fails
            db_path = Path(db_filename)
        
        # 3. Connect to the database. SQLite automatically creates the file 
        # if it doesn't exist at the specified path.
        self.conn = sqlite3.connect(str(db_path))
        self.cursor = self.conn.cursor()
        self.create_table()
        
    def create_table(self):
        """Creates the subjects table if it does not exist."""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                data TEXT
            )
        ''')
        self.conn.commit()

        # Ensure a default subject exists if the table is empty
        # All keys are initialized to avoid errors in the SubjectPage edit dialog.
        if not self.get_subject_names():
            default_data = {
                "name": "Default Subject",
                "altura_total": "", "altura_torso": "", "altura_entrepierna": "", 
                "anchura_hombros": "", "longitud_pies": "", "longitud_metatarsal": "",
                "altura_hombro_suelo": "", "altura_mano_suelo": ""
            }
            self.add_subject(default_data) 
        
    def add_subject(self, subject_data):
        """Adds or updates a subject profile."""
        name = subject_data['name']
        
        # Serialize all non-name data into a JSON string
        data_to_serialize = {k: v for k, v in subject_data.items() if k != 'name'}
        data_json = json.dumps(data_to_serialize)
        
        try:
            # Attempt INSERT
            self.cursor.execute('''
                INSERT INTO subjects (name, data) VALUES (?, ?)
            ''', (name, data_json))
            self.conn.commit()
            return True, f"Subject '{name}' added successfully."
        except sqlite3.IntegrityError:
            # If name exists (IntegrityError), UPDATE the data
            self.cursor.execute('''
                UPDATE subjects SET data = ? WHERE name = ?
            ''', (data_json, name))
            self.conn.commit()
            return True, f"Subject '{name}' updated successfully."
        except Exception as e:
            return False, f"Database error: {e}"

    def get_subject_names(self):
        """Returns a list of all subject names."""
        self.cursor.execute('SELECT name FROM subjects ORDER BY name')
        return [row[0] for row in self.cursor.fetchall()]

    def get_subject_data(self, name):
        """Retrieves the full profile data for a given subject name."""
        self.cursor.execute('SELECT data FROM subjects WHERE name = ?', (name,))
        row = self.cursor.fetchone()
        
        if row:
            # Deserialize the data and combine with the name
            data = json.loads(row[0])
            data['name'] = name
            return data
        return None

class MainApp(QMainWindow):
    """
    Main application window acting as the controller and data store.
    Uses QStackedWidget to manage different pages (MainPage, GraphPage, etc.).
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bike Fitting Data Analysis")
        self.resize(1300, 800) 
        
        # --- DATABASE & SUBJECT MANAGEMENT ---
        self.db = SubjectDatabase()
        
        # Initialize active subject from DB data (defaulting to the first one)
        initial_names = self.db.get_subject_names()
        self.active_subject_name = initial_names[0] if initial_names else 'Default Subject'

        # --- Data Storage ---
        self.file1_path = None
        self.file2_path = None
        self.bike_measures = {} # Stores bike measurement data
        

        # DataFrame, Peaks (indices), Analysis results (Summary stats), Cycle data
        self.data1 = {'df': None, 'right_peaks': None, 'left_peaks': None, 'summary': None, 'avg_periods': None, 'std_devs': None, 'avg_time': None}
        self.data2 = {'df': None, 'right_peaks': None, 'left_peaks': None, 'summary': None, 'avg_periods': None, 'std_devs': None, 'avg_time': None}
        
        # --- GUI Setup ---
        self.stacked_widget = QStackedWidget(self)
        self.setCentralWidget(self.stacked_widget)

        self.pages = {}
        
        self.main_page = MainPage(controller=self)
        self.graph_page = GraphPage(controller=self) # <-- New GraphPage instance
       
        
        self.stacked_widget.addWidget(self.main_page)
        self.stacked_widget.addWidget(self.graph_page) 
        
        self.pages['MainPage'] = self.main_page
        self.pages['GraphPage'] = self.graph_page
       
        
        self.show_page('MainPage') 
        
    # This method resides inside the main window class (where self.pages and self.stacked_widget exist)
      # This method resides inside the main window class (where self.pages and self.stacked_widget exist)
    def show_page(self, page_name):
        """
        Switches to the specified page (widget) and ensures the content is refreshed.
        
        This version assumes 'GraphPage' is the primary view for visualization 
        and uses the 'draw_plots' method to refresh content.
        """
        page = self.pages.get(page_name)
        
        if page:
            # 1. Main Navigation Command: Tell the stacked widget to display this page
            self.stacked_widget.setCurrentWidget(page)
            
            # 2. Conditional Refresh Logic: Force dynamic pages to update their content
            #    Now we only check for 'GraphPage' and call the single refresh method.
            if page_name == 'GraphPage':
                # This line will run if page_name is exactly 'GraphPage'
                page.set_data(self.data1, self.data2)
                page.draw_plots() 
                print(f"Page '{page_name}' opened and draw_plots() was executed.")
                
        else:
            print(f"Error: Could not find page with key '{page_name}'. Check the pages dictionary keys.")



    def load_data_and_update_gui(self, file_num, file_path):
        """
        Loads data using the backend function and updates the main page tables.
        Expects df, peaks, and summary from load_data.
        """
        # Call the external function which returns data (df), peaks, and summary
        try:
            df, right_peaks, left_peaks, summary, avg_periods, std_devs, avg_time = load_data(file_path)

             # 1. Guardar el DataFrame en un CSV
            df.to_csv('data_principal.csv', index=False)

            # Clase auxiliar para convertir datos de NumPy a formato que JSON entienda
            class NpEncoder(json.JSONEncoder):
                def default(self, obj):
                    if isinstance(obj, np.integer): return int(obj)
                    if isinstance(obj, np.floating): return float(obj)
                    if isinstance(obj, np.ndarray): return obj.tolist()
                    return super(NpEncoder, self).default(obj)

            # 2. Guardar los diccionarios en archivos JSON independientes
            archivos_diccionarios = {
                'right_peaks.json': right_peaks,
                'left_peaks.json': left_peaks,
                'summary.json': summary,
                'avg_periods.json': avg_periods,
                'std_devs.json': std_devs,
                'avg_time.json': avg_time
            }

            for nombre_archivo, contenido in archivos_diccionarios.items():
                with open(nombre_archivo, 'w', encoding='utf-8') as f:
                    json.dump(contenido, f, cls=NpEncoder, indent=4, ensure_ascii=False)

            print("¡Todos los archivos han sido guardados correctamente!")

        except ValueError as e:
            # Handle case where load_data failed to return 6 items
            QMessageBox.critical(self, "Error de Carga", 
                                 f"El archivo {file_num} no pudo cargarse o procesarse correctamente. Error: {e}")
            return
        except Exception as e:
            QMessageBox.critical(self, "Error de Carga", 
                                 f"Ocurrió un error inesperado al cargar el archivo {file_num}. Error: {e}")
            return
        # --- Critical Error Check ---
        if df is None or summary is None:
            QMessageBox.critical(self, "Error de Carga", 
                                 f"No se pudo cargar o analizar los datos del archivo {file_num}. Revise el formato del Excel.")
            return # Stop execution if data loading failed
        new_data_set = {
            'df': df, 
            'right_peaks': right_peaks,
            'left_peaks': left_peaks,
            'summary': summary,
            'avg_periods': avg_periods,  # <-- NEW: Storing plot data
            'std_devs': std_devs,        # <-- NEW: Storing plot data
            'avg_time': avg_time         # <-- NEW: Storing plot data
        }
        
        if file_num == 1:
            self.file1_path = file_path
            self.data1 = new_data_set # Store all components
            self.main_page.update_path_label(1, file_path)
        else:
            self.file2_path = file_path
            self.data2 = new_data_set # Store all components
            self.main_page.update_path_label(2, file_path)
            
        # Update the analysis table with the newly loaded data
        self.main_page.update_analysis_table()


class MainPage(QWidget):
    """
    The primary control panel containing file loaders, input tables, 
    analysis results, and navigation buttons.
    """
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        # Main layout is a horizontal box (Left Controls | Right Tables)
        main_layout = QHBoxLayout(self)
        
        # --- 1. Left Control Panel (Buttons, Subject, Nav) ---
        left_panel = QVBoxLayout()
        left_panel.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # 1a. File Loading Group
        file_group = QGroupBox("Archivos (.xlsx)")
        file_layout = QVBoxLayout()
        
        btn_load1 = QPushButton("Carga Archivo Uno (Pre) ")
        btn_load1.clicked.connect(lambda: self.open_file_dialog(1))
        self.path_label1 = QLabel("Path 1: No file loaded")
        
        btn_load2 = QPushButton("Carga archivo 2 (Post)")
        btn_load2.clicked.connect(lambda: self.open_file_dialog(2))
        self.path_label2 = QLabel("Path 2: No file loaded")
        
        file_layout.addWidget(btn_load1)
        file_layout.addWidget(self.path_label1)
        file_layout.addWidget(btn_load2)
        file_layout.addWidget(self.path_label2)
        file_group.setLayout(file_layout)
        left_panel.addWidget(file_group)

        # 1b. Subject Management Group
        subject_group = QGroupBox("Subject Management")
        subject_layout = QVBoxLayout()
        
        # Subject Name Display/Field
        self.subject_name_label = QLabel(f"Current Subject: {self.controller.active_subject_name}")
        subject_layout.addWidget(self.subject_name_label)
        
        # Subject Action Buttons
        subject_action_layout = QHBoxLayout()
        btn_new_subject = QPushButton("New Subject")
        btn_new_subject.clicked.connect(self.open_subject_page)
        
        # Edit Subject Button
        btn_edit_subject = QPushButton("Edit Subject")
        btn_edit_subject.clicked.connect(self.edit_subject_profile)
        
        # Dropdown Menu for subject selection
        self.subject_dropdown = QComboBox()
        self.subject_dropdown.setToolTip("Select a saved subject profile.")
        self.subject_dropdown.setMinimumWidth(150)
        self.populate_subject_dropdown()
        
        self.subject_dropdown.currentIndexChanged.connect(self.select_subject_from_dropdown)
        
        subject_action_layout.addWidget(btn_new_subject)
        subject_action_layout.addWidget(btn_edit_subject)
        subject_action_layout.addWidget(self.subject_dropdown)
        subject_layout.addLayout(subject_action_layout)
        
        subject_group.setLayout(subject_layout)
        left_panel.addWidget(subject_group)


        # 1c. Navigation and Export Buttons
        nav_group = QGroupBox("Actions")
        nav_layout = QVBoxLayout()

        btn_graphs = QPushButton("Open Graphs Window")
        btn_graphs.setObjectName("GraphButton") # Set object name for findChild to work
        btn_graphs.setEnabled(False) # Enable once data is loaded
        btn_graphs.clicked.connect(lambda: self.controller.show_page('GraphPage')) # Connect to placeholder
        
        btn_pdf = QPushButton("Create PDF Report")
        btn_pdf.setObjectName("PDFButton") # Set object name for findChild to work
        btn_pdf.setEnabled(False) # Enable once data is loaded/analyzed
        btn_pdf.clicked.connect(lambda: QMessageBox.information(self, "Feature", "PDF creation placeholder."))
        
        btn_save_measures = QPushButton("Capture Bike Measures")
        btn_save_measures.setObjectName("SaveButton") 
        btn_save_measures.clicked.connect(self.save_bike_measures)

        nav_layout.addWidget(btn_graphs)
        nav_layout.addWidget(btn_pdf)
        nav_layout.addWidget(btn_save_measures)
        nav_group.setLayout(nav_layout)
        left_panel.addWidget(nav_group)

        
        # --- 2. Right Tables Panel ---
        right_panel = QVBoxLayout()
        right_panel.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # 2a. Bike Measures Input Table (Editable)
        bike_group = QGroupBox("Bike Measurement Input")
        bike_layout = QVBoxLayout()
        
        
        self.bike_measures_table = QTableWidget(11, 4) 
        self.bike_measures_table.setHorizontalHeaderLabels(["Esquema", "Medida", "Pre", "Post"])
        
        # Pre-populate rows with common bike fitting measures
        measures = ["Eje pedalier a centro de sillín", "Eje pedalier a punta de sillín", 
                    "Punta de sillín a tornillo potencia", "Punta de sillín a abrazadera manillar", 
                    "Punta de silllín a final de maneta", "Inclinación de sillín",
                    "Inclinación de manetas", "Longitud de biela", "Longitud de potencia",
                    "Anchura manillar", "Espaciadores bajo manillar"]
        esquemas = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"]
                    
        for i, esquema in enumerate(esquemas):
            item = QTableWidgetItem(esquema)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable) # Make esquema name non-editable
            self.bike_measures_table.setItem(i, 0, item)
            
        for i, measure in enumerate(measures):
            item = QTableWidgetItem(measure)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable) # Make measure name non-editable
            self.bike_measures_table.setItem(i, 1, item)

            
        bike_layout.addWidget(self.bike_measures_table)
        bike_group.setLayout(bike_layout)
        right_panel.addWidget(bike_group)
        

        # 2b. Data Measures Analysis Table (Read-Only)
        data_group = QGroupBox("Análisis de Variables")
        data_layout = QVBoxLayout()
        
        # Compare Checkbox
        self.compare_checkbox = QCheckBox("Comparar Archivos (File 1 vs File 2)")
        self.compare_checkbox.setChecked(True)
        # Force table update when the checkbox state changes
        self.compare_checkbox.stateChanged.connect(self.update_analysis_table) 
        data_layout.addWidget(self.compare_checkbox)
        
        self.analysis_table = QTableWidget(0, 7) # Max columns needed for comparison
        self.analysis_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers) # Read-only
        self.analysis_table.setSortingEnabled(True)
        
        data_layout.addWidget(self.analysis_table)
        data_group.setLayout(data_layout)
        right_panel.addWidget(data_group)

        # --- Final Assembly ---
        main_layout.addLayout(left_panel, 1) # Left panel takes 1 part of the width
        main_layout.addLayout(right_panel, 3) # Right panel (tables) takes 3 parts of the width
        self.setLayout(main_layout)

    # --- Methods ---
    def edit_subject_profile(self):
        """
        Loads the active subject's data, opens SubjectPage for editing, 
        and updates the database if changes are accepted.
        """
        active_name = self.controller.active_subject_name
        
        # 1. Fetch current data
        current_data = self.controller.db.get_subject_data(active_name)
        
        if not current_data:
            QMessageBox.warning(self, "Error", f"No se pudieron cargar los datos para el sujeto '{active_name}'.")
            return
            
        # 2. Open dialog with current data for editing
        dialog = SubjectPage(self, initial_data=current_data)
        dialog.setWindowTitle(f"Editar Perfil: {active_name}")
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated_subject_data = dialog.get_subject_data()
            
            if updated_subject_data:
                # 3. Update the database (add_subject handles the overwrite logic)
                success, message = self.controller.db.add_subject(updated_subject_data)
                
                if success:
                    # Refresh the dropdown in case the name was also changed
                    self.populate_subject_dropdown()
                    QMessageBox.information(self, "Success", f"Perfil de '{active_name}' actualizado correctamente.")
                else:
                    QMessageBox.critical(self, "Database Error", message)
    
    def populate_subject_dropdown(self):
        """Fills the QComboBox with all stored subject names from the database."""
        # Temporarily block signals to prevent selection changes from firing during setup
        self.subject_dropdown.blockSignals(True) 
        self.subject_dropdown.clear()
        
        # Get names 
        subject_names = self.controller.db.get_subject_names()
        
        self.subject_dropdown.addItems(subject_names)
        
        # Set the active subject as the current index
        index = self.subject_dropdown.findText(self.controller.active_subject_name)
        if index >= 0:
            self.subject_dropdown.setCurrentIndex(index)
            
        self.subject_dropdown.blockSignals(False)
        
    def select_subject_from_dropdown(self, index):
        """
        Handles selection from the dropdown, updating the controller's active subject 
        and the status label.
        """
        if index < 0:
            return
            
        subject_name = self.subject_dropdown.currentText()
        
        # Only switch if the selected subject is different from the current active one
        if subject_name and subject_name != self.controller.active_subject_name:
            self.controller.active_subject_name = subject_name
            self.subject_name_label.setText(f"Current Subject: {subject_name}")
            
            # Since the data is stored in all_subjects, you can now access the full profile:
            # active_profile = self.controller.all_subjects[subject_name]
            
            QMessageBox.information(self, "Subject Switched", f"Active Subject set to: '{subject_name}'")    
    
    def open_file_dialog(self, file_num):
        """Opens a file dialog and initiates data loading."""
        # Use the QFileDialog for .xlsx files
        file_path, _ = QFileDialog.getOpenFileName(self, f"Select Excel File {file_num}", "", "Excel Files (*.xlsx)")
        if file_path:
            # Pass the path string to the controller
            self.controller.load_data_and_update_gui(file_num, file_path)

    def update_path_label(self, file_num, file_path):
        """Updates the labels under the file buttons and enables navigation buttons."""
        display_name = file_path.split('/')[-1]
        if file_num == 1:
            self.path_label1.setText(f"Path 1: {display_name}")
        else:
            self.path_label2.setText(f"Path 2: {display_name}")
            
        # Check if we can enable the navigation buttons
        if self.controller.data1['df'] is not None:
             # Use the explicit objectName to reliably find the buttons
             graph_btn = self.findChild(QPushButton, "GraphButton")
             pdf_btn = self.findChild(QPushButton, "PDFButton")
             
             if graph_btn:
                 graph_btn.setEnabled(True)
             if pdf_btn:
                 pdf_btn.setEnabled(True)
                 
    def open_subject_page(self):
        """Opens the SubjectPage modal dialog."""
        dialog = SubjectPage(self)
        
        # .exec() blocks the main app until the dialog is closed
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_subject_data = dialog.get_subject_data()
            if new_subject_data:
                subject_name = new_subject_data.get('name')
                # Check for duplication (optional, but good practice)
                existing_profile = self.controller.db.get_subject_data(subject_name)
                
                if existing_profile and subject_name != 'Default Subject':
                    reply = QMessageBox.question(self, 'Subject Exists', 
                        f"Subject '{subject_name}' already exists. Overwrite?", 
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                        QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.No:
                        return
                    
                success, message = self.controller.db.add_subject(new_subject_data)
                        
                if success:
                    # 1. Set the newly created/updated subject as the active one
                    self.controller.active_subject_name = subject_name
                    
                    # 2. Update the label on the main page 
                    self.subject_name_label.setText(f"Current Subject: {subject_name}")
                    
                    # 3. REFRESH THE DROPDOWN to include the new subject
                    self.populate_subject_dropdown()
                    
                    QMessageBox.information(self, "Success", message)
                else:
                    QMessageBox.critical(self, "Database Error", message)
                
    def save_bike_measures(self):
        """
        Extracts all data from the bike_measures_table and stores it in the
        controller's in-memory object (self.controller.bike_measures).
        """
        measures_data = {}
        measures = ["Eje pedalier a centro de sillín", "Eje pedalier a punta de sillín", 
                    "Punta de sillín a tornillo potencia", "Punta de sillín a abrazadera manillar", 
                    "Punta de silllín a final de maneta", "Inclinación de sillín",
                    "Inclinación de manetas", "Longitud de biela", "Longitud de potencia",
                    "Anchura manillar", "Espaciadores bajo manillar"]
        
        # Iterate over the rows of the bike measures table
        for i, measure_name in enumerate(measures):
            
            # Get the QTableWidgetItem for the Pre and Post columns (columns 2 and 3)
            item_pre = self.bike_measures_table.item(i, 2)
            item_post = self.bike_measures_table.item(i, 3)
            
            # Extract the text (or empty string if item is None or empty)
            value_pre = item_pre.text() if item_pre and item_pre.text() else ""
            value_post = item_post.text() if item_post and item_post.text() else ""
            
            # Store data using the measure name as the key
            measures_data[measure_name] = {
                "Pre": value_pre,
                "Post": value_post
            }
            
        print(measures_data)
        # Update the controller's data store
        self.controller.bike_measures = measures_data

    def update_analysis_table(self):
        """
        Populates the analysis table with Min, Max, and Range data for File 1 and File 2.
        Ensures the table is cleared and rows are set correctly before population.
        """
        # Define indices based on your new 3-element summary list: [min_val, max_val, range_val]
        MIN_IDX = 0
        MAX_IDX = 1
        RANGE_IDX = 2
        
        # Helper function to safely format value, handling both None and NumPy NaN
        def safe_format(val):
            # Check for None, and check for numpy NaN
            # NOTE: np.isnan() requires NumPy to be imported at the top of app.py
            if val is not None and not np.isnan(val):
                print(f"{float(val):.2f}")
                return f"{float(val):.2f}"
            return 'N/A'
            
        # --- 1. Get Data Safely ---
        summary1 = self.controller.data1.get('summary', {})
        summary2 = self.controller.data2.get('summary', {})
        
        if not summary1:
            # Clear table if File 1 data is missing
            self.analysis_table.setRowCount(0)
            return
            
        # We use summary1 keys to define rows, assuming all relevant variables are present.
        joint_angles = list(summary1.keys())
        num_rows = len(joint_angles)
        
        # --- CRITICAL FIX: Reset Table Structure ---
        self.analysis_table.setRowCount(0)  

        
        # --- 3. Populate Table Cells ---
        

        for angle in joint_angles:
            row = self.analysis_table.rowCount()
            self.analysis_table.insertRow(row)
            
            
            # --- Get Data Safely (3-element fallback) ---
            summary_list1 = summary1.get(angle, [None, None, None])
            
            # --- File 1 (Pre) Data (Columns 1, 2, 3) ---
            
            # Max (Pre) (Index 1)
            max_val1 = summary_list1[MAX_IDX] if len(summary_list1) > MAX_IDX else None
            self.analysis_table.setItem(row, 1, QTableWidgetItem(safe_format(max_val1)))
    
            # Min (Pre) (Index 0)
            min_val1 = summary_list1[MIN_IDX] if len(summary_list1) > MIN_IDX else None
            self.analysis_table.setItem(row, 2, QTableWidgetItem(safe_format(min_val1)))
            
            # Range (Pre) (Index 2)
            range_val1 = summary_list1[RANGE_IDX] if len(summary_list1) > RANGE_IDX else None
            self.analysis_table.setItem(row, 3, QTableWidgetItem(safe_format(range_val1)))
            
        
            
            # --- File 2 (Post) Data (Columns 4, 5, 6) ---
            # Only populate if File 2 summary exists
            if summary2 and self.compare_checkbox.isChecked(): 
                # summary_list2 uses the same structure [min_val, max_val, range_val]
                summary_list2 = summary2.get(angle, [None, None, None])
    
                # Max (Post)
                max_val2 = summary_list2[MAX_IDX] if len(summary_list2) > MAX_IDX else None
                self.analysis_table.setItem(row, 4, QTableWidgetItem(safe_format(max_val2)))
                
                # Min (Post)
                min_val2 = summary_list2[MIN_IDX] if len(summary_list2) > MIN_IDX else None
                self.analysis_table.setItem(row, 5, QTableWidgetItem(safe_format(min_val2)))
                
                # Range (Post)
                range_val2 = summary_list2[RANGE_IDX] if len(summary_list2) > RANGE_IDX else None
                self.analysis_table.setItem(row, 6, QTableWidgetItem(safe_format(range_val2)))
            else:
                  # Clear File 2 columns if no data is loaded
                  for col in range(4, 7):
                      self.analysis_table.setItem(row, col, QTableWidgetItem('N/A'))
                      
            # Column 0: Variable Name (Only written once per row)
            self.analysis_table.setItem(row, 0, QTableWidgetItem(angle))
            
        self.analysis_table.resizeColumnsToContents()
        self.analysis_table.resizeRowsToContents()
        self.analysis_table.horizontalHeader().setStretchLastSection(True)


        
class GraphPage(QWidget):
    """
    Page dedicated to comparing averaged movement cycles for specific joints
    in a 2x3 grid using Matplotlib.
    """
    

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.data1 = None
        self.data2 = None
        
        main_layout = QVBoxLayout(self)
        
        # Top Row: Controls and Navigation
        control_layout = QHBoxLayout()
        
        btn_back = QPushButton("← Back to Analysis")
        btn_back.clicked.connect(lambda: self.controller.show_page('MainPage'))
        
        btn_refresh = QPushButton("Refresh Cycle Plots")
        btn_refresh.clicked.connect(self.draw_plots)
        
        
        control_layout.addWidget(btn_back)
        control_layout.addWidget(QLabel("Gráficos de Ciclo Promedio (2x3)"))
        control_layout.addWidget(btn_refresh)
        control_layout.addStretch(1)
        main_layout.addLayout(control_layout)

        # Matplotlib Figure and Canvas for 2x3 grid
        # Use a large figure size for readability of 6 subplots
        self.figure = Figure(figsize=(12, 8)) 
        self.canvas = FigureCanvas(self.figure)
        main_layout.addWidget(self.canvas)
        
        # Define the 3 target plots for the first row (2x3 grid)
        # This includes the 6 variables specified for comparison
        self.target_plots = {
            # Subplot (row, col) : [Variable Name]
            (0, 0): 'Knee Flexion/Extension',
            (0, 1): 'Knee Abduction/Adduction',
            (0, 2): 'Ankle Dorsiflexion/Plantarflexion',
            (1, 0): 'L5 y',
            (1, 1): 'Pelvis z',
            (1, 2): 'Pelvis x',
        }
        
        # Axes storage and subplot creation
        self.axes = {}
        for (r, c), _ in self.target_plots.items():
            # Add subplot to 2 rows and 3 columns (r * 3 + c + 1 gives 1-6 indexing)
            self.axes[(r, c)] = self.figure.add_subplot(2, 3, r * 3 + c + 1)
        
        # Initial draw
        self.figure.tight_layout(pad=3.0)
        self.draw_plots()
        
    def set_data(self, data1, data2):
        """Receives fresh references from MainApp"""
        self.data1 = data1
        self.data2 = data2
        
    def draw_plots(self):
        """
        Draws the 6 comparison plots using averaged cycle data.
        Plots the mean and shades the standard deviation for Pre and Post.
        """
        # Ensure we have data structure, even if empty
        
        if self.data1 and self.data2: 
            data1 = self.data1
            data2 = self.data2
        
            for (r, c), variable_name in self.target_plots.items():
                ax = self.axes[(r, c)]
                ax.clear()
                normalized_time = np.linspace(0, 1, 100)
                # --- Get Data Pointers ---
                avg_time1 = data1.get('avg_time', {})
                avg_periods1 = data1.get('avg_periods', {})
                std_devs1 = data1.get('std_devs', {})
                
                avg_time2 = data2.get('avg_time', {})
                avg_periods2 = data2.get('avg_periods', {})
                std_devs2 = data2.get('std_devs', {})
                
                # Use 'x1' as the reference time axis for stabilization
                x1 = None 
                
                # --- Plot File 1 (Pre) ---
                if 'Knee' in variable_name or 'Ankle' in variable_name: #Plots for leg variables, with right/left
                    y1 = avg_periods1[f"Right {variable_name}"]
                    if y1 is None:
                        print(f"Advertencia: No se encontró la variable {variable_name}")
                        continue # Salta esta gráfica y sigue con la siguiente
                    y1 = avg_periods1.get(variable_name)
                    x1 = avg_time1.get(f"Right {variable_name}")
                    f1 = interp1d(x1, y1, kind='linear', fill_value='extrapolate')
                    y1_resampled = f1(normalized_time)
                    std1 = std_devs1[f"Right {variable_name}"]
                    f11 = interp1d(x1, std1, kind='linear', fill_value='extrapolate')
                    std1_resampled = f11(normalized_time)
                    
                    
                    y2 = avg_periods1[f"Left {variable_name}"]
                    x2 = avg_time1.get(f"Left {variable_name}")
                    f2 = interp1d(x2, y2, kind='linear', fill_value='extrapolate')
                    y2_resampled = f2(normalized_time)
                    std2 = std_devs1[f"Left {variable_name}"]
                    f22 = interp1d(x2, std2, kind='linear', fill_value='extrapolate')
                    std2_resampled = f22(normalized_time)
                    
                    ax.plot(normalized_time, y1_resampled, label='Right Pre', color='blue')
                    ax.plot(normalized_time, y2_resampled, label='Left Pre', color='green')
                    # Shade the standard deviation
                    ax.fill_between(normalized_time, y1_resampled - std1_resampled, y1_resampled + std1_resampled, color='blue', alpha=0.1)
                    ax.fill_between(normalized_time, y2_resampled - std2_resampled, y2_resampled + std2_resampled, color='green', alpha=0.1)
                        
                    # --- Plot File 2 (Post) ---
                    if self.controller.data2.get('df') is not None:
                        y3 = avg_periods2[f"Right {variable_name}"]
                        x3 = avg_time2.get(f"Right {variable_name}")
                        f3 = interp1d(x3, y3, kind='linear', fill_value='extrapolate')
                        y3_resampled = f3(normalized_time)
                        std3 = std_devs2[f"Right {variable_name}"]
                        f33 = interp1d(x3, std3, kind='linear', fill_value='extrapolate')
                        std3_resampled = f33(normalized_time)
                        
                        y4 = avg_periods2[f"Left {variable_name}"]
                        x4 = avg_time2.get(f"Left {variable_name}")
                        f4 = interp1d(x4, y4, kind='linear', fill_value='extrapolate')
                        y4_resampled = f4(normalized_time)
                        std4 = std_devs2[f"Left {variable_name}"]
                        f44 = interp1d(x4, std4, kind='linear', fill_value='extrapolate')
                        std4_resampled = f44(normalized_time)
        
                        # Ensure array lengths are approximately equal before comparison plot
                        ax.plot(normalized_time, y3_resampled, label='Right Post', color='pink')
                        ax.plot(normalized_time, y4_resampled, label='Left Post', color='red')
                        # Shade the standard deviation
                        ax.fill_between(normalized_time, y3_resampled - std3_resampled, y3_resampled + std3_resampled, color='pink', alpha=0.1)
                        ax.fill_between(normalized_time, y4_resampled - std4_resampled, y4_resampled + std4_resampled, color='red', alpha=0.1)
                        
        
        
                    # --- Formatting ---
                    title_parts = variable_name.split(' ')
                    # Example: 'Knee Flexion/Extension' -> 'Left Knee F/E'
                    simplified_title = f"{title_parts[0]} {title_parts[1]} F/E" if 'Flexion/Extension' in variable_name else f"{title_parts[0]} {title_parts[1]} A/A"
                    ax.set_title(simplified_title, fontsize=10)
                    ax.set_xlabel("Porcentaje de ciclo (%)", fontsize=8)
                    ax.set_ylabel("Ángulo (°)", fontsize=8)
                    ax.legend(loc='upper right', fontsize=8)
                    ax.grid(True, linestyle='--', alpha=0.6)
                    
                else: #plots for trunk variables
                    y1 = avg_periods1[f"{variable_name}"]
                    if y1 is None:
                        print(f"Advertencia: No se encontró la variable {variable_name}")
                        continue # Salta esta gráfica y sigue con la siguiente
                    x1 = avg_time1.get(f"{variable_name}")
                    f1 = interp1d(x1, y1, kind='linear', fill_value='extrapolate')
                    y1_resampled = f1(normalized_time)
                    std1 = std_devs1[f"{variable_name}"]
                    f11 = interp1d(x1, std1, kind='linear', fill_value='extrapolate')
                    std1_resampled = f11(normalized_time)
                    
                    ax.plot(normalized_time, y1_resampled, label='Pre', color='blue')
                    ax.fill_between(normalized_time, y1_resampled - std1_resampled, y1_resampled + std1_resampled, color='blue', alpha=0.1)
                    
                    if self.controller.data2.get('df') is not None:
                        y3 = avg_periods2[f"{variable_name}"]
                        x3 = avg_time2.get(f"{variable_name}")
                        f3 = interp1d(x3, y3, kind='linear', fill_value='extrapolate')
                        y3_resampled = f3(normalized_time)
                        std3 = std_devs2[f"{variable_name}"]
                        f33 = interp1d(x3, std3, kind='linear', fill_value='extrapolate')
                        std3_resampled = f33(normalized_time)
                        
                        ax.plot(normalized_time, y3_resampled, label='Post', color='pink')
                        ax.fill_between(normalized_time, y3_resampled - std3_resampled, y3_resampled + std3_resampled, color='pink', alpha=0.1)
                        
                    # --- Formatting ---
                    simplified_title = "Inclinación Lateral de tronco" if c == 0 else "Rotación Lateral Pelvis" if c==1 else "Pelvis Drop"
                    ax.set_title(simplified_title, fontsize=10)
                    ax.set_xlabel("Porcentaje de ciclo (%)", fontsize=8)
                    ax.set_ylabel("Ángulo (°)", fontsize=8)
                    ax.legend(loc='upper right', fontsize=8)
                    ax.grid(True, linestyle='--', alpha=0.6)
            # Final draw of the entire canvas
            self.figure.tight_layout(pad=3.0)
            self.canvas.draw()
            
class SubjectPage(QDialog):
    """
    A modal dialog window for creating new subject profiles with key anthropometric data.
    """
    def __init__(self, parent=None, initial_data=None):
        super().__init__(parent)
        self.setWindowTitle("Crear Nuevo Perfil de Sujeto")
        self.setFixedSize(400, 450) 
        self.subject_data = None # To store collected data

        main_layout = QVBoxLayout(self)
        
        # Form Layout for the fields
        form_layout = QFormLayout()
        
        # Define fields and their labels
        field_labels = {
            "name": "Nombre:",
            "altura_total": "Altura Total (cm):",
            "altura_torso": "Altura del Torso (cm):",
            "altura_entrepierna": "Altura de Entrepierna (cm):",
            "anchura_hombros": "Anchura de Hombros (cm):",
            "longitud_pies": "Longitud de Pies (cm):",
            "longitud_metatarsal": "Longitud Metatarsal (cm):",
            "altura_hombro_suelo": "Altura Hombro-Suelo (cm):",
            "altura_mano_suelo": "Altura Mano-Suelo (cm):",
        }
        
        # Store QLineEdit references dynamically
        self.fields = {}

        for key, label in field_labels.items():
            line_edit = QLineEdit()
            if key != "name":
                # Set validator to allow floating point numbers
                line_edit.setValidator(QDoubleValidator())
                line_edit.setPlaceholderText("0.0")
                
            # Populate field if initial data is provided (for editing)
            if initial_data and key in initial_data and initial_data[key] is not None:
                # Ensure data is converted to string for QLineEdit
                line_edit.setText(str(initial_data[key]))
            
            self.fields[key] = line_edit
            form_layout.addRow(label, line_edit)

        main_layout.addLayout(form_layout)
        
        # Dialog buttons (OK and Cancel)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept_data)
        button_box.rejected.connect(self.reject)
        
        main_layout.addWidget(button_box)

    def accept_data(self):
        """Collects the data from the fields and accepts the dialog."""
        name = self.fields["name"].text().strip()
        if not name:
            QMessageBox.warning(self, "Campo Faltante", "El Nombre del Sujeto es requerido.")
            return

        # Collect all data as text/string for now
        self.subject_data = {key: line_edit.text() for key, line_edit in self.fields.items()}
        
        self.accept() # Close the dialog successfully

    def get_subject_data(self):
        """Returns the collected subject data."""
        return self.subject_data
    

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())

