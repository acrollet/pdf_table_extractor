# PDF Table Extractor

This project is a Python script that extracts tables from PDF files, processes the data, and stores it in a SQLite database. It also includes functionality to visualize the extracted data and manage processed files.

## Features

- Convert PDF files to images
- Filter images containing tables
- Extract tables using OCR and AI (Claude API)
- Extract primary author and DOI information
- Store extracted data in a SQLite database
- Visualize extracted data
- Track processed files to avoid redundant processing

## Prerequisites

- Python 3.7+
- Tesseract OCR
- Poppler (for pdf2image)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/acrollet/pdf-table-extractor.git
   cd pdf-table-extractor
   ```

2. Install the required Python packages:
   ```
   pip install pdf2image pytesseract anthropic matplotlib Pillow
   ```

3. Install Tesseract OCR:
   - On macOS: `brew install tesseract`
   - On Ubuntu: `sudo apt-get install tesseract-ocr`
   - On Windows: Download and install from [GitHub](https://github.com/UB-Mannheim/tesseract/wiki)

4. Install Poppler:
   - On macOS: `brew install poppler`
   - On Ubuntu: `sudo apt-get install poppler-utils`
   - On Windows: Download and install from [poppler releases](http://blog.alivate.com.au/poppler-windows/)

5. Set up your Anthropic API key:
   ```
   export ANTHROPIC_API_KEY=your_api_key_here
   ```

## Usage

Run the script with the following command:

```
python pdf_table_extractor.py /path/to/pdf/directory [--debug] [--reset]
```

- `/path/to/pdf/directory`: The directory containing the PDF files to process
- `--debug`: (Optional) Enable debug mode to save filtered images without processing
- `--reset`: (Optional) Reset the record of processed files

## Output

- The extracted data is stored in a SQLite database named `extracted_data.db`
- A simple visualization of the extracted data is saved as `data_visualization.png`

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License.

