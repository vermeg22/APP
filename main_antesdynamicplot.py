import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

import sqlite3
import json 
import os
from pathlib import Path

from fpdf import FPDF
import copy
from io import BytesIO

import re

from PyQt6.QtCore import Qt, QTimer

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QPushButton,
                             QLabel, QVBoxLayout, QStackedWidget, QFileDialog,
                             QHBoxLayout, QTableWidget, QTableWidgetItem,
                             QCheckBox, QLineEdit, QGroupBox, QMessageBox,
                             QDialog, QFormLayout, QDialogButtonBox, QComboBox, QTextEdit, QHeaderView) 
from PyQt6.QtCore import Qt
# --- FIX: QDoubleValidator MUST be imported from QtGui ---
from PyQt6.QtGui import QFont, QDoubleValidator
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from PdfGenerator import generate_pdf

from extract_table_data import extract_table_data
 # (Import what you need)
from PyQt6.QtGui import QColor
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
            master_peaks = {k: np.array([15, 75]) for k in MOCK_SUMMARY.keys()}
            avg_periods = {k: data[k].values for k in MOCK_SUMMARY.keys()}
            std_devs = {k: np.full_like(data[k].values, 0.5) for k in MOCK_SUMMARY.keys()}
            avg_time = {k: time for k in MOCK_SUMMARY.keys()}
            # Returns mock summary data
            return data, master_peaks, MOCK_SUMMARY, avg_periods, std_devs, avg_time
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
        self.analysis_table = None
        self.bike_measures_table = QTableWidget()
        # DataFrame, Peaks (indices), Analysis results (Summary stats), Cycle data
        self.data1 = {'df': None, 'peaks': None, 'summary': None, 'avg_periods': None, 'std_devs': None, 'avg_time': None}
        self.data2 = {'df': None, 'peaks': None, 'summary': None, 'avg_periods': None, 'std_devs': None, 'avg_time': None}
        
        # --- GUI Setup ---
        self.stacked_widget = QStackedWidget(self)
        self.setCentralWidget(self.stacked_widget)

        self.pages = {}
        self.figure = None
        self.subject_data = None # To store collected data
        self.image_paths = {
            'bike_photo': None,
            'cyclist_photo1': None,
            'cyclist_photo2': None
        }
        self.extra_data = None
        self.compare_checkbox = True
        self.modality = None
        self.current_modality = None
        
        self.report_elements = {
            'bike_measures': {"text": "Medidas de Bicicleta (Bike Measures)", "type": "Data", "checkbox": None},
            'anthropometric_data': {"text": "Datos Antropométricos del Sujeto", "type": "Data", "checkbox": None},
            'analysis_table': {"text": "Tabla Resumen de Análisis (Max/Min)", "type": "Data", "checkbox": None},
            'plots': {"text": "Gráficos de las Sesiones", "type": "Plot", "checkbox": None},
            'cyclist foto':{'text' : 'Fotos del Ciclista', 'type': 'Foto', "checkbox": None},
            'bike foto':{'text' : 'Foto de la Bicicleta', 'type': 'Foto', "checkbox": None},
        }
        
        self.main_page = MainPage(controller=self)
        self.graph_page = GraphPage(controller=self)
        self.pdf_page = PDFPage(controller=self,main_page_instance=self.main_page)
        self.subject_page = SubjectPage(controller=self)
       
        
        self.stacked_widget.addWidget(self.main_page)
        self.stacked_widget.addWidget(self.graph_page) 
        self.stacked_widget.addWidget(self.pdf_page)
        
        self.pages['MainPage'] = self.main_page
        self.pages['GraphPage'] = self.graph_page
        self.pages['PDFPage'] = self.pdf_page
       
        
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
            'std_devs': std_devs,      # <-- NEW: Storing plot data
            'avg_time': avg_time       # <-- NEW: Storing plot data
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
        self.path_label1 = QLabel("Ruta 1: Sin Archivo")
        
        btn_load2 = QPushButton("Carga archivo 2 (Post)")
        btn_load2.clicked.connect(lambda: self.open_file_dialog(2))
        self.path_label2 = QLabel("Ruta 2: Sin Archivo")
        
        file_layout.addWidget(btn_load1)
        file_layout.addWidget(self.path_label1)
        file_layout.addWidget(btn_load2)
        file_layout.addWidget(self.path_label2)
        file_group.setLayout(file_layout)
        left_panel.addWidget(file_group)

        # 1b. Subject Management Group
        subject_group = QGroupBox("Gestión de Sujetos")
        subject_layout = QVBoxLayout()
        
        # Subject Name Display/Field
        self.subject_name_label = QLabel(f"Sujeto Actual: {self.controller.active_subject_name}")
        subject_layout.addWidget(self.subject_name_label)
        
        # Subject Action Buttons
        subject_action_layout = QHBoxLayout()
        btn_new_subject = QPushButton("Nuevo Sujeto")
        btn_new_subject.clicked.connect(self.open_subject_page)
        
        # Edit Subject Button
        btn_edit_subject = QPushButton("Editar Sujeto")
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
        nav_group = QGroupBox("Acciones")
        nav_layout = QVBoxLayout()

        btn_graphs = QPushButton("Abrir Ventana de Gráficos")
        btn_graphs.setObjectName("GraphButton") # Set object name for findChild to work
        btn_graphs.setEnabled(False) # Enable once data is loaded
        btn_graphs.clicked.connect(lambda: self.controller.show_page('GraphPage')) # Connect to placeholder
        
        btn_pdf = QPushButton("Crear Informe PDF")
        btn_pdf.setObjectName("PDFButton") # Set object name for findChild to work
        btn_pdf.setEnabled(False) # Enable once data is loaded/analyzed
        btn_pdf.clicked.connect(lambda: self.controller.show_page('PDFPage'))
        
        # btn_save_measures = QPushButton("Captura Medidas de Bicicleta")
        # btn_save_measures.setObjectName("SaveButton") 
        # btn_save_measures.clicked.connect(self.save_bike_measures)
        
        btn_add_data = QPushButton("Añadir Datos")
        btn_add_data.clicked.connect(self.show_extra_data_dialog)
        
        nav_layout.addWidget(btn_add_data)
        nav_layout.addWidget(btn_graphs)
        nav_layout.addWidget(btn_pdf)
        # nav_layout.addWidget(btn_save_measures)
        nav_group.setLayout(nav_layout)
        left_panel.addWidget(nav_group)

        
        # --- 2. Right Tables Panel ---
        right_panel = QVBoxLayout()
        right_panel.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        
        # 2a. Bike Measures Input Table (Editable)
        
        self.modality_combo = None 
        self._update_bike_measures('Ruta')
        self.setup_bike_measurement_input(right_panel)
               

        # 2b. Data Measures Analysis Table (Read-Only)
        data_group = QGroupBox("Análisis de Variables")
        data_layout = QVBoxLayout()
        
        # Compare Checkbox
        self.compare_checkbox = QCheckBox("Comparar Archivos (Pre vs Post)")
        self.compare_checkbox.setChecked(True)
        # Force table update when the checkbox state changes
        self.compare_checkbox.stateChanged.connect(self.update_analysis_table) 
        data_layout.addWidget(self.compare_checkbox)
        
        data_layout.addWidget(QLabel("·Rojo: Variación>30%   ·Amarillo: 30%>Variación>15%"))
        
        self.analysis_table = QTableWidget(0, 7) # Max columns needed for comparison
        self.analysis_table.setHorizontalHeaderLabels(["Variable", "Max Pre","Min Pre","Rango Pre",
                                                       "Max Post","Min Post","Rango Post",])
        self.analysis_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers) # Read-only
        self.analysis_table.setSortingEnabled(True)
        
        data_layout.addWidget(self.analysis_table)
        data_group.setLayout(data_layout)
        right_panel.addWidget(data_group)

        # --- Final Assembly ---
        main_layout.addLayout(left_panel, 1) # Left panel takes 1 part of the width
        main_layout.addLayout(right_panel, 3) # Right panel (tables) takes 3 parts of the width
        self.setLayout(main_layout)
        
        self.COLOR_RED = QColor(255, 204, 203) # Light Red
        self.COLOR_YELLOW = QColor(255, 242, 204) # Light Yellow

    # --- Methods ---
    def setup_bike_measurement_input(self, right_panel):
        bike_group = QGroupBox("Medidas Bicicleta")
        bike_layout = QVBoxLayout()
        
        # Label
        bike_layout.addWidget(QLabel("Modalidad:"))
        
        # ComboBox Setup
        self.modality_combo = QComboBox()
        self.modality_combo.addItem('Modalidad')
        self.modality_combo.addItems(['Ruta', 'MTB', 'TT'])
        self.modality_combo.setCurrentIndex(0)
        
        self.modality_combo.currentTextChanged.connect(self._update_bike_measures)
        
        # Register the widget in the controller
        self.controller.modality = self.modality_combo
        bike_layout.addWidget(self.modality_combo)
        
        # --- QTableWidget Setup ---
        self.controller.bike_measures_table = QTableWidget(0, 4)  # Initial rows can be anything
        self.controller.bike_measures_table.setHorizontalHeaderLabels(["Esquema", "Medida (mm)", "Pre", "Post"])
        
        # Set column 0 and 1 to stretch to fit content
        header = self.controller.bike_measures_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        # Register the table in the controller
        bike_layout.addWidget(self.controller.bike_measures_table)
        
        # Add the completed group box to the right panel
        bike_group.setLayout(bike_layout)
        right_panel.addWidget(bike_group)

    def get_comparison_color(self, val_pre, val_post):
        """
        Compares two values and returns a QColor if they meet the criteria,
        otherwise returns None.
        """
        # 1. Check for invalid data
        if val_pre is None or np.isnan(val_pre) or \
           val_post is None or np.isnan(val_post):
            return None

        # 2. Check for ZeroDivisionError
        if abs(val_pre) < 1e-6: # Check if val_pre is essentially zero
            if abs(val_post) < 1e-6:
                return None # 0 vs 0 is no change
            else:
                return self.COLOR_RED # Any change from 0 is "infinite" percent change

        # 3. Calculate percentage change
        difference = abs(val_post - val_pre)
        percent_change = difference / abs(val_pre)

        # 4. Apply coloring rules
        if percent_change > 0.30:
            return self.COLOR_RED
        elif percent_change >= 0.15: 
            return self.COLOR_YELLOW
        
        return None # No significant change
    
    ## Function to dynamically update the table content
    def _update_bike_measures(self,modality_name):
        """
        Updates the QTableWidget with the correct rows and measure names 
        based on the selected modality.
        """
        MEASURES_DATA = {
            'Ruta': {
                'rows': 11,
                'measures': [
                    "Eje pedalier a centro de sillín", "Eje pedalier a punta de sillín", 
                    "Punta de sillín a tornillo potencia", "Punta de sillín a abrazadera manillar", 
                    "Punta de silllín a final de maneta", "Inclinación de sillín",
                    "Inclinación de manetas", "Longitud de biela", "Longitud de potencia",
                    "Anchura manillar", "Espaciadores bajo manillar"
                ],
                'esquemas': ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"]
            },
            'MTB': {
                'rows':10, # Dummy number set by user request
                'measures': [
                    "Eje pedalier a centro de sillín", "Eje pedalier a punta de sillín", 
                    "Punta de sillín a tornillo potencia", "Punta de sillín a abrazadera manillar",
                    "Inclinación de sillín", "Longitud de biela", "Longitud de potencia",
                    "Inclinación de manetas", "Espaciadores bajo manillar"
                ],
                'esquemas':  ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
            },
            'TT': {
                'rows': 13, 
                'measures': [
                    "Eje pedalier a centro de sillín", "Eje pedalier a punta de sillín", "Punta de sillín a tornillo de potencia", 
                    "Punta de sillín a inicio de apoyacodo", "Punta de sillín a final de acople", 
                    "Longitud de biela", "Longitud de potencia ","Espaciadores bajo manillar", "Inclinación de apoyacodos ",
                    "Ancho de manillar","Ancho de barras","Ancho de apoyacodos", "Inclinación de sillín"
                ],
                'esquemas': ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M"]
            }
        }
        data = MEASURES_DATA.get(modality_name)
        if not data:
            print(f"Error: No data found for modality: {modality_name}")
            return
            
        rows = data['rows']
        measures = data['measures']
        esquemas = data['esquemas']
        
        # 1. Clear existing content and set new row count
        self.controller.bike_measures_table.setRowCount(0) # Temporarily set to 0 to clear
        self.controller.bike_measures_table.setRowCount(rows)
        
        # 2. Populate the table with new data
        for i, (esquema, measure) in enumerate(zip(esquemas, measures)):
            # Column 0: Esquema (e.g., A, M1, T1)
            esquema_item = QTableWidgetItem(esquemas[i])
            # Make schema name non-editable
            esquema_item.setFlags(esquema_item.flags() & ~Qt.ItemFlag.ItemIsEditable) 
            self.controller.bike_measures_table.setItem(i, 0, esquema_item)
            
            # Column 1: Medida (e.g., Eje pedalier a centro de sillín)
            measure_item = QTableWidgetItem(measures[i])
            # Make measure name non-editable
            measure_item.setFlags(measure_item.flags() & ~Qt.ItemFlag.ItemIsEditable) 
            self.controller.bike_measures_table.setItem(i, 1, measure_item)

            # Columns 2 (Pre) and 3 (Post) are left as editable input fields.
            self.controller.bike_measures_table.setItem(i, 2, QTableWidgetItem("")) # Pre
            self.controller.bike_measures_table.setItem(i, 3, QTableWidgetItem("")) # Post
            
        self.controller.bike_measures_table.resizeColumnsToContents()
        self.controller.bike_measures_table.resizeRowsToContents()
        print(f"Bike measures updated for modality: {modality_name} with {rows} rows.") 
        
    def show_extra_data_dialog(self):
        """Launches the dialog and updates the controller with the saved data."""
        
        dialog = ExtraDataDialog(self.controller, self,  initial_data=self.controller.extra_data)
        
        # 3. Handle the result
        if dialog.exec() == QDialog.accepted:
            # Save the collected data back to the controller
            # self.controller.extra_data = dialog.save_data()
            QMessageBox.information(self, "Datos Guardados", "Los datos adicionales han sido guardados y se incluirán en el PDF.")
    
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
        current_modality = self.modality_combo.currentText()
        
        if current_modality == 'Modalidad':
            QMessageBox.warning(self, "Guardar Error", "Por favor, selecciona una modalidad antes de guardar.")
            return
        
        table = self.controller.bike_measures_table
        row_count = table.rowCount()
        
        measures_data = {}
        
        # Iterate over the actual rows in the visible table
        for i in range(row_count):
            
            # Use item(i, 1) to get the measure name from the table's contents
            measure_item = table.item(i, 1)
            measure_name = measure_item.text() if measure_item and measure_item.text() else f"Unknown_Measure_{i}"

            # Extract Pre and Post values (Columns 2 and 3)
            item_pre = table.item(i, 2)
            item_post = table.item(i, 3)
            
            value_pre = item_pre.text() if item_pre else ""
            value_post = item_post.text() if item_post else ""
            
            # Store data using the measure name as the key
            measures_data[measure_name] = {
                "Pre": value_pre,
                "Post": value_post
            }
            
        # Update the controller's data store
        self.controller.bike_measures = measures_data
        self.controller.current_modality = current_modality # Store modality separately

        print("\n--- BIKE MEASURES SAVED ---")
        print(f"Modality: {self.controller.current_modality}")
        print("Measures (Requested Structure):")
        for name, data in self.controller.bike_measures.items():
            print(f"  {name}: Pre={data['Pre']}, Post={data['Post']}")
        print("---------------------------\n")

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
                color = self.get_comparison_color(max_val1, max_val2)
                item_max2 = QTableWidgetItem(safe_format(max_val2))
                if color:
                    item_max2.setBackground(color) # Set color
                self.analysis_table.setItem(row, 4,item_max2)
                
                # Min (Post)
                min_val2 = summary_list2[MIN_IDX] if len(summary_list2) > MIN_IDX else None
                color = self.get_comparison_color(min_val1, min_val2) # Get color
                item_min2 = QTableWidgetItem(safe_format(min_val2))  # Create item
                if color:
                    item_min2.setBackground(color) # Set color
                self.analysis_table.setItem(row, 5, item_min2)
                
                # Range (Post)
                range_val2 = summary_list2[RANGE_IDX] if len(summary_list2) > RANGE_IDX else None
                color = self.get_comparison_color(range_val1, range_val2) # Get color
                item_range2 = QTableWidgetItem(safe_format(range_val2)) # Create item
                if color:
                    item_range2.setBackground(color) # Set color
                self.analysis_table.setItem(row, 6, item_range2)
            else:
                  # Clear File 2 columns if no data is loaded
                  for col in range(4, 7):
                      self.analysis_table.setItem(row, col, QTableWidgetItem('N/A'))
                      
            # Column 0: Variable Name (Only written once per row)
            self.analysis_table.setItem(row, 0, QTableWidgetItem(angle))
            
        self.analysis_table.resizeColumnsToContents()
        self.analysis_table.resizeRowsToContents()
        self.analysis_table.horizontalHeader().setStretchLastSection(True)
        self.controller.analysis_table = self.analysis_table
        self.controller.compare_checkbox  = self.compare_checkbox.isChecked()
        
               
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
        
        # --- Plotting Setup ---
        self.controller.figure, self.axes = plt.subplots(2, 3, figsize=(10, 10))
        self.controller.figure.tight_layout(pad=3.0)
        self.canvas = FigureCanvas(self.controller.figure)
        
        # 1. Navigation Toolbar (Zoom, Pan, Reset)
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        # 2. Legend Toggle Button
        self.btn_toggle_legend = QPushButton("Alternar Leyenda")
        self.btn_toggle_legend.clicked.connect(self.toggle_legend)
        
        self.btn_go_back = QPushButton('Volver <--')
        self.btn_go_back.clicked.connect(lambda: self.controller.show_page('MainPage'))
        
        self.btn_custom_plot = QPushButton('Custom Plot')
        self.btn_custom_plot.clicked.connect(self.launch_custom_plot_dialog)


        # 3. Layout for Toolbar and Button
        control_layout = QHBoxLayout()
        control_layout.addWidget(self.toolbar)
        control_layout.addWidget(self.btn_toggle_legend)
        control_layout.addWidget(self.btn_go_back)
        control_layout.addWidget(self.btn_custom_plot)
        control_layout.addStretch(1) # Pushes the button to the left
        
        # 4. Main Layout (Update)
        main_layout = QVBoxLayout(self)
        main_layout.addLayout(control_layout) # Add controls first
        main_layout.addWidget(self.canvas)
        
        # 5. Tooltip/Annotation Setup
        self.annotations = {}
        
        # 6. Connect the hover event to the canvas
        self.canvas.mpl_connect('motion_notify_event', self.on_hover)
        self.target_plots = {
            # Subplot (row, col) : [Variable Name]
            (0, 0): 'Knee Flexion/Extension',
            (0, 1): 'Knee Abduction/Adduction',
            (0, 2): 'Ankle Dorsiflexion/Plantarflexion',
            (1, 0): 'L5 y',
            (1, 1): 'Pelvis z',
            (1, 2): 'Pelvis x',
        }
        
        self.draw_plots()

    def standardize_and_deduplicate_variables(self, raw_variable_list):      
        
        # We use a set to automatically store only unique values (deduplication)
        unique_core_variables = set()
    
        for variable in raw_variable_list:
            # Split the string by spaces
            words = variable.split()
            
            if len(words) > 1:
                # Join the words back together, starting from the second word (index 1)
                # This effectively removes the first word ("Left" or "Right")
                core_variable_name = " ".join(words[1:])
            else:
                # Handle cases where the variable name is only one word (shouldn't happen 
                # if they all have side prefixes, but good for robustness)
                core_variable_name = variable
    
            # Add the cleaned name to the set. Sets automatically prevent duplicates.
            unique_core_variables.add(core_variable_name)
    
        # Convert the set back to a list and sort it alphabetically for a clean display
        return sorted(list(unique_core_variables))
        
    def toggle_legend(self):
        """Toggles the visibility of the legend on all subplots."""
        for ax in self.axes.flat: # .flat iterates through all 6 subplots
            legend = ax.get_legend()
            if legend:
                # Toggle visibility state
                legend.set_visible(not legend.get_visible())

        self.canvas.draw()
        
    def launch_custom_plot_dialog(self):
        # 1. Get the list of variables available for plotting (e.g., from self.controller.data1)
        summary1 = self.controller.data1.get('summary', {})
        available_vars = list(summary1.keys())
        sorted_available_vars = self.standardize_and_deduplicate_variables(available_vars)
        # 2. Instantiate the Dialog, passing the variables and the parent window
        dialog = CustomPlotDialog(sorted_available_vars)
    
        # 3. Show the dialog modally and wait for the user action
        if dialog.exec() == QDialog.accepted:
            # User clicked 'Confirmar'
            custom_config = dialog.result
            
            plot_var = custom_config['plot_var']
            substitute_var = custom_config['substitute_var']
            
            # 4. CRITICAL: Trigger the update on the Graph Page
            self.update_graph_with_custom_variable(plot_var, substitute_var)
        else:
            # User clicked 'Cancelar' or closed the window
            print("Configuración de gráfico cancelada.")
        
    def on_hover(self, event):
        """
        Handles mouse hover events to display data coordinates for the closest point
        on ANY line within the active axes (subplot).
    
        It uses the self.annotations dictionary to manage a unique annotation artist
        for each axes object, preventing annotation conflicts.
        """
        if event.inaxes:
            ax = event.inaxes
            
            # Initialize trackers for the closest point found across all lines in this axes
            min_distance = float('inf')
            best_x = None
            best_y = None
            
            # 1. Iterate through ALL lines (data series) in the current subplot
            for line in ax.get_lines(): 
                xdata = line.get_xdata()
                ydata = line.get_ydata()
                
                # Find the index of the data point closest to the mouse x-coordinate
                # Use data coordinates to calculate the difference
                diff = abs(xdata - event.xdata)
                i = diff.argmin()
                
                # Calculate the actual Euclidean distance in screen/display coordinates
                # This is more accurate for proximity checks
                display_coords = ax.transData.transform((xdata[i], ydata[i]))
                event_coords = (event.x, event.y)
                
                # Distance formula: sqrt((x2-x1)^2 + (y2-y1)^2)
                distance = ((display_coords[0] - event_coords[0])**2 + 
                            (display_coords[1] - event_coords[1])**2)**0.5
    
                # 2. Update the 'best' point if the current point is closer
                if distance < min_distance:
                    min_distance = distance
                    best_x = xdata[i]
                    best_y = ydata[i]
            
            # 3. Manage the specific annotation for this axes (ax)
            
            # Get or create the annotation for the current axes
            if ax not in self.annotations:
                # Create a new annotation object for this specific axes
                self.annotations[ax] = ax.annotate(
                    '', # Start with empty text
                    xy=(0, 0), 
                    xytext=(10, 10), 
                    textcoords='offset points',
                    bbox=dict(boxstyle="round,pad=0.4", fc="lightblue", alpha=0.8),
                    arrowprops=dict(arrowstyle="->", connectionstyle="arc3", color="black"),
                    visible=False
                )
            
            annotation = self.annotations[ax]
    
            # 4. Check if the closest point is within a reasonable display proximity (e.g., 20 pixels)
            if best_x is not None and min_distance < 20: 
                
                # Update the position and text of the retrieved annotation
                annotation.xy = (best_x, best_y)
                annotation.set_text(f'({best_x:.2f}, {best_y:.2f})')
                annotation.set_visible(True)
            else:
                # If nothing is close enough, hide the annotation for this axes
                annotation.set_visible(False)
    
            # 5. Ensure only the annotation for the active axes is potentially visible
            # (The loop above already set the visibility for 'ax')
            for other_ax, other_annotation in self.annotations.items():
                if other_ax != ax:
                    other_annotation.set_visible(False)
    
            # 6. Redraw the canvas
            self.canvas.draw_idle()
        
        else:
            # If the mouse is not over any axes, hide all annotations across the figure
            for annotation in self.annotations.values():
                annotation.set_visible(False)
            self.canvas.draw_idle()    
        
    def set_data(self, data1, data2):
        """Receives fresh references from MainApp"""
        self.data1 = data1
        self.data2 = data2
    
    def update_graph_with_custom_variable(self, new_variable, variable_to_replace):
        """Replaces one active plot variable with the user's custom selection."""
        
        # Example: If your page stores the active plots in a list:
        if variable_to_replace in self.target_plots:
            index = self.target_plots.index(variable_to_replace)
            self.target_plots[index] = new_variable
            
            # Call your existing function that handles the drawing
            self.draw_plots() 
        else:
            print(f"Error: {variable_to_replace} no encontrado en los gráficos activos.")
        
    def draw_plots(self):
        """
        Draws the 6 comparison plots using averaged cycle data.
        Plots the mean and shades the standard deviation for Pre and Post.
        """
        # Ensure we have data structure, even if empty
        # Reset annotation dictionary 
          
        if self.data1 and self.data2: 
            data1 = self.data1
            data2 = self.data2
         
            for (r, c), variable_name in self.target_plots.items():
                ax = self.axes[(r, c)]
                ax.clear()
                normalized_time = np.linspace(0, 100, 100)
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
                    
                    ax.plot(normalized_time, y1_resampled, label='Right Pre', color='powderblue')
                    ax.plot(normalized_time, y2_resampled, label='Left Pre', color='grey')
                    # Shade the standard deviation
                    ax.fill_between(normalized_time, y1_resampled - std1_resampled, y1_resampled + std1_resampled, color='powderblue', alpha=0.1)
                    ax.fill_between(normalized_time, y2_resampled - std2_resampled, y2_resampled + std2_resampled, color='grey', alpha=0.1)
                        
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
                        ax.plot(normalized_time, y3_resampled, label='Right Post', color='blue')
                        ax.plot(normalized_time, y4_resampled, label='Left Post', color='black')
                        # Shade the standard deviation
                        ax.fill_between(normalized_time, y3_resampled - std3_resampled, y3_resampled + std3_resampled, color='blue', alpha=0.1)
                        ax.fill_between(normalized_time, y4_resampled - std4_resampled, y4_resampled + std4_resampled, color='black', alpha=0.1)
                        
        
        
                    # --- Formatting ---
                    title_parts = variable_name.split(' ')
                    # Example: 'Knee Flexion/Extension' -> 'Left Knee F/E'
                    simplified_title = f"{title_parts[0]} {title_parts[1]} F/E" if 'Flexion/Extension' in variable_name else f"{title_parts[0]} {title_parts[1]} A/A"
                    ax.set_title(simplified_title, fontsize=10)
                    ax.set_xlabel("Porcentaje de ciclo (%)", fontsize=8)
                    ax.set_ylabel("Ángulo (°)", fontsize=8)
                    ax.legend(loc='upper right', fontsize=8, frameon=True)
                    ax.grid(True, linestyle='--', alpha=0.6)
                    
                else: #plots for trunk variables
                    y1_r = avg_periods1[f"{variable_name} (R-Cycle)"]
                    y1_l = avg_periods1[f"{variable_name} (L-Cycle)"]
                    std1_r = std_devs1[f"{variable_name} (R-Cycle)"]
                    std1_l = std_devs1[f"{variable_name} (L-Cycle)"]
                    
                    y1_consolidated = (y1_r + y1_l) / 2
                    std1_consolidated = (std1_r + std1_l) / 2
                    
                    x1 = avg_time1.get(f"{variable_name} (R-Cycle)")
                    f1 = interp1d(x1, y1_consolidated, kind='linear', fill_value='extrapolate')
                    y1_resampled = f1(normalized_time)
                    f11 = interp1d(x1, std1_consolidated, kind='linear', fill_value='extrapolate')
                    std1_resampled = f11(normalized_time)
                    
                    ax.plot(normalized_time, y1_resampled, label='Pre', color='blue')
                    ax.fill_between(normalized_time, y1_resampled - std1_resampled, y1_resampled + std1_resampled, color='blue', alpha=0.1)
                    
                    if self.controller.data2.get('df') is not None:
                        y2_r = avg_periods2[f"{variable_name} (R-Cycle)"]
                        y2_l = avg_periods2[f"{variable_name} (L-Cycle)"]
                        std2_r = std_devs2[f"{variable_name} (R-Cycle)"]
                        std2_l = std_devs2[f"{variable_name} (L-Cycle)"]
                        
                        y2_consolidated = (y2_r + y2_l) / 2
                        std2_consolidated = (std2_r + std2_l) / 2
                        
                        x3 = avg_time2.get(f"{variable_name} (R-Cycle)")
                        f3 = interp1d(x3, y2_consolidated, kind='linear', fill_value='extrapolate')
                        y3_resampled = f3(normalized_time)
                        f33 = interp1d(x3, std2_consolidated, kind='linear', fill_value='extrapolate')
                        std3_resampled = f33(normalized_time)
                        
                        ax.plot(normalized_time, y3_resampled, label='Post', color='black')
                        ax.fill_between(normalized_time, y3_resampled - std3_resampled, y3_resampled + std3_resampled, color='black', alpha=0.1)
                        
                    # --- Formatting ---
                    simplified_title = "Inclinación Lateral de tronco" if c == 0 else "Rotación Lateral Pelvis" if c==1 else "Pelvis Drop"
                    ax.set_title(simplified_title, fontsize=10)
                    ax.set_xlabel("Porcentaje de ciclo (%)", fontsize=8)
                    ax.set_ylabel("Ángulo (°)", fontsize=8)
                    ax.legend(loc='upper right', fontsize=8, frameon=True)
                    ax.grid(True, linestyle='--', alpha=0.6)
            # Final draw of the entire canvas 
            self.controller.figure.tight_layout()
            self.controller.figure.canvas.draw()
            
