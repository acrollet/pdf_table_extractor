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
        max_tokens=1000,
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
                        "text": "Extract any tables from this image as structured JSON data. If no tables are found, return an empty list."
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
    # This is a placeholder function. You'll need to implement the logic
    # to harmonize the data based on your specific requirements.
    return all_tables

def insert_into_sqlite(data, db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create table (adjust schema as needed)
    cursor.execute('''CREATE TABLE IF NOT EXISTS extracted_data
                      (id INTEGER PRIMARY KEY, data TEXT)''')
    
    # Insert data
    for item in data:
        cursor.execute("INSERT INTO extracted_data (data) VALUES (?)", (json.dumps(item),))
    
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
