import os
import requests
from dotenv import load_dotenv
import markdown
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

# Load environment variables
load_dotenv()

# Constants
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OUTPUT_DIR = "processed_notes"

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_notes_with_gemini(transcription):
    """Sends combined transcription to Gemini API to generate structured notes."""
    prompt = f"""Please convert the following lecture/meeting transcription into well-structured, detailed notes. 
    Follow these guidelines:
    1. Create clear main topics and subtopics with proper hierarchy
    2. Use bullet points for key concepts and examples
    3. Highlight important definitions and formulas
    4. Include relevant examples and explanations
    5. Add section headers and subheaders
    6. Format mathematical equations clearly
    7. Use markdown formatting for better readability
    8. Include a summary at the end of each major section
    9. Add a table of contents at the beginning
    
    Transcription:
    {transcription}
    
    Please format the output in markdown with proper headings, bullet points, and sections."""

    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", json=payload, headers=headers)
    
    if response.status_code == 200:
        result = response.json()
        return result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    else:
        print(f"❌ Error {response.status_code}: {response.text}")
        return ""

def convert_md_to_pdf(md_content, output_pdf_path):
    """Converts markdown content to a PDF file with proper styling."""
    # Convert markdown to HTML
    html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])
    
    # Add custom CSS
    css = CSS(string='''
        @page {
            margin: 2.5cm;
            @top-right {
                content: "Page " counter(page);
            }
        }
        body {
            font-family: "DejaVu Sans", sans-serif;
            line-height: 1.6;
            color: #333;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 2px solid #eee;
            padding-bottom: 0.3em;
        }
        h2 {
            color: #34495e;
            margin-top: 1.5em;
        }
        h3 {
            color: #2c3e50;
        }
        code {
            background-color: #f8f9fa;
            padding: 0.2em 0.4em;
            border-radius: 3px;
            font-family: "DejaVu Sans Mono", monospace;
        }
        pre {
            background-color: #f8f9fa;
            padding: 1em;
            border-radius: 5px;
            overflow-x: auto;
        }
        blockquote {
            border-left: 4px solid #ddd;
            padding-left: 1em;
            color: #666;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 1em 0;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #f8f9fa;
        }
        ul, ol {
            padding-left: 2em;
        }
        li {
            margin: 0.5em 0;
        }
    ''')
    
    # Configure fonts
    font_config = FontConfiguration()
    
    # Generate PDF
    HTML(string=html_content).write_pdf(
        output_pdf_path,
        stylesheets=[css],
        font_config=font_config
    )

def process_markdown_files(audio_md_path, video_md_path):
    """Process markdown files to generate structured notes and save as PDF."""
    # Combine content from both markdown files
    combined_content = ""
    for file_path in [audio_md_path, video_md_path]:
        with open(file_path, "r", encoding="utf-8") as f:
            combined_content += f.read().strip() + "\n\n"

    if not combined_content.strip():
        print("⚠️ No content found to process.")
        return

    print("🧠 Sending combined content to Gemini...")
    structured_notes = generate_notes_with_gemini(combined_content)

    # Save structured notes as markdown
    md_output_file = os.path.join(OUTPUT_DIR, "combined_notes.md")
    with open(md_output_file, "w", encoding="utf-8") as f:
        f.write(structured_notes)

    print(f"✅ Notes generated and saved to: {md_output_file}")

    # Convert markdown to PDF
    pdf_output_file = os.path.join(OUTPUT_DIR, "combined_notes.pdf")
    convert_md_to_pdf(structured_notes, pdf_output_file)

    print(f"✅ PDF generated and saved to: {pdf_output_file}")

# Example usage
audio_md_path = "scripts/output.md"  # Updated path to audio notes markdown
video_md_path = "scripts/ocr_notes.md"  # Updated path to video notes markdown
process_markdown_files(audio_md_path, video_md_path)
