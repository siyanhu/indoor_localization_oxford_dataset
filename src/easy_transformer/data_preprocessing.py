import os
import torch
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split

class IMUSequence:
    def __init__(self, imu_file, vi_file, sequence_length):
        imu_data = pd.read_csv(imu_file, header=None).iloc[:, list(range(4,16))].values

        vi_data = pd.read_csv(vi_file, header=None).iloc[:, 2:5].values  # Only x, y, z

        self.sequences = []
        self.targets = []

        for i in range(0, len(imu_data) - sequence_length, sequence_length):
            self.sequences.append(imu_data[i:i+sequence_length])
            self.targets.append(vi_data[i+sequence_length])

        self.sequences = np.array(self.sequences)
        self.targets = np.array(self.targets)

class IMUDataset(Dataset):
    def __init__(self, sequences, device):
        self.sequences = []
        self.targets = []
        for seq in sequences:
            self.sequences.extend(seq.sequences)
            self.targets.extend(seq.targets)
        
        self.sequences = torch.FloatTensor(np.array(self.sequences)).to(device)
        self.targets = torch.FloatTensor(np.array(self.targets)).to(device)

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        return self.sequences[idx], self.targets[idx]

def load_sequences(root_dir, sequence_length):
    sequences = []
    for data_folder in os.listdir(root_dir):
        folder_path = os.path.join(root_dir, data_folder, 'syn')
        if os.path.isdir(folder_path):
            imu_files = sorted([f for f in os.listdir(folder_path) if f.startswith('imu')])
            vi_files = sorted([f for f in os.listdir(folder_path) if f.startswith('vi')])
            
            for imu_file, vi_file in zip(imu_files, vi_files):
                sequences.append(IMUSequence(
                    os.path.join(folder_path, imu_file),
                    os.path.join(folder_path, vi_file),
                    sequence_length
                ))
    return sequences

def prepare_data(root_dir, sequence_length, batch_size, device):
    all_sequences = load_sequences(root_dir, sequence_length)
    train_sequences, val_sequences = train_test_split(all_sequences, test_size=0.1, random_state=42)

    train_dataset = IMUDataset(train_sequences, device)
    val_dataset = IMUDataset(val_sequences, device)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size)

    return train_loader, val_loader, train_dataset, val_dataset