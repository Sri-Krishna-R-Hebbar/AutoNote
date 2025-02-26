import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
import json

class TransformerModel(nn.Module):
    def __init__(self, vocab_size, d_model=512, num_heads=8, num_layers=4, dropout=0.1):
        super(TransformerModel, self).__init__()
        
        self.embedding = nn.Embedding(vocab_size, d_model)
        
        self.encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=num_heads, dropout=dropout
        )
        self.encoder = nn.TransformerEncoder(self.encoder_layer, num_layers=num_layers)
        
        self.decoder_layer = nn.TransformerDecoderLayer(
            d_model=d_model, nhead=num_heads, dropout=dropout
        )
        self.decoder = nn.TransformerDecoder(self.decoder_layer, num_layers=num_layers)
        
        self.output_layer = nn.Linear(d_model, vocab_size)
    
    def forward(self, src, tgt):
        # Convert input tokens to embeddings
        src_emb = self.embedding(src)  # Shape: [batch_size, src_sequence_length, d_model]
        tgt_emb = self.embedding(tgt)  # Shape: [batch_size, tgt_sequence_length, d_model]
        
        # Transpose for transformer (sequence length first)
        src_emb = src_emb.transpose(0, 1)  # Shape: [src_sequence_length, batch_size, d_model]
        tgt_emb = tgt_emb.transpose(0, 1)  # Shape: [tgt_sequence_length, batch_size, d_model]
        
        memory = self.encoder(src_emb)  # Encoder processing
        output = self.decoder(tgt_emb, memory)  # Decoder processing
        
        # Transpose back to [batch_size, tgt_sequence_length, d_model]
        output = output.transpose(0, 1)  # Shape: [tgt_sequence_length, batch_size, d_model]
        
        return self.output_layer(output)  # Shape: [tgt_sequence_length, batch_size, vocab_size]

# Dataset Class for Loading Training Data
class NotesDataset(Dataset):
    def __init__(self, json_file, tokenizer, max_length=512):
        with open(json_file, 'r') as f:
            self.data = json.load(f)
        self.tokenizer = tokenizer
        self.max_length = max_length
        
        # Filter out empty transcriptions
        self.data = [item for item in self.data if item["text"].strip()]
    
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        transcription = self.data[idx]["text"]
        input_tokens = self.tokenizer(transcription, padding="max_length", truncation=True, max_length=self.max_length, return_tensors="pt")
        target_tokens = self.tokenizer(transcription, padding="max_length", truncation=True, max_length=self.max_length, return_tensors="pt")
        
        return input_tokens.input_ids.squeeze(0), target_tokens.input_ids.squeeze(0)

# Training Function
def train_model(model, dataset, tokenizer, epochs=10, batch_size=16, lr=5e-5):
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()
    
    for epoch in range(epochs):
        total_loss = 0
        for src, tgt in dataloader:
            print(f"Source shape: {src.shape}, Target shape: {tgt.shape}")
            optimizer.zero_grad()
            output = model(src, tgt[:, :-1])  # Shift target for training
            
            # Reshape output and target for loss calculation
            output = output.view(-1, output.shape[-1])  # Shape: [batch_size * seq_length, vocab_size]
            target = tgt[:, 1:].reshape(-1)  # Shape: [batch_size * (seq_length - 1)]
            
            loss = criterion(output, target)  # Calculate loss
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        
        print(f"Epoch {epoch+1}, Loss: {total_loss / len(dataloader)}")
    
    torch.save(model.state_dict(), "transformer_model.pth")
    print("Model saved!")

# Example usage:
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")  # Example tokenizer
VOCAB_SIZE = tokenizer.vocab_size

dataset = NotesDataset("processed_data/training_data.json", tokenizer)
model = TransformerModel(vocab_size=VOCAB_SIZE)
train_model(model, dataset, tokenizer)