import os
import cv2
import requests
from transformers import Qwen2VLForConditionalGeneration, AutoTokenizer, AutoProcessor
from qwen_vl_utils import process_vision_info
from PIL import Image
import torch

# Constants
OCR_TEXT_DIR = "ocr_texts"
OUTPUT_DIR = "processed_notes"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GEMINI_API_KEY = "AIzaSyBhjM258PcXrpKGz-k3weT8fNnR75I5jys"  # 🔐 Replace this with your Gemini API key
EXTRACT_INTERVAL_SECONDS = 5  # Extract frames every 5 seconds

# Ensure directories exist
os.makedirs(OCR_TEXT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load the model and processor
model = Qwen2VLForConditionalGeneration.from_pretrained(
    "Qwen/Qwen2-VL-2B-Instruct",
    device_map="auto",
    torch_dtype=torch.float16
)
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2-VL-2B-Instruct")
processor = AutoProcessor.from_pretrained("Qwen/Qwen2-VL-2B-Instruct")

def extract_frames(video_path, interval_seconds):
    """Extract frames from a video at regular time intervals."""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_interval = int(fps * interval_seconds)
    frames = []
    frame_count = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if frame_count % frame_interval == 0:
            frames.append(frame)
        frame_count += 1

    cap.release()
    return frames

def perform_ocr_on_frame(frame):
    """Perform OCR on a single frame using Qwen2-VL model."""
    # Convert frame to PIL Image
    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(image)

    # Prepare input data
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": pil_image},
                {"type": "text", "text": "What does the image say?"},
            ],
        }
    ]

    # Process input data
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, _ = process_vision_info(messages)
    inputs = processor(
        text=[text],
        images=image_inputs,
        padding=True,
        return_tensors="pt"
    )
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    # Generate output
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=128)

    # Decode result
    generated_ids_trimmed = [out_ids[len(inputs['input_ids'][0]):] for out_ids in generated_ids]
    output_text = processor.batch_decode(generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)
    return output_text[0]

def generate_notes_with_gemini(transcription):
    """Sends OCR transcription to Gemini API to generate structured notes."""
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

def process_video(video_path):
    """Process the video to extract text and generate notes."""
    frames = extract_frames(video_path, EXTRACT_INTERVAL_SECONDS)
    ocr_combined_text = ""

    for i, frame in enumerate(frames):
        ocr_text = perform_ocr_on_frame(frame)
        ocr_combined_text += ocr_text + "\n\n"

        # Save individual frame OCR text
        frame_text_path = os.path.join(OCR_TEXT_DIR, f"frame_{i:04d}.txt")
        with open(frame_text_path, "w", encoding="utf-8") as f:
            f.write(ocr_text)

    if not ocr_combined_text.strip():
        print("⚠️ No OCR text found to process.")
    else:
        print("🧠 Sending OCR content to Gemini...")
        structured_notes = generate_notes_with_gemini(ocr_combined_text)

        # Save structured notes
        output_file = os.path.join(OUTPUT_DIR, "ocr_notes.md")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(structured_notes)

        print(f"✅ Notes generated and saved to: {output_file}")

# Example usage
video_path = "output.mp4"  # Replace with your video path
process_video(video_path)
