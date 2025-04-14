import json
from datasets import load_dataset

# Load Wikipedia dataset from Hugging Face (English) with trust_remote_code=True
dataset = load_dataset("wikipedia", "20220301.en", split="train", trust_remote_code=True)

# Determine the size of the dataset
total_articles = len(dataset)
chunk_size = total_articles // 25  # 20% of the dataset

# Print the first few entries to understand the structure
print("Sample entries from the dataset:")
for i in range(5):
    print(dataset[i])  # Print the first 5 entries

# Save as JSON in chunks
output_file = "training_data.json"
with open(output_file, "w", encoding="utf-8") as f:
    for i in range(0, total_articles, chunk_size):
        # Extract a chunk of articles (20%)
        chunk = dataset[i:i + chunk_size]
        
        # Extract the text from each article
        articles = [{"text": article["text"]} for article in chunk]  # Accessing the "text" key directly
        
        # Write the chunk to the JSON file
        json.dump(articles, f, ensure_ascii=False, indent=4)
        
        # Print progress
        print(f"Processed chunk {i // chunk_size + 1}: {len(articles)} articles saved.")