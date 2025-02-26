import json
import re
import os

def clean_text(text):
    """
    Cleans the input text by removing unwanted characters and formatting.
    Args:
        text (str): The input transcription text.
    Returns:
        str: The cleaned text.
    """
    # Example cleaning steps
    text = text.lower()  # Convert to lowercase
    text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces with a single space
    text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
    return text.strip()  # Remove leading and trailing whitespace

def create_training_data(dataset_path, output_path):
    """
    Creates a training dataset from the given dataset path and saves it as a JSON file.
    Args:
        dataset_path (str): Path to the input dataset (e.g., a text file or JSON).
        output_path (str): Path to save the output JSON file.
    """
    # Load your dataset (assuming it's a JSON file with a list of entries)
    with open(dataset_path, 'r') as f:
        data = json.load(f)

    training_data = []
    for item in data:
        # Assuming each item is a dictionary with a "text" key
        if "text" in item:
            cleaned_text = clean_text(item["text"])
            if cleaned_text:  # Ensure it's not empty after cleaning
                training_data.append({"text": cleaned_text})

    # Ensure the output directory exists
    output_dir = os.path.dirname(output_path)
    os.makedirs(output_dir, exist_ok=True)

    # Save to JSON
    with open(output_path, 'w') as f:
        json.dump(training_data, f, indent=4)

if __name__ == "__main__":
    dataset_path = "dataset.json"  # Change this to your input file path
    output_path = "processed_data/training_data.json"  # Change this to your desired output path
    create_training_data(dataset_path, output_path)
    print(f"Training data created and saved to {output_path}")