from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, Image, PageBreak, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, lightgrey, black
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import Frame
from reportlab.pdfgen import canvas   
from reportlab.platypus import SimpleDocTemplate
import pathlib
import io 
from reportlab.lib.utils import ImageReader
import os
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os 
from reportlab.pdfgen import canvas 
from reportlab.platypus import KeepTogether

def register_custom_font(font_name):
    
    # Define the base directory where your assets are stored
    # This assumes your assets directory is located relative to the script's location
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    ASSETS_DIR = os.path.join(BASE_DIR, 'assets') 
    
    # 1. Define the TTF file path
    regular_font_file = os.path.join(ASSETS_DIR, f'{font_name}-Regular.ttf')
    
    # 2. Register the individual TTF file with a simple font name
    # We use the full name for the TTFont object itself
    pdfmetrics.registerFont(TTFont(font_name, regular_font_file))
    
    # 3. Register the family name.
    # IMPORTANT: We map all variants (normal, bold, italic) back to the single registered TTFont name.
    # ReportLab will attempt to derive bold/italic effects internally.
    pdfmetrics.registerFontFamily(
        font_name, 
        normal=font_name, 
        bold=font_name, 
        italic=font_name, 
        boldItalic=font_name
    )
    
    # You may also want to register common fallback names:
    pdfmetrics.registerFont(TTFont('BBH-Regular', regular_font_file))
    pdfmetrics.registerFontFamily('BBH-Regular', normal='BBH-Regular', bold='BBH-Regular')

    print(f"Custom font '{font_name}' registered from: {regular_font_file}")

def setup_styles():
    styles = getSampleStyleSheet()
    styles.ACCENT_COLOR = HexColor('#77829e')
    styles.TEXT_COLOR = HexColor('#0d0c0c')
    styles.ALTERNATIVE_COLOR = HexColor('#414175')
    register_custom_font("BBHSansBartle")
    register_custom_font("Sansation")
    
    styles.add(ParagraphStyle(
        name= 'ReportTitle', fontName='BBHSansBartle', fontSize=26, 
        textColor=styles.TEXT_COLOR, spaceAfter=30, alignment=1, leading=60
        ))
    styles.add(ParagraphStyle(
        name='SectionHeading', fontName='Sansation', fontSize=18,
        textColor=styles.ACCENT_COLOR, spaceBefore=20, spaceAfter=10,
        leftIndent=5 # Aesthetic left margin for the border
    ))
    if 'BodyText' in styles:
        styles['BodyText'].fontName = 'Sansation'
        styles['BodyText'].fontSize = 12
        styles['BodyText'].textColor = styles.TEXT_COLOR
        styles['BodyText'].leading = 14
        styles['BodyText'].spaceAfter = 6
    
    return styles

BASE_DIR = pathlib.Path(__file__).parent.resolve()
ASSETS_DIR = BASE_DIR / 'assets'
LOGO_PATH = str(ASSETS_DIR / 'logo.png')
BACKGROUND_IMAGE_PATH =str(ASSETS_DIR / 'background.jpg')
BACKGROUND1_IMAGE_PATH =str(ASSETS_DIR / 'background1.png')
RUTA_BIKE_MEASURES_IMAGE = str(ASSETS_DIR / 'medida_bici.png')
TT_BIKE_MEASURES_IMAGE = str(ASSETS_DIR / 'medida_bici_TT.png')
MTB_BIKE_MEASURES_IMAGE = str(ASSETS_DIR / 'medida_bici_MTB.png')

