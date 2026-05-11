from PyQt5.QtWidgets import QTableWidget, QWidget, QTableWidgetItem

def extract_table_data(table_widget: QTableWidget) -> list[list[str]]:
    """
    Extracts all data, including headers, from a QTableWidget 
    into a standard Python list of lists (table format).
    """
    row_count = table_widget.rowCount()
    column_count = table_widget.columnCount()
    data = []

    # 1. Extract Column Headers (Header row)
    header_row = []
    for col in range(column_count):
        header_item = table_widget.horizontalHeaderItem(col)
        header_row.append(header_item.text() if header_item is not None else f"Column {col}")
    data.append(header_row)

    # 2. Extract Row Data
    for row in range(row_count):
        row_data = []
        for col in range(column_count):
            item = table_widget.item(row, col)
            # Use item.text() if the cell has content, otherwise use an empty string
            cell_text = item.text() if item is not None else ""
            row_data.append(cell_text)
        data.append(row_data)
        
    return data