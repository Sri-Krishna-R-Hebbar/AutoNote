import os
import requests
from fpdf import FPDF

# Constants
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GEMINI_API_KEY = "AIzaSyCR965bweN1CKG5AnLNXrTBRufc-5gVc14"  # 🔐 Replace this with your Gemini API key
OUTPUT_DIR = "processed_notes"

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_notes_with_gemini(transcription):
    """Sends combined transcription to Gemini API to generate structured notes."""
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": transcription}]}]
    }
    response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", json=payload, headers=headers)

    if response.status_code == 200:
        result = response.json()
        return result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    else:
        print(f"❌ Error {response.status_code}: {response.text}")
        return ""

def convert_md_to_pdf(md_content, output_pdf_path):
    """Converts markdown content to a PDF file."""
    class PDF(FPDF):
        def header(self):
            self.set_font("DejaVu", "B", 12)
            self.cell(0, 10, "Structured Notes", 0, 1, "C")

        def footer(self):
            self.set_y(-15)
            self.set_font("DejaVu", "I", 8)
            self.cell(0, 10, f"Page {self.page_no()}", 0, 0, "C")

    pdf = PDF()
    # Add DejaVu font for Unicode support
    pdf.add_font("DejaVu", "", "DejaVuSans.ttf", uni=True)
    pdf.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf", uni=True)
    pdf.add_font("DejaVu", "I", "DejaVuSans-Oblique.ttf", uni=True)
    
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("DejaVu", size=12)

    # Add markdown content to PDF
    for line in md_content.split("\n"):
        pdf.multi_cell(0, 10, line)

    pdf.output(output_pdf_path)

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
