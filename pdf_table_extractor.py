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
import shutil
import pytesseract
import hashlib

def convert_pdf_to_images(pdf_path):
    images = convert_from_path(pdf_path)
    return images

def filter_images_with_table(images):
    filtered_images = []
    for image in images:
        text = pytesseract.image_to_string(image)
        if "Table" in text:
            filtered_images.append(image)
    return filtered_images

def extract_tables_from_images(images, filename):
    client = anthropic.Anthropic()
    all_tables = []

    for i, image in enumerate(images):
        # Resize the image if it's too large
        max_size = (1600, 1600)  # Adjust these dimensions as needed
        image.thumbnail(max_size, Image.LANCZOS)
        
        # Convert PIL Image to bytes
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        if len(img_byte_arr) > 5 * 1024 * 1024:  # 5MB in bytes
            print("Image size exceeds 5MB. Skipping this image.")
            continue

        # Encode the binary data to base64
        img_base64 = base64.b64encode(img_byte_arr).decode('utf-8')

        full_response = ""
        chunk_size = 4096  # Adjust this value based on your needs

        message = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=4000,  # Increased max_tokens
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
        
        # Collect the full response
        for chunk in message.content[0].text:
            full_response += chunk
            if len(full_response) >= chunk_size:
                print(f"Received {len(full_response)} characters")
        
        # Print raw response for debugging
        print("Raw API response:", full_response)
        
        try:
            tables = json.loads(full_response)
            for table in tables:
                table['filename'] = filename
                table['page_number'] = i + 1
            all_tables.extend(tables)
        except json.JSONDecodeError:
            print("Failed to parse JSON. Skipping this image.")

    return all_tables

def harmonize_data(all_tables):
    harmonized_data = []
    for table in all_tables:
        harmonized_table = {
            "filename": table["filename"],
            "page_number": table["page_number"],
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
                      (id INTEGER PRIMARY KEY, filename TEXT, page_number INTEGER, title TEXT)''')
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
        cursor.execute("INSERT INTO tables (filename, page_number, title) VALUES (?, ?, ?)", 
                       (table['filename'], table['page_number'], table['title']))
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
    
    # Fetch data from the tables table
    cursor.execute("SELECT id, filename, page_number, title FROM tables")
    tables = cursor.fetchall()
    
    # Fetch the number of rows for each table
    table_sizes = []
    for table_id, _, _, _ in tables:
        cursor.execute("SELECT COUNT(*) FROM rows WHERE table_id = ?", (table_id,))
        row_count = cursor.fetchone()[0]
        table_sizes.append(row_count)
    
    # Simple visualization
    plt.figure(figsize=(12, 6))
    plt.bar(range(len(tables)), table_sizes)
    plt.xlabel('Table')
    plt.ylabel('Number of Rows')
    plt.title('Number of Rows per Extracted Table')
    plt.xticks(range(len(tables)), [f"{table[1]}:{table[2]}" for table in tables], rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig('data_visualization.png')
    plt.close()

    conn.close()

def manage_processed_files(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create table for processed files if it doesn't exist
    cursor.execute('''CREATE TABLE IF NOT EXISTS processed_files
                      (id INTEGER PRIMARY KEY, filename TEXT, file_hash TEXT)''')
    
    def is_file_processed(filename, file_hash):
        cursor.execute("SELECT * FROM processed_files WHERE filename = ? AND file_hash = ?", (filename, file_hash))
        return cursor.fetchone() is not None
    
    def mark_file_as_processed(filename, file_hash):
        cursor.execute("INSERT INTO processed_files (filename, file_hash) VALUES (?, ?)", (filename, file_hash))
        conn.commit()
    
    return is_file_processed, mark_file_as_processed, conn.close

def main(directory, debug=False):
    if debug:
        debug_dir = 'debug_images'
        if os.path.exists(debug_dir):
            shutil.rmtree(debug_dir)
        os.makedirs(debug_dir)

    db_path = 'extracted_data.db'
    is_file_processed, mark_file_as_processed, close_db = manage_processed_files(db_path)

    all_tables = []
    for filename in os.listdir(directory):
        if filename.endswith('.pdf'):
            pdf_path = os.path.join(directory, filename)
            
            # Calculate file hash
            with open(pdf_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            
            # Check if file has been processed
            if is_file_processed(filename, file_hash):
                print(f"Skipping already processed file: {filename}")
                continue
            
            print(f"Processing {pdf_path}")
            images = convert_pdf_to_images(pdf_path)
            filtered_images = filter_images_with_table(images)
            
            if debug:
                for i, image in enumerate(filtered_images):
                    image_filename = f"{os.path.splitext(filename)[0]}_page_{i+1}.png"
                    image_path = os.path.join(debug_dir, image_filename)
                    image.save(image_path, format='PNG')
                    print(f"Saved debug image: {image_path}")
                continue  # Skip further processing in debug mode
            
            tables = extract_tables_from_images(filtered_images, filename)
            print(f"Extracted {len(tables)} tables from {filename}")
            if tables:
                all_tables.extend(tables)
            
            # Mark file as processed
            mark_file_as_processed(filename, file_hash)
    
    if debug:
        print(f"Debug images saved to {debug_dir}")
        close_db()
        return

    print(f"Total tables extracted: {len(all_tables)}")
    harmonized_data = harmonize_data(all_tables)
    insert_into_sqlite(harmonized_data, db_path)
    visualize_data(db_path)
    close_db()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract tables from PDF files and process the data.")
    parser.add_argument("directory", help="Directory containing PDF files")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode to dump images and quit")
    args = parser.parse_args()
    main(args.directory, args.debug)
