import torch
from transformer_model import TransformerModel
from tokenizer import tokenize_text, detokenize_text
import json
from transformers import AutoTokenizer
import os

# Load the trained model
MODEL_PATH = "transformer_model.pth"
# vocab_size = 10000  
tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
vocab_size = tokenizer.vocab_size # Ensure this matches the training configuration

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = TransformerModel(vocab_size=vocab_size).to(device)
model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
model.eval()

# Load dataset.json
with open("test_data.json", "r", encoding="utf-8") as f:
    dataset = json.load(f)

OUTPUT_DIR = "processed_notes"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Generate notes for each transcription
for entry in dataset:
    audio_path = entry["audio"]
    transcription = entry["text"].strip()
    
    if not transcription:
        print(f"Skipping empty transcription for {audio_path}")
        continue
    
    # Tokenize input
    input_tokens = tokenize_text(transcription)
    input_tensor = torch.tensor(input_tokens).unsqueeze(0).to(device)
    
    # Generate output
    with torch.no_grad():
        output_tensor = model(input_tensor, input_tensor)
    
    # Convert tokens back to text
    generated_text = detokenize_text(output_tensor.squeeze(0).cpu().tolist())
    
    # Save notes
    video_name = os.path.basename(os.path.dirname(audio_path))
    output_path = os.path.join(OUTPUT_DIR, f"{video_name}.md")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(generated_text)
    
    print(f"Notes saved for {video_name} at {output_path}")