def title_page_template(canvas, doc, report_title, styles, LOGO_PATH, BACKGROUND_IMAGE_PATH):
    canvas.saveState()
    
    page_width = letter[0]
    page_height = letter[1]
    
    # --- 1. Draw Full-Page Background Image (Base Layer) ---
    try:
        canvas.drawImage(BACKGROUND1_IMAGE_PATH, 
                         0, 0, 
                         width=page_width, 
                         height=page_height, 
                         preserveAspectRatio=True)
    except Exception as e:
        print(f"Error loading background image: {e}")
        canvas.setFillColor(lightgrey)
        canvas.rect(0, 0, page_width, page_height, fill=1)
    
    # --- 4. Centered, Wrapping Report Title ---
    
    TITLE_MARGIN = 1.5 * inch
    TITLE_WIDTH = page_width - (2 * TITLE_MARGIN)
    
    title_style = styles['ReportTitle']
    
    # FIX: Set text color to white against the dark overlay
    temp_style = title_style.clone('TempTitleStyle')
    temp_style.textColor = HexColor('#FFFFFF')
    temp_style.alignment = 1 # Center alignment (TA_CENTER)
    title_paragraph = Paragraph(report_title, temp_style)

    # Calculate the height the paragraph will occupy
    title_width_actual, title_height_actual = title_paragraph.wrap(TITLE_WIDTH, page_height)
    
    # Position the title (Centered vertically, or slightly higher for better balance)
    TITLE_CENTER_Y = page_height * 3 / 5# Slightly above center
    
    # X position starts at the left margin of the title area
    x_position = TITLE_MARGIN
    
    # Calculate draw position (bottom edge of text block aligns with TITLE_CENTER_Y)
    y_draw_position = TITLE_CENTER_Y - title_height_actual 
    
    # Draw the Paragraph flowable directly onto the canvas
    title_paragraph.drawOn(canvas, x_position, y_draw_position)
    
    # --- 5. Logo in the Middle, Close to the Bottom ---
    
    IMG_WIDTH = 3.0 * inch
    IMG_HEIGHT = 1.2 * inch
    
    img_x_center = (page_width - IMG_WIDTH) / 2
    
    # ACTION: Place the logo relative to the bottom margin (e.g., 2 inches from the bottom)
    BOTTOM_MARGIN = 2.0 * inch
    img_y_position = BOTTOM_MARGIN
    
    if LOGO_PATH:        
        canvas.drawImage(
            LOGO_PATH, 
            
            img_x_center, 
            img_y_position, 
            width=IMG_WIDTH, 
            height=IMG_HEIGHT, 
            mask = 'auto'
        )

    canvas.restoreState()

def subsequent_pages_template(canvas, doc, styles, LOGO_PATH, BACKGROUND_IMAGE_PATH):
    """
    Template for subsequent pages: white background, logo on the left, 
    contextual data and link on the right in the header area.
    """
    canvas.saveState()
    
    page_width = letter[0]
    page_height = letter[1]

    
    # canvas.setFillAlpha(0.1) 
    try:
        canvas.drawImage(BACKGROUND_IMAGE_PATH, 0, 0, width=page_width, height=page_height, preserveAspectRatio=True)
    except Exception as e:
        print(f"Error loading background image: {e} at path {str(BACKGROUND_IMAGE_PATH)}")
        
    # canvas.setFillAlpha(1)
    # --- 1. Branding (Top Left) ---
    
    # Place the smaller logo image
    IMG_WIDTH = 1.4 * inch  # Smaller logo size
    IMG_HEIGHT = 0.8 * inch
    LOGO_X = 1.0 * inch 
    LOGO_Y = letter[1] - 1.0 * inch # Positioned in the top margin area
    
    try:
        canvas.drawImage(LOGO_PATH, LOGO_X, LOGO_Y, width=IMG_WIDTH, height=IMG_HEIGHT, mask='auto')
    except Exception as e:
        canvas.setFillColor(styles.TEXT_COLOR)
        canvas.setFont('Helvetica', 8)
        canvas.drawString(LOGO_X, LOGO_Y + 0.1 * inch, f"Logo Placeholder Error: {str(e)} for path {str(LOGO_PATH)}")
    # --- 2. Contextual Data (Top Right) ---
    
    # Define the starting Y position for the right-side text stack
    # This should align roughly with the top of the logo/header area
    START_Y = letter[1] - 0.5 * inch
    LINE_HEIGHT = 10 # Spacing between lines of text
    
    # Text pieces and link (using data passed via patient_data)
    info_lines = [
        f"info@rx2center.com",
        f"P.º Club Deportivo 4",
        f"28223 Pozuelo de Alarcón",
        "www.rx2center.com" # The static link
    ]
    
    canvas.setFont('Sansation', 8)
    canvas.setFillColor(styles.TEXT_COLOR)
    
    for i, line in enumerate(info_lines):
        y_pos = START_Y - (i * LINE_HEIGHT)
        
        # Calculate X position for right-alignment
        text_width = canvas.stringWidth(line, 'Sansation', 8)
        x_pos = page_width - inch - text_width
        
        # Apply a different color/style for the link (Optional aesthetic touch)
        if "www" in line:
            canvas.setFillColor(styles.ACCENT_COLOR) # Use accent color for the link
            canvas.setFont('Sansation', 8) # Use italics for a link
        
        canvas.drawString(x_pos, y_pos, line)
        
        # Reset color/font for the next line
        canvas.setFillColor(styles.TEXT_COLOR)
        canvas.setFont('Sansation', 8)

    # --- 3. Aesthetic Separator Line ---
    # A subtle line separating the header area from the content frame
    canvas.setStrokeColor(styles.ALTERNATIVE_COLOR)
    canvas.setLineWidth(0.5)
    canvas.line(inch, letter[1] - 0.95 * inch, page_width - inch, letter[1] - 0.95 * inch)


    # --- 4. Footer / Page Number ---
    canvas.setFont('Helvetica', 9)
    canvas.setFillColor(styles.TEXT_COLOR)
    page_string = "%d" % doc.page
    
    x_center = page_width / 2 - canvas.stringWidth(page_string, 'Helvetica', 9) / 2
    canvas.drawString(x_center, 0.5 * inch, page_string)
                      
    canvas.restoreState()