class SubjectPage(QDialog):
    """
    A modal dialog window for creating new subject profiles with key anthropometric data.
    """
    def __init__(self, controller, parent=None, initial_data=None):
        super().__init__(parent)
        self.setWindowTitle("Crear Nuevo Perfil de Sujeto")
        self.setFixedSize(400, 450) 
        self.controller = controller
        

        main_layout = QVBoxLayout(self)
        
        # Form Layout for the fields
        form_layout = QFormLayout()
        
        # Define fields and their labels
        field_labels = {
            "name": "Nombre:",
            "altura_total": "Altura Total (mm):",
            "altura_torso": "Altura del Torso (mm):",
            "altura_entrepierna": "Altura de Entrepierna (mm):",
            "anchura_hombros": "Anchura de Hombros (mm):",
            "longitud_pies": "Longitud de Pies (mm):",
            "longitud_metatarsal": "Longitud Metatarsal (mm):",
            "altura_hombro_suelo": "Altura Hombro-Suelo (mm):",
            "altura_mano_suelo": "Altura Mano-Suelo (mm):",
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
        self.controller.subject_data = {key: line_edit.text() for key, line_edit in self.fields.items()}
        
        self.accept() # Close the dialog successfully

    def get_subject_data(self):
        """Returns the collected subject data."""
        return self.controller.subject_data

class PDFPage(QWidget):
    """Page for configuring and generating the PDF report."""
    def __init__(self, controller,main_page_instance):
        super().__init__()
        self.controller = controller
        # Updated list of elements based on user request
        
        
        # --- Autosave Timer Setup (Debounce) ---
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True) # Ensures it only fires once per start
        self.autosave_timer.timeout.connect(self.perform_autosave)
        self.summary_text_edit = (" ")
        self.contact_name_text = (" ")
        self.contact_tlf_text = (" ")
        self.contact_mail_text = (" ")
        
        self.status_label = QLabel (" ")
        self.summary_paragraph = None
        self.contact_name = None
        self.contact_tlf = None
        self.contact_mail = None
        self.main_page = main_page_instance
        self.init_ui()
   
    def handle_image_upload(self, key_name: str, button: QPushButton):
        """
        Opens a file dialog for image selection, stores the path in the controller, 
        and updates the button text to confirm selection.
        """
        
        # Open the File Dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            f"Seleccionar {button.text()}", 
            "", 
            "Image Files (*.png *.jpg *.jpeg)" 
        )
    
        if file_path:
            # 1. Initialize image_paths in controller if it doesn't exist
            if not hasattr(self.controller, 'image_paths'):
                self.controller.image_paths = {
                    'bike_photo': None,
                    'cyclist_photo1': None,
                    'cyclist_photo2': None
                }
            
            # 2. Store the absolute path in the controller
            self.controller.image_paths[key_name] = file_path
            
            # 3. Update the Button Text to Confirm Selection
            button.setText(f"✅ {os.path.basename(file_path)}")
        else:
            # User cancelled, restore original text or do nothing
            if self.controller.image_paths.get(key_name) is None:
                # If nothing was selected before, restore original text
                if key_name == 'bike_photo':
                    button.setText('Foto Bicicleta')
                elif key_name == 'cyclist_photo1':
                    button.setText('Foto Ciclista 1')
                elif key_name == 'cyclist_photo2':
                    button.setText('Foto Ciclista 2')
                
    def get_analysis_data_table(self):
        """
        Extracts, formats, and structures the Min, Max, and Range data for File 1
        and File 2 into a list-of-lists format suitable for PDF table rendering.
        
        This function replaces the QTableWidget population logic.
        
        Returns:
            dict: A dictionary containing 'headers' (list of lists for multi-row headers) 
                  and 'data' (list of lists for table body rows).
        """
        # Define indices based on your new 3-element summary list: [min_val, max_val, range_val]
        MIN_IDX = 0
        MAX_IDX = 1
        RANGE_IDX = 2
        
        # Helper function to safely format value, handling both None and NumPy NaN
        def safe_format(val):
            # Check for None, and check for numpy NaN
            if val is not None and not np.isnan(val):
                # Printing to console removed to clean up the data preparation logic
                return f"{float(val):.2f}"
            return 'N/A'
            
        # --- 1. Get Data Safely ---
        # Assuming self.controller.data1 and self.controller.data2 exist and are accessible
        self.summary1 = self.controller.data1.get('summary', {})
        self.summary2 = self.controller.data2.get('summary', {})
        
        
          
        # Check if comparison is enabled (assuming self.compare_checkbox is accessible)
        compare_is_checked = self.compare_checkbox.isChecked() if hasattr(self, 'compare_checkbox') else False
    
        if not self.summary1:
            # If File 1 data is missing, return empty data structure
            return {'headers': [], 'data': []}
            
        # We use summary1 keys to define rows.
        # joint_angles = list(self.summary1.keys()) WE WILL CHOOSE WHICH VARIABLES TO PRINT
        joint_angles = ['Right Knee Flexion/Extension','Left Knee Flexion/Extension','Right Knee Abduction/Adduction',
                        'Left Knee Abduction/Adduction', 'Right Ankle Dorsiflexion/Plantarflexion','Left Ankle Dorsiflexion/Plantarflexion',
                        'L5 z','L5 y','Pelvis z','Pelvis x']
        joint_labels = ['FLEXIÓN/EXTENSIÓN RODILLA DERECHA', 'FLEXIÓN/EXTENSIÓN RODILLA IZQUIERDA', 'VARO(+)/VALGO(-) RODILLA DERECHA',
                        'VARO(+)/VALGO(-) RODILLA IZQUIERDA', 'FLEXIÓN DORSAL(+)/PLANTAR TOBILLO DERECHO', 'FLEXIÓN DORSAL(+)/PLANTAR TOBILLO IZQUIERDO',
                        'INCLINACIÓN ANTERIOR TRONCO', 'INCLINACIÓN LATERAL TRONCO', 'ROTACIÓN PELVIS', 'DROP PELVIS']
        
        
        # --- 2. Define Table Headers (Structured for Multi-Row PDF Table) ---
        
        # Row 1: Group headers (File 1, File 2)
        group_headers = ["Joint Angle", "File 1 (Pre)", "File 1 (Pre)", "File 1 (Pre)"]
        
        # Row 2: Metric headers (Max, Min, Range)
        metric_headers = ["", "Max", "Min", "Range"] # "" for the Joint Angle column
        
        if compare_is_checked:
            group_headers.extend(["File 2 (Post)", "File 2 (Post)", "File 2 (Post)"])
            metric_headers.extend(["Max", "Min", "Range"])
    
        table_headers = [group_headers, metric_headers]
        
        # --- 3. Prepare Table Body Data ---
        table_rows = []
        
        for angle, label in zip(joint_angles, joint_labels):
            current_row = []
            
            # Column 0: Variable Name
            current_row.append(label)
    
            # --- Get Data Safely (3-element fallback) ---
            summary_list1 = self.summary1.get(angle, [None, None, None])
            
            # --- File 1 (Pre) Data (Max, Min, Range) ---
            
            # Max (Pre)
            max_val1 = summary_list1[MAX_IDX] if len(summary_list1) > MAX_IDX else None
            current_row.append(safe_format(max_val1))
            
            # Min (Pre)
            min_val1 = summary_list1[MIN_IDX] if len(summary_list1) > MIN_IDX else None
            current_row.append(safe_format(min_val1))
            
            # Range (Pre)
            range_val1 = summary_list1[RANGE_IDX] if len(summary_list1) > RANGE_IDX else None
            current_row.append(safe_format(range_val1))
            
            
            # --- File 2 (Post) Data (Max, Min, Range) ---
            if self.summary2:
                # summary_list2 uses the same structure [min_val, max_val, range_val]
                summary_list2 = self.summary2.get(angle, [None, None, None])
    
                # Max (Post)
                max_val2 = summary_list2[MAX_IDX] if len(summary_list2) > MAX_IDX else None
                current_row.append(safe_format(max_val2))
                
                # Min (Post)
                min_val2 = summary_list2[MIN_IDX] if len(summary_list2) > MIN_IDX else None
                current_row.append(safe_format(min_val2))
                
                # Range (Post)
                range_val2 = summary_list2[RANGE_IDX] if len(summary_list2) > RANGE_IDX else None
                current_row.append(safe_format(range_val2))
            elif compare_is_checked:
                # Append N/A placeholders for File 2 columns if comparison is active but data is missing
                for _ in range(3):
                    current_row.append('N/A')
            
            table_rows.append(current_row)
                
        return {'headers': table_headers, 'data': table_rows}
    

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # 1. Header and Navigation
        header_layout = QHBoxLayout()
        btn_back = QPushButton("Volver a Análisis")
        btn_back.clicked.connect(lambda: self.controller.show_page('MainPage'))
        header_layout.addWidget(btn_back)
        header_layout.addStretch(1)
        main_layout.addLayout(header_layout)

        # 2. Configuration Group
        config_group = QGroupBox("Selección de Contenido para el Reporte PDF")
        config_layout = QHBoxLayout()
        
        # Left Column: General Data and Tables
        data_group = QGroupBox("Datos y Tablas")
        data_layout = QVBoxLayout()
        data_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Middle Column: Fotos
        foto_group = QGroupBox('Fotos')
        foto_layout = QVBoxLayout()
        foto_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Right Column: Visualizaciones
        plot_group = QGroupBox("Visualizaciones")
        plot_layout = QVBoxLayout()
        plot_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        

        # Populate the Checkboxes
        for key, element in self.controller.report_elements.items():
            checkbox = QCheckBox(element["text"])
            checkbox.setChecked(True) # Default to checked
            self.controller.report_elements[key]["checkbox"] = checkbox
            
            if element["type"] == "Data":
                data_layout.addWidget(checkbox)
            elif element["type"] == "Plot":
                plot_layout.addWidget(checkbox)
            elif element['type'] == 'Foto':
                foto_layout.addWidget(checkbox)
                
        
        data_layout.addStretch(1) # Push content to the top
        plot_layout.addStretch(1) # Push content to the top
        foto_layout.addStretch(1) # Push content to the top
        
        data_group.setLayout(data_layout)
        plot_group.setLayout(plot_layout)
        foto_group.setLayout(foto_layout)

        config_layout.addWidget(data_group)
        config_layout.addWidget(plot_group)
        config_layout.addWidget(foto_group)
        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)
        
        image_group = QGroupBox("2. Fotos del Análisis")
        image_layout = QHBoxLayout()
        image_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        # 1. Bike Photo Button
        self.btn_bike_photo = QPushButton('Foto Bicicleta')
        self.btn_bike_photo.clicked.connect(
            lambda: self.handle_image_upload('bike_photo', self.btn_bike_photo)
        )
        
        # 2. Cyclist Photo 1 Button
        self.btn_cyclist_photo1 = QPushButton('Foto Ciclista Pre')
        self.btn_cyclist_photo1.clicked.connect(
            lambda: self.handle_image_upload('cyclist_photo1', self.btn_cyclist_photo1)
        )
    
        # 3. Cyclist Photo 2 Button
        self.btn_cyclist_photo2 = QPushButton('Foto Ciclista Post')
        self.btn_cyclist_photo2.clicked.connect(
            lambda: self.handle_image_upload('cyclist_photo2', self.btn_cyclist_photo2)
        )
        
        image_layout.addWidget(self.btn_bike_photo)
        image_layout.addWidget(self.btn_cyclist_photo1)
        image_layout.addWidget(self.btn_cyclist_photo2)
        image_layout.addStretch(1) # Keeps buttons left-aligned
        
        image_group.setLayout(image_layout)
        main_layout.addWidget(image_group)
        
        contact_group = QGroupBox('3. Datos de contacto')
        contact_layout = QVBoxLayout()
        contact_group.setLayout(contact_layout)
        
        contact_layout.addWidget(QLabel('Nombre y Apellidos: '))
        self.contact_name_text = QTextEdit()
        self.contact_name_text.textChanged.connect(self.start_autosave_timer)
        contact_layout.addWidget(self.contact_name_text)
        
        contact_layout.addWidget(QLabel('Número de teléfono: '))
        self.contact_tlf_text = QTextEdit()
        self.contact_tlf_text.textChanged.connect(self.start_autosave_timer)
        contact_layout.addWidget(self.contact_tlf_text)
        
        contact_layout.addWidget(QLabel('Correo electrónico'))
        self.contact_mail_text = QTextEdit()
        self.contact_mail_text.textChanged.connect(self.start_autosave_timer)
        contact_layout.addWidget(self.contact_mail_text)
        
        main_layout.addWidget(contact_group)
        
        notes_group = QGroupBox("4. Notas de Resumen y Recomendaciones")
        notes_layout = QVBoxLayout()
        notes_group.setLayout(notes_layout)
        
        notes_layout.addWidget(QLabel("Escriba el párrafo de resumen final para incluir en el PDF:"))
        
        self.summary_text_edit = QTextEdit()
        self.summary_text_edit.setPlaceholderText(
            "E.g., El ciclista mostró una excelente adaptación a los nuevos ajustes. La principal recomendación es monitorear la fatiga del glúteo medio en salidas largas..."
        )
        self.summary_text_edit.setMinimumHeight(120)
        
        self.summary_text_edit.textChanged.connect(self.start_autosave_timer)
        
        notes_layout.addWidget(self.summary_text_edit)
        
        
        main_layout.addWidget(notes_group)

        # 3. Action Button
        btn_generate = QPushButton("Generar PDF")
        btn_generate.clicked.connect(self.main_page.save_bike_measures)
        btn_generate.clicked.connect(self.generate_pdf_and_save)
        # btn_generate.clicked.connect(self.generate_pdf)                                        
        main_layout.addWidget(btn_generate)

        main_layout.addStretch(1)
        
    def generate_pdf_and_save(self):
        """Handles the button click: generates the PDF data and prompts user to save it."""
        joint_angles = ['Right Knee Flexion/Extension','Left Knee Flexion/Extension','Right Knee Abduction/Adduction',
                        'Left Knee Abduction/Adduction', 'Right Ankle Dorsiflexion/Plantarflexion','Left Ankle Dorsiflexion/Plantarflexion',
                        'L5 z','L5 y','Pelvis z','Pelvis x']
        joint_labels = ['FLEXOEXTENSIÓN RODILLA DERECHA', 'FLEXOEXTENSIÓN RODILLA IZQUIERDA', 'VARO(+)/VALGO(-) RODILLA DERECHA',
                        'VARO(+)/VALGO(-) RODILLA IZQUIERDA', 'DORSAL(+)/PLANTAR(-) TOBILLO D.', 'DORSAL(+)/PLANTAR(-) TOBILLO I.',
                        'INCLINACIÓN ANTERIOR TRONCO', 'INCLINACIÓN LATERAL TRONCO', 'ROTACIÓN PELVIS', 'DROP PELVIS']
        # --- 1. PREPARE DATA AND GENERATE PDF IN MEMORY ---
        bike_measures_data = extract_table_data(self.controller.bike_measures_table)
        subject_name = self.controller.active_subject_name
        print(subject_name)
        subject_data = self.controller.db.get_subject_data(subject_name)
        report_title = 'INFORME BIOMECANICO CICLISMO'
        try:     
            pdf_data = generate_pdf(bike_measures_data , subject_data,
                                    self.controller.analysis_table, joint_angles, joint_labels,
                                    self.controller.figure,self.summary_paragraph, 
                                    self.controller.image_paths, self.controller.extra_data, report_title, self.controller.compare_checkbox,
                                    self.controller.current_modality, self.contact_name, self.contact_tlf, self.contact_mail,
                                    self.controller.report_elements)
        except Exception as e:
            QMessageBox.critical(self, "Error de Generación", 
                                 f"Ocurrió un error al generar el PDF:\n{e}")
            print(f"PDF Generation Error: {e}")
            return # Stop execution if generation fails
    
        # --- 2. ASK USER WHERE TO SAVE THE FILE ---
        default_filename = f"Reporte_Biomecanico_{subject_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        # QFileDialog.getSaveFileName returns a tuple (path, filter)
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Guardar Reporte PDF", 
            default_filename, 
            "PDF Files (*.pdf)"
        )
    
        # --- 3. SAVE THE FILE ---
        if file_path:
            try:
                # Write the raw PDF bytes returned by generate_pdf to the chosen file path
                with open(file_path, 'wb') as f:
                    f.write(pdf_data)
                
                # Show success message
                QMessageBox.information(
                    self, 
                    "PDF Generado", 
                    f"Reporte guardado exitosamente en:\n{file_path}"
                )
            except Exception as e:
                # Show error message
                QMessageBox.critical(
                    self, 
                    "Error al Guardar", 
                    f"Ocurrió un error al guardar el archivo:\n{e}"
                )
        
    def start_autosave_timer(self):
        """
        Called on every text change. 
        It resets and starts the timer, implementing the debounce logic.
        """
        self.status_label.setText("✏️ Escribiendo... Autosave en curso.")
        # Stop and restart the timer: waits 1000ms (1 second) for inactivity
        self.autosave_timer.start(1000)
        
    def perform_autosave(self):
       
        self.summary_paragraph = self.summary_text_edit.toPlainText().strip()
        self.contact_name = self.contact_name_text.toPlainText().strip()
        self.contact_tlf = self.contact_tlf_text.toPlainText().strip()
        self.contact_mail = self.contact_mail_text.toPlainText().strip()

