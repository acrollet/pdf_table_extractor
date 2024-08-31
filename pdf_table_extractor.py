import os
import sys
import argparse
from pdf2image import convert_from_path
import sqlite3
import matplotlib.pyplot as plt
import anthropic
from PIL import Image
import io
import json
import base64

def convert_pdf_to_image(pdf_path):
    return convert_from_path(pdf_path)[0]

def extract_tables_from_image(image):
    client = anthropic.Anthropic()
    
    # Convert PIL Image to bytes
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()

    # Encode the binary data to base64
    img_base64 = base64.b64encode(img_byte_arr).decode('utf-8')

    message = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=1500,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": """Extract any tables from this image as structured JSON data. Pay special attention to tables with titles like:
1. "Table 1 Results for the calculated entropy-forming-ability (EFA) descriptor, energetic distance from six-dimensional convex hull (ΔHf) and vibrational free energy at 2000 K (ΔFvib) for the five-metal carbide systems, arranged in descending order of EFA"
2. "TABLE 2 Comparison of the thermal properties of (Hf0.2Zr0.2Ta0.2Nb0.2Ti0.2)C with binary carbides HfC, ZrC, TaC, NbC, and TiC. The data is at room temperature unless specifically indicated"

These tables likely contain scientific data related to metal carbide systems and their properties. Extract all table data, including headers and values. If no tables are found, return an empty list.

Format the extracted data as a list of dictionaries, where each dictionary represents a table with the following structure:
{
    "title": "The full title of the table",
    "headers": ["Column1", "Column2", ...],
    "data": [
        ["Row1Col1", "Row1Col2", ...],
        ["Row2Col1", "Row2Col2", ...],
        ...
    ]
}"""
                    }
                ]
            }
        ]
    )
    
    # Print raw response for debugging
    print("Raw API response:", message.content[0].text)
    
    try:
        return json.loads(message.content[0].text)
    except json.JSONDecodeError:
        print("Failed to parse JSON. Returning empty list.")
        return []

def harmonize_data(all_tables):
    harmonized_data = []
    for table in all_tables:
        harmonized_table = {
            "title": table["title"],
            "columns": table["headers"],
            "rows": table["data"]
        }
        harmonized_data.append(harmonized_table)
    return harmonized_data

def insert_into_sqlite(data, db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''CREATE TABLE IF NOT EXISTS tables
                      (id INTEGER PRIMARY KEY, title TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS columns
                      (id INTEGER PRIMARY KEY, table_id INTEGER, name TEXT,
                       FOREIGN KEY(table_id) REFERENCES tables(id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS rows
                      (id INTEGER PRIMARY KEY, table_id INTEGER,
                       FOREIGN KEY(table_id) REFERENCES tables(id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS cell_values
                      (row_id INTEGER, column_id INTEGER, value TEXT,
                       FOREIGN KEY(row_id) REFERENCES rows(id),
                       FOREIGN KEY(column_id) REFERENCES columns(id))''')
    
    # Insert data
    for table in data:
        cursor.execute("INSERT INTO tables (title) VALUES (?)", (table['title'],))
        table_id = cursor.lastrowid
        
        for col_name in table['columns']:
            cursor.execute("INSERT INTO columns (table_id, name) VALUES (?, ?)", (table_id, col_name))
        
        for row in table['rows']:
            cursor.execute("INSERT INTO rows (table_id) VALUES (?)", (table_id,))
            row_id = cursor.lastrowid
            for col_id, value in enumerate(row, start=1):
                cursor.execute("INSERT INTO cell_values (row_id, column_id, value) VALUES (?, ?, ?)",
                               (row_id, col_id, value))
    
    conn.commit()
    conn.close()

def visualize_data(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Fetch data (adjust query as needed)
    cursor.execute("SELECT * FROM extracted_data")
    data = cursor.fetchall()
    
    # Simple visualization (adjust as needed)
    plt.figure(figsize=(10, 6))
    plt.bar(range(len(data)), [len(json.loads(row[1])) for row in data])
    plt.xlabel('Row ID')
    plt.ylabel('Number of Items')
    plt.title('Visualization of Extracted Data')
    plt.savefig('data_visualization.png')
    plt.close()

    conn.close()

def main(directory):
    all_tables = []
    for filename in os.listdir(directory):
        if filename.endswith('.pdf'):
            pdf_path = os.path.join(directory, filename)
            print(f"Processing {pdf_path}")
            image = convert_pdf_to_image(pdf_path)
            tables = extract_tables_from_image(image)
            print(f"Extracted {len(tables)} tables from {filename}")
            if tables:
                all_tables.extend(tables)
    
    print(f"Total tables extracted: {len(all_tables)}")
    harmonized_data = harmonize_data(all_tables)
    db_path = 'extracted_data.db'
    insert_into_sqlite(harmonized_data, db_path)
    visualize_data(db_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract tables from PDF files and process the data.")
    parser.add_argument("directory", help="Directory containing PDF files")
    args = parser.parse_args()
    main(args.directory)