def generate_pdf(bike_measures_data, subject_data, analysis_table, joint_angles, joint_labels, plots, 
                 coment, image_paths, extra_data, report_title, compare, modality,contact_name, 
                 contact_tlf, contact_mail, report_elements):  #, selected_elemetns

    styles = setup_styles()
    story = []
    story.append(Spacer(1, 1)) 
    story.append(PageBreak())
    try:
        story.append(Paragraph("DATOS DE CONTACTO", styles['SectionHeading']))
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph("Nombre y apellidos: " + contact_name, styles['BodyText']))
        story.append(Spacer(1, 0.05 * inch))
        story.append(Paragraph("Número de teléfono: " + contact_tlf, styles['BodyText']))
        story.append(Spacer(1, 0.05 * inch))
        story.append(Paragraph("Correo electrónico: " + contact_mail, styles['BodyText']))
    except:
        story.append(
            Paragraph(f"ERROR: No se pudieron cargar los datos de contacto", styles['BodyText'])
        )
    # --- SECTION: INFORMACIÓN DE LA BICICLETA ---
    story.append(Paragraph("INFORMACIÓN DE LA BICICLETA", styles['SectionHeading']))
    story.append(Spacer(1, 0.2 * inch))
    
    # --------------------------------------------------------
    # 1. CREATE LEFT COLUMN (Bike Data)
    # --------------------------------------------------------
    
    # Define the fields to retrieve from the extra_data dictionary
    bike_fields = [
        ("Fabricante:", 'bike_Fabricante'),
        ("Modelo cuadro:", 'bike_Modelo_cuadro'),
        ("Talla:", 'bike_Talla'),
        ("Sillín:", 'bike_Sillin'),
        ("Pedal:", 'bike_Pedal'),
    ]
    
    bike_data_flowables = []
    # Add a section title for the data block
    try:
        for label, key in bike_fields:
            value = extra_data.get(key, "N/A")
            
            # Use Paragraphs to format the data: Label (Bold) + Value
            formatted_entry = Paragraph(
                f"<b>{label}</b><br/>{value}",  
                styles['BodyText']
            )
            bike_data_flowables.append(formatted_entry)
            bike_data_flowables.append(Spacer(1, 0.05 * inch))
    except:
       bike_data_flowables.append(Paragraph("Datos de la Bicicleta No Disponible", styles['BodyText'])) 
    
    # --------------------------------------------------------
    # 2. CREATE RIGHT COLUMN (Bike Image)
    # --------------------------------------------------------
    if (report_elements.get('bike foto') and 
    report_elements['bike foto'].get('checkbox') and
    report_elements['bike foto']['checkbox'].isChecked()):
        image_flowable = []
        bike_photo_path = image_paths.get('bike_photo')
        
        # Define dimensions for the layout (adjust as needed)
        # Usable Width: 6.5 inches (standard)
        TEXT_COL_WIDTH = 1.5 * inch
        IMAGE_COL_WIDTH = 5.0 * inch
        MAX_IMAGE_HEIGHT = 3.0 * inch 
        
        if bike_photo_path and os.path.exists(bike_photo_path):
            try:
                # Pass the path string directly to Image. Set height=None to preserve aspect ratio.
                bike_img = Image(bike_photo_path, 
                                 width=IMAGE_COL_WIDTH, 
                                 height=None, 
                                 hAlign='CENTER')
                bike_img._restrictSize(IMAGE_COL_WIDTH, MAX_IMAGE_HEIGHT)                 
                # Limit image height to prevent page overflow if a very tall image is uploade
                
                image_flowable.append(bike_img)
            except Exception as e:
                image_flowable.append(
                    Paragraph(f"ERROR: No se pudo cargar la imagen de la bicicleta.", styles['BodyText'])
                )
                print(f"Error loading bike photo: {e}")
        else:
            image_flowable.append(
                Paragraph("Foto de la Bicicleta No Disponible", styles['BodyText'])
            )
    else:
        TEXT_COL_WIDTH = 1.5 * inch
        IMAGE_COL_WIDTH = 5.0 * inch
        MAX_IMAGE_HEIGHT = 3.0 * inch 
        
        bike_flowable = []
        logoimage = Image(LOGO_PATH, 
                         width=IMAGE_COL_WIDTH, 
                         height=None, 
                         hAlign='CENTER')
        logoimage._restrictSize(IMAGE_COL_WIDTH, MAX_IMAGE_HEIGHT) 
        bike_flowable.append(logoimage)
    
    # --------------------------------------------------------
    # 3. COMBINE INTO A TABLE
    # --------------------------------------------------------
    
    bike_info_table = Table(
        # Table data is a single row with two columns (the lists of flowables)
        [[bike_data_flowables, image_flowable]],
        # Column widths must equal the total usable width (e.g., 6.5 inches)
        colWidths=[TEXT_COL_WIDTH, IMAGE_COL_WIDTH], 
        style=[
            ('VALIGN', (0, 0), (-1, -1), 'TOP'), # Align all content to the top
            ('LEFTPADDING', (0, 0), (0, 0), 5), 
            # Add a small gap between the text and the image
            ('RIGHTPADDING', (0, 0), (0, 0), 10),
            
            # --- FIX FOR IMAGE (Column 1) ---
            # Add a small gap to the left of the image
            ('LEFTPADDING', (1, 0), (1, 0), 10)
        ]
    )
    
    story.append(bike_info_table)
    story.append(Spacer(1, 0.5 * inch))
    
    # --- SECTION: DATOS DEL ENTRENAMIENTO ---
    story.append(Paragraph("DATOS DEL ENTRENAMIENTO", styles['SectionHeading']))
    story.append(Spacer(1, 0.2 * inch))
    
    # Define the fields to retrieve and their corresponding display labels
    training_fields = [
        ("Modalidad: ", 'training_Modalidad'),
        ("Años de práctica: ", 'training_Años_de_practica'),
        ("Horas semanales: ", 'training_Horas_semanales'),
        ("Km anuales: ", 'training_Km_anuales'),
    ]
    
    # Create a flowable list to hold all the entries
    training_data_flowables = []
    
    try:
        # Iterate through the defined fields, retrieve the value, and format it
        for label, key in training_fields:
            # Use .get() for safe retrieval, falling back to "N/A" if the field is missing
            # Note: The key uses underscores because it was defined that way in the dialog class.
            value = extra_data.get(key, "N/A") 
            
            # Format the entry with bold label and regular value
            formatted_entry = Paragraph(
                f"<b>{label}</b> {value}", 
                styles['BodyText']
            )
            training_data_flowables.append(formatted_entry)
            training_data_flowables.append(Spacer(1, 0.05 * inch)) # Small space after each item
        # Add all flowables to the main story
        for flowable in training_data_flowables:
            story.append(flowable)
    except:
        story.append(Paragraph("Datos de entrenamiento No Disponible", styles['BodyText']))
    story.append(Spacer(1, 0.5 * inch))
    if (report_elements.get('anthropometric_data') and 
    report_elements['anthropometric_data'].get('checkbox') and
    report_elements['anthropometric_data']['checkbox'].isChecked()):
        story.append(Paragraph("DATOS ANTROPOMÉTRICOS", styles['SectionHeading']))
        
        def create_subject_data_table(subject_data, styles):
            SUBJECT_DATA_MAP = [
            ("Altura Total", 'altura_total'), # Example: 'subject_name' is the key in your dict
            ("Altura del Torso", 'altura_torso'),
            ("Altura de la Entrpierna", 'altura_entrepierna'),
            ("Anchura de hombros", 'anchura_hombros'),
            ("Longitud de Pies", 'longitud_pies'),
            ("Longitud Metatarsal", 'longitud_metatarsal'),
            ("Altura del Hombro al Suelo", 'altura_hombro_suelo'),
            ("Altura de la Mano al Suelo", 'altura_mano_suelo'),
            
            ]
            if subject_data is not None:
                # 1. Prepare Data
                data = []
                for label, key in SUBJECT_DATA_MAP:
                    # Get the value from the input dictionary using the key
                    value = subject_data.get(key, "N/A") 
                    # Append the [Display Label, Value]
                    data.append([label, str(value)+' mm'])
                # Define column widths: 2.5 inches for the key, 3.5 inches for the value
                col_widths = [2.5 * inch, 3.5 * inch] 
                
                subject_table = Table(data, colWidths=col_widths)
                
                # 2. Define Aesthetic Style
                style = TableStyle([
                    # All Cells: Padding, Text Alignment
                    ('LEFTPADDING', (0, 0), (-1, -1), 10),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                    ('TOPPADDING', (0, 0), (-1, -1), 5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TEXTCOLOR', (0, 0), (-1, -1), styles.TEXT_COLOR),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
            
                    # Key Column (Left): Bold, Accent Color Background (subtle contrast)
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica'), # Bold the keys
                    ('BACKGROUND', (0, 0), (0, -1), HexColor('#F0F8FF')), # Very light blue background
            
                    # Grid/Borders: Only horizontal lines (cleaner look)
                    ('LINEBELOW', (0, 0), (-1, -1), 0.5, lightgrey), # Light grey line below every row
                    ('LINEBELOW', (0, -1), (-1, -1), 1, styles.ACCENT_COLOR), # A slightly thicker accent line at the bottom
                ])
                
                table_style = TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), HexColor('#D9E1F2')), # Header row background
                    ('TEXTCOLOR', (0, 0), (-1, 0), black),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('INNERGRID', (0, 0), (-1, -1), 0.25, lightgrey),
                    ('BOX', (0, 0), (-1, -1), 0.5, black),
                ])
            
                subject_table.setStyle(table_style)
                return subject_table
                      
            else:
                return Paragraph(
                "Subject data not available.", 
                styles['BodyText']
                )
                 
            
        subject_data_table = create_subject_data_table(subject_data, styles)
        story.append(Spacer(1, 0.5 * inch))
        story.append(subject_data_table)
        story.append(Spacer(1, 0.5 * inch))
    # --- SECTION: REGISTRO DE LESIONES ---
    story.append(Paragraph("REGISTRO DE LESIONES", styles['SectionHeading']))
    story.append(Spacer(1, 0.2 * inch))
    
    try:
        # The key for lesions data in the controller is simply 'lesiones'
        lesions_text = extra_data.get('lesiones')
        
        if lesions_text and lesions_text.strip():
            # Use Paragraph to format the large block of text.
            # The text will automatically wrap and flow down the page.
            lesions_paragraph = Paragraph(
                lesions_text.strip().replace('\n', '<br/>'), # Replace newlines with HTML <br/> for ReportLab
                styles['BodyText']
            )
            story.append(lesions_paragraph)
        else:
            story.append(
                Paragraph("No se registraron lesiones o historial médico relevante.", styles['BodyText'])
            )
    except:
        story.append(Paragraph("Datos de Lesiones No Disponible", styles['BodyText']))
    
    story.append(Spacer(1, 0.5 * inch))

    if (report_elements.get('analysis_table') and 
    report_elements['analysis_table'].get('checkbox') and
    report_elements['analysis_table']['checkbox'].isChecked()):
        from extract_table_data import extract_table_data
        
        analysis_table_data = extract_table_data(analysis_table)
        
        def create_analysis_table(analysis_table_data, joint_angles, joint_labels, styles, compare):
                
            # 1. Handle Missing or Empty Data
            # Check if data is None, or if it's a list with only the header row
            if not analysis_table_data or len(analysis_table_data) <= 1:
                return Paragraph(
                    "Analysis data not available.", 
                    styles['BodyText']
                )
            
            # Define Column Indices and Header (based on the compare flag)
            if compare:
                # Use all 7 columns (Label + 6 data columns)
                spanning_header = ['','PRE','','','POST','','']
                table_data = [[Paragraph(text) for text in spanning_header]]
                header_row = ['PARÁMETRO BIOMECÁNICO', 'MAX', 'MIN', 'RANGO', 'MAX', 'MIN', 'RANGO' ]
                data_indices = [0, 1, 2, 3, 4, 5, 6]
                # [3.0in (Label), 0.8in, 0.8in, 0.8in, 0.8in, 0.8in, 0.8in] = 7.8in (Too Wide, must reduce total width)
                col_widths = [2.9 * inch, 0.55 * inch, 0.55 * inch, 0.70 * inch, 0.55 * inch, 0.55 * inch, 0.70 * inch]
            else:
                # Use 4 columns (Label + Max, Min, ROM)
                header_row = ['PARÁMETRO BIOMECÁNICO', 'MÁXIMO', 'MÍNIMO', 'RANGO' ]
                data_indices = [0, 1, 2, 3] # Indices for Label, Max, Min, ROM
                # [3.0in (Label), 1.1in, 1.1in, 1.3in] = 6.5in (Good)
                col_widths = [3.5 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch] 
                table_data =[]
            # NEW Row 1 (Main Header)
            table_data.append([Paragraph(text) for text in header_row])   
            
            for i, variable in enumerate(joint_angles):
                for raw_row in analysis_table_data[1:]:
                    new_row = []
                    if raw_row[0] == variable:
                        # Extract and format the required columns
                        try:
                            # get label from label list
                            new_row.append(joint_labels[i]) 
                
                            # Columns 1, 2, 3: Max, Min, ROM (always included, formatted with °)
                            for col_index in [1, 2, 3]:
                                val = float(raw_row[col_index])
                                new_row.append(f"{val:.1f}°")
                            
                            # Columns 4, 5, 6: Extra data (only included if compare=True)
                            if compare:
                                for i in [4, 5, 6]:
                                    # Keep extra columns as-is (they contain 'N/A' or raw data)
                                    new_row.append(raw_row[i])
                                    
                            table_data.append(new_row)
                    
                        except (ValueError, IndexError) as e:
                            print(f"Skipping row due to data formatting error: {raw_row}. Error: {e}")
                            # Optional: Append a row with "Data Error" instead of skipping
                    
            # 3. Create the Table and Define Aesthetic Style
            
            table = Table(table_data, colWidths=col_widths)
            
            style_commands = [
                # General Grid and Padding
                ('GRID', (0, 0), (-1, -1), 0.5, lightgrey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                
                # Header Style (Row 0)
                ('BACKGROUND', (0, 0), (-1, 0), styles.ACCENT_COLOR),
                ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#FFFFFF')),
                ('FONTNAME', (0, 0), (-1, 0), 'Sansation'), 
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                
                # Body Alignment (Rows 1 to end)
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),      # Parameter Label (Col 0) to the left
                ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),    # All value columns (Col 1 onwards) to the right
            ]
            
            # Alternating Row Colors (simplified)
            # Start loop from row 1 (first data row)
            for i in range(1, len(table_data)):
                if i % 2 == 0:  # Even rows (2, 4, 6...) get white background
                    style_commands.append(('BACKGROUND', (0, i), (-1, i), HexColor('#FFFFFF')))
                else:           # Odd rows (1, 3, 5...) get light gray background
                    style_commands.append(('BACKGROUND', (0, i), (-1, i), HexColor('#F5F5F5')))
                    
            style = TableStyle(style_commands)
            table.setStyle(style)
            return table
        table_flowable_list = []    
        table_flowable_list.append(Paragraph("TABLA DE DATOS", styles['SectionHeading']))
        table_flowable_list.append(Spacer(1, 0.2 * inch))
        analysis_table = create_analysis_table(analysis_table_data, joint_angles, joint_labels, styles, compare)
        table_flowable_list.append(analysis_table)
        protected_table = KeepTogether(table_flowable_list)
        story.append(protected_table) 
        story.append(Spacer(1, 0.5 * inch))
   
    if (report_elements.get('plots') and 
    report_elements['plots'].get('checkbox') and
    report_elements['plots']['checkbox'].isChecked()):
        story.append(Paragraph("GRÁFICOS", styles['SectionHeading']))
        story.append(Spacer(1, 0.2 * inch))
        try:
            img_buffer = io.BytesIO()
        
            # 2. Save the Matplotlib Figure to the buffer as a PNG image
            # Use 'bbox_inches='tight'' to prevent clipping of labels/axes
            plots.savefig(img_buffer, format='png', bbox_inches='tight')
            
            # 3. Rewind the buffer's cursor to the beginning
            img_buffer.seek(0)
            
            # 4. Create the ReportLab Image flowable from the memory buffer
            plot_image = Image(img_buffer, width=6.5 * inch, height=4 * inch)
            plot_image.hAlign = 'CENTER' # Center the image horizontally
            story.append(plot_image)
            
        except Exception as e:
             story.append(Paragraph(
                 f"Error: No se pudo cargar el gráfico desde", 
                 styles['BodyText']
             ))
             print(f"ReportLab Plot Error: {e}")
        
        story.append(Spacer(1, 0.5 * inch))
        
    if  (report_elements.get('cyclist foto') and 
     report_elements['cyclist foto'].get('checkbox') and
     report_elements['cyclist foto']['checkbox'].isChecked()):
        # Configuration for the two stacked images
        photo_flowables_list = []
        photo_flowables_list.append(Paragraph("FOTOS DEL CICLISTA", styles['SectionHeading']))
        photo_flowables_list.append(Spacer(1, 0.2 * inch))
        # Calculate the maximum usable width on the page. 
        MAX_USABLE_WIDTH = 6.5 * inch 
        
        # Define a proportionate height. Setting height=None preserves aspect ratio.
        # If you set both width and height, the image might stretch or squeeze.
        IMAGE_WIDTH = MAX_USABLE_WIDTH * 4/5 
        IMAGE_HEIGHT = 4.2 *inch
        
        # --- 1. Handle Cyclist Photo 1 ---
        if compare:     
                photo_flowables_list.append(
                    Paragraph("Antes:", styles['BodyText'])
                )
                photo_flowables_list.append(Spacer(1, 0.1 * inch)) # Small gap between caption and image
        photo1_path = image_paths.get('cyclist_photo1')
        if photo1_path and os.path.exists(photo1_path):
            try:
                # Create the image flowable set to the full width
                img1 = Image(photo1_path, width=IMAGE_WIDTH, height=None, hAlign='CENTER')
                img1.restrictSize(IMAGE_WIDTH, MAX_IMAGE_HEIGHT)
                photo_flowables_list.append(img1)
            except Exception as e:
                photo_flowables_list.append(
                    Paragraph(f"ERROR FOTO 1: No se pudo cargar la imagen: {os.path.basename(photo1_path)}", styles['BodyText'])
                )
                print(f"Error loading cyclist_photo1: {e}")
        else:
            photo_flowables_list.append(
                Paragraph("FOTO CICLISTA 1: No disponible.", styles['BodyText'])
            )
        
        photo_flowables_list.append(Spacer(1, 0.2 * inch)) # Add a small gap between photos
        
        # --- 2. Handle Cyclist Photo 2 ---
        if compare: 
            photo_flowables_list.append(
                Paragraph("Después:", styles['BodyText'])
            )
            photo_flowables_list.append(Spacer(1, 0.1 * inch)) # Small gap between caption and image
            
            photo2_path = image_paths.get('cyclist_photo2')
            if photo2_path and os.path.exists(photo2_path):
                try:
                    # Create the image flowable set to the full width
                    img2 = Image(photo2_path, width=IMAGE_WIDTH, height=None, hAlign='CENTER')
                    img2._restrictSize(IMAGE_WIDTH, MAX_IMAGE_HEIGHT)
                    photo_flowables_list.append(img2)
                except Exception as e:
                    photo_flowables_list.append(
                        Paragraph(f"ERROR FOTO 2: No se pudo cargar la imagen: {os.path.basename(photo2_path)}", styles['BodyText'])
                    )
                    print(f"Error loading cyclist_photo2: {e}")
            else:
                photo_flowables_list.append(
                    Paragraph("FOTO CICLISTA 2: No disponible.", styles['BodyText'])
                )
        
        protected_photo_block = KeepTogether(photo_flowables_list)
        story.append(protected_photo_block)
    
    # --- SECTION: MEDIDAS DE LA BICICLETA ---
    # Only try to create the table if we actually have data (i.e., header + at least one row)
    if (report_elements.get('bike_measures') and 
    report_elements['bike_measures'].get('checkbox') and
    report_elements['bike_measures']['checkbox'].isChecked()):
        story.append(Spacer(1, 0.4 * inch))
        story.append(Paragraph("MEDIDAS DE LA BICICLETA", styles['SectionHeading']))
        story.append(Spacer(1, 0.2 * inch))
        # 1. Create the Table object
        # Calculate column widths (e.g., divide usable width evenly)
        num_cols = len(bike_measures_data[0]) if bike_measures_data else 1
        usable_width = 6.5 * inch # Adjust based on your document margins
        if compare:
            col_widths = [
                usable_width/5 ,
                usable_width*2/5,
                usable_width/5 ,
                usable_width/5,
                ]
            
            # 1. Get the header row
            header_row = bike_measures_data[0]
            
            # 2. Find the index for both columns
            pre_column_index = header_row.index('Pre')
            post_column_index = header_row.index('Post')
        
            # 3. Iterate through all the data rows (skip row 0, the header)
            for i in range(1, len(bike_measures_data)):
                
                # --- Handle 'Pre' Column ---
                current_pre_value = bike_measures_data[i][pre_column_index]
                # Check if the value is not empty or just whitespace
                if current_pre_value.strip():
                    new_pre_value = current_pre_value + ' mm'
                    bike_measures_data[i][pre_column_index] = new_pre_value
        
                # --- Handle 'Post' Column ---
                current_post_value = bike_measures_data[i][post_column_index]
                # Check if the value is not empty or just whitespace
                if current_post_value.strip():
                    new_post_value = current_post_value + ' mm'
                    bike_measures_data[i][post_column_index] = new_post_value
                    
        else:
            data_for_table_3col = []
            col_widths = [
                usable_width/4 ,
                usable_width*2/4,
                usable_width/4 ,
                ]
            header_row = bike_measures_data[0]
            idx_esquema = header_row.index('Esquema')
            idx_medida = header_row.index('Medida (mm)')
            idx_post = header_row.index('Post')
            
            data_for_table_3col.append([
            header_row[idx_esquema],
            header_row[idx_medida],
            header_row[idx_post]
            ])
            for i in range(1, len(bike_measures_data)):
                original_row = bike_measures_data[i]
                
                # Get the 'Pre' value
                pre_value = original_row[idx_post]
                
                # Add 'mm' suffix if the value is not empty
                if pre_value.strip():
                    pre_value += ' mm'
                
                # Create the new 3-column row (Esquema, Medida, Pre)
                new_row = [
                    original_row[idx_esquema],
                    original_row[idx_medida],
                    pre_value
                ]
                data_for_table_3col.append(new_row)

            # 5. Overwrite the original variable with the new 3-column data
            bike_measures_data = data_for_table_3col
            
        bike_measures_table = Table(
            bike_measures_data, 
            colWidths= col_widths
        )
        # 2. Define the Table Style
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#D9E1F2')), # Header row background
            ('TEXTCOLOR', (0, 0), (-1, 0), black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, lightgrey),
            ('BOX', (0, 0), (-1, -1), 0.5, black),
        ])
        # Add alternating row colors for readability (zebra stripes)
        for i in range(1, len(bike_measures_data)):
            if i % 2 == 0:
                table_style.add('BACKGROUND', (0, i), (-1, i), HexColor('#F5F5F5'))
                
        bike_measures_table.setStyle(table_style)
        MEASURES_IMAGE = ''
        print(modality)
        # 3. Add the table to the story
        if modality == 'Ruta':
            MEASURES_IMAGE = RUTA_BIKE_MEASURES_IMAGE
        if modality == 'TT':
            MEASURES_IMAGE = TT_BIKE_MEASURES_IMAGE
        if modality == 'MTB':
           MEASURES_IMAGE = MTB_BIKE_MEASURES_IMAGE
        
        img_bike_measure = Image( MEASURES_IMAGE,width=IMAGE_WIDTH, height=None, hAlign='CENTER')
        story.append(Spacer(1, 0.5 * inch))
        story.append(bike_measures_table)
    
    story.append(Paragraph("COMENTARIOS Y RECOMENDACIONES", styles['SectionHeading']))
    story.append(Spacer(1, 0.5 * inch))
    
    if coment:
        story.append(Paragraph(coment, styles['BodyText']))

        
    first_page_handler = lambda canvas, doc: title_page_template(
    canvas, 
    doc,  
    report_title,
    styles,
    LOGO_PATH,
    BACKGROUND_IMAGE_PATH           # This resolves the 'report_title' and 'styles' errors
    )
    
    later_pages_handler = lambda canvas, doc: subsequent_pages_template(
    canvas, 
    doc,
    styles,
    LOGO_PATH,
    BACKGROUND_IMAGE_PATH
    )
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            leftMargin=inch, rightMargin=inch,
                            topMargin=1.2 * inch, bottomMargin=0.75 * inch)
    
    doc.build(story, onFirstPage=first_page_handler, onLaterPages=later_pages_handler)
    buffer.seek(0)
    return buffer.read() # Returns the raw PDF data (bytes)