class CustomPlotDialog(QDialog):
    def __init__(self, available_vars):
        super().__init__()
        self.setWindowTitle("Configurar Gráfico Personalizado")
        self.result = {}
        self.variable_list = available_vars
        print(self.variable_list)
        self.init_ui()
    def init_ui(self,):
        """Sets up the minimalist layout with two dropdown menus."""
        main_layout = QVBoxLayout()

        # 1. Input Form (QFormLayout for clean label/input pairing)
        form_layout = QFormLayout()
        # --- Variable to Plot (The new data series) ---
        self.plot_combo = QComboBox()
        self.plot_combo.addItems(self.variable_list)
        # Set the default choice to the first item
        if self.variable_list:
            self.plot_combo.setCurrentText(self.variable_list[0])

        form_layout.addRow(QLabel("Variable a Plotear (Nueva):"), self.plot_combo)

        # --- Variable to Substitute (The data series to replace) ---
        self.substitute_combo = QComboBox()
        self.substitute_combo.addItems(['Knee Flexion/Extension','Knee Abduction/Adduction', 'Ankle Dorsiflexion/Plantarflexion',
                                       'L5 y','Pelvis z', 'Pelvis x'])
        # Note: If you want to only show the currently visible plots here, 
        # you should pass a separate list (e.g., 'active_plots') to the constructor.
        
        form_layout.addRow(QLabel("Variable a Sustituir (Existente):"), self.substitute_combo) 
        
        main_layout.addLayout(form_layout)
        
        # 2. Action Buttons (Standard QDialogButtonBox)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        
        # Rename the standard buttons to Spanish
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Confirmar")
        self.button_box.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        
        # Connect signals to the dialog's standard slots
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        
        
        main_layout.addWidget(self.button_box)
        self.setLayout(main_layout)
        # Set a fixed size for a clean pop-up appearance
        self.setFixedSize(350, 180)
        

    def accept(self):
        """
        Overrides the standard QDialog accept method. 
        It captures the selected values before closing the dialog.
        """
        # Save the selected values into the result dictionary
        self.result = {
            'plot_var': self.plot_combo.currentText(),
            'substitute_var': self.substitute_combo.currentText()
        }
        super().accept()
        
