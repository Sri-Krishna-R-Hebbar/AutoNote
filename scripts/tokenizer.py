from transformers import AutoTokenizer
import torch

tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")

def tokenize_text(text):
    """Tokenizes the given text and returns token IDs."""
    return tokenizer.encode(text, truncation=True, padding="max_length", max_length=512)

def detokenize_text(token_ids):
    """Converts token IDs back to text."""
    # token_ids is already a list here
    # Convert it back to a tensor before applying argmax
    token_ids = torch.tensor(token_ids)  
    token_ids = torch.argmax(token_ids, dim=-1).tolist() 
    return tokenizer.decode(token_ids, skip_special_tokens=True)