class ExtraDataDialog(QDialog):
    def __init__(self, controller, parent=None, initial_data=None):
        super().__init__(parent)
        self.setWindowTitle("Añadir Datos Adicionales")
        self.setGeometry(100, 100, 500, 600)
        self.data = initial_data if initial_data else self.create_default_data()
        self.fields = {} # To store references to QLineEdit objects
        self.controller = controller
        main_layout = QVBoxLayout(self)
        
        # --- Group 1: Informacion bicicleta ---
        self.create_group_box(
            main_layout, "Informacion Bicicleta",
            fields=["Fabricante", "Modelo cuadro", "Talla", "Sillin", "Pedal"],
            key_prefix="bike_"
        )

        # --- Group 2: Datos Entrenamiento ---
        self.create_group_box(
            main_layout, "Datos Entrenamiento",
            fields=["Modalidad", "Años de practica", "Horas semanales", "Km anuales"],
            key_prefix="training_"
        )

        # --- Group 3: Registro de Lesiones (Single Large Field) ---
        lesiones_group = QGroupBox("Registro de Lesiones")
        lesiones_layout = QVBoxLayout()
        
        self.lesiones_text_edit = QTextEdit()
        self.lesiones_text_edit.setPlaceholderText("Escriba aquí cualquier lesión relevante, historial médico, o detalles del análisis.")
        self.fields['lesiones'] = self.lesiones_text_edit # Store reference
        

        lesiones_layout.addWidget(self.lesiones_text_edit)
        lesiones_group.setLayout(lesiones_layout)
        main_layout.addWidget(lesiones_group)
        
        # --- Action Buttons ---
        button_layout = QHBoxLayout()
        btn_save = QPushButton("Guardar y Cerrar")
        btn_cancel = QPushButton("Cancelar")
        
        btn_save.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        
        button_layout.addStretch(1)
        button_layout.addWidget(btn_save)
        button_layout.addWidget(btn_cancel)
        
        main_layout.addLayout(button_layout)
        
        # Load remaining initial data
        # self.load_data()
    def accept(self):
        self.controller.extra_data = self.save_data()
        print(self.controller.extra_data)
        super().accept()
        

    def create_default_data(self):
        """Creates the full structure of the stored data."""
        data = {
            'bike_Fabricante': '', 'bike_Modelo_cuadro': '', 'bike_Talla': '', 'bike_Sillin': '', 'bike_Pedal': '',
            'training_Modalidad': '', 'training_Años_de_practica': '', 'training_Horas_semanales': '', 'training_Km_anuales': '',
            'lesiones': ''
        }
        return data

    def create_group_box(self, main_layout, title, fields, key_prefix):
        """Helper to create the smaller QGroupBoxes with line edits."""
        group = QGroupBox(title)
        layout = QVBoxLayout()
        
        for field_name in fields:
            key = f"{key_prefix}{field_name.replace(' ', '_')}"
            
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{field_name}:"))
            line_edit = QLineEdit()
            
            self.fields[key] = line_edit # Store reference
            
            layout.addLayout(row)
            layout.addWidget(line_edit)
            
        group.setLayout(layout)
        main_layout.addWidget(group)

    def load_data(self):
        """Populates the line edits with existing data."""
        for key, widget in self.fields.items():
            if key in self.data:
                # Handle QTextEdit vs QLineEdit
                if isinstance(widget, QLineEdit):
                    widget.setText(self.data[key])
                elif isinstance(widget, QTextEdit):
                    widget.setText(self.data[key])

    def save_data(self):
        """Gathers data from the fields into the self.data dictionary."""
        for key, widget in self.fields.items():
            if isinstance(widget, QLineEdit):
                self.data[key] = widget.text()
            elif isinstance(widget, QTextEdit):
                self.data[key] = widget.toPlainText()
        
        return self.data

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())

