import argparse
import torch
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # FATAL
from lstm_model import IMULSTMModel
from data_preprocessing import prepare_data
from lstm_test import test_model
from torch.utils.tensorboard import SummaryWriter
import datetime
import os


def train(args):
    # Create a custom log directory name
    current_time = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_dir = os.path.join("../../logs", f"{current_time}_input{args.input_size}_hidden{'-'.join(map(str, args.hidden_sizes))}_output{args.output_size}_lr{args.learning_rate}_batch{args.batch_size}")
    writer = SummaryWriter(log_dir)

    # Load data
    train_loader, val_loader, train_dataset, val_dataset = prepare_data(args.root_dir, args.sequence_length, args.batch_size)

    # Print and log data information
    print(f"Total training samples: {len(train_dataset)}")
    print(f"Total validation samples: {len(val_dataset)}")
    print(f"Total samples: {len(train_dataset) + len(val_dataset)}")
    print(f"Input shape: {train_dataset[0][0].shape}")
    print(f"Target shape: {train_dataset[0][1].shape}")
    print(f"Number of training batches: {len(train_loader)}")
    print(f"Number of validation batches: {len(val_loader)}")

    writer.add_text("Dataset Info", f"Train samples: {len(train_dataset)}, Val samples: {len(val_dataset)}")
    writer.add_text("Input Shape", str(train_dataset[0][0].shape))
    writer.add_text("Target Shape", str(train_dataset[0][1].shape))

    # Initialize the model, loss function, and optimizer
    model = IMULSTMModel(args.input_size, args.hidden_sizes, args.output_size)
    criterion = torch.nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)

    def mean_baseline_eval(loader, mean_position):
        total_loss = 0
        for _, targets in loader:
            batch_size = targets.size(0)
            mean_predictions = mean_position.repeat(batch_size, 1)
            loss = torch.nn.functional.mse_loss(mean_predictions, targets)
            total_loss += loss.item() * batch_size
        return total_loss / len(loader.dataset)

    # Calculate mean position from the training set
    all_targets = torch.cat([targets for _, targets in train_loader], dim=0)
    mean_position = all_targets.mean(dim=0)

    # Perform mean baseline evaluation
    print("Performing mean baseline evaluation...")
    baseline_train_loss = mean_baseline_eval(train_loader, mean_position)
    baseline_val_loss = mean_baseline_eval(val_loader, mean_position)
    print(f"Baseline Train Loss: {baseline_train_loss:.4f}, Baseline Val Loss: {baseline_val_loss:.4f}")

    # Log baseline loss as "Epoch 0"
    writer.add_scalar("Loss/Train", baseline_train_loss, 0)
    writer.add_scalar("Loss/Validation", baseline_val_loss, 0)

    # Training loop
    best_val_loss = float('inf')
    for epoch in range(args.num_epochs):
        model.train()
        train_loss = 0
        for batch_idx, (imu_seq, vi_target) in enumerate(train_loader):
            outputs = model(imu_seq)
            loss = criterion(outputs, vi_target)
            
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
        
        # Validation
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for imu_seq, vi_target in val_loader:
                outputs = model(imu_seq)
                val_loss += criterion(outputs, vi_target).item()
        
        train_loss /= len(train_loader)
        val_loss /= len(val_loader)
        
        print(f'Epoch [{epoch+1}/{args.num_epochs}], Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f}')
        
        # Log to TensorBoard
        writer.add_scalar("Loss/Train", train_loss, epoch + 1)
        writer.add_scalar("Loss/Validation", val_loss, epoch + 1)
        
        # Save the best model
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), args.model_save_path)
            writer.add_scalar("Best_Val_Loss", best_val_loss, epoch + 1)

    print("Training completed.")
    writer.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train LSTM model for IMU data")
    parser.add_argument("--root_dir", type=str, default="../../data/Oxford Inertial Odometry Dataset/handheld", help="Root directory of the dataset")
    parser.add_argument("--sequence_length", type=int, default=100, help="Sequence length for LSTM input")
    parser.add_argument("--input_size", type=int, default=15, help="Number of features in IMU data")
    parser.add_argument("--hidden_sizes", type=int, nargs='+', default=[64, 32], help="Hidden sizes of LSTM layers")
    parser.add_argument("--output_size", type=int, default=3, help="Output size (x, y, z)")
    parser.add_argument("--learning_rate", type=float, default=0.001, help="Learning rate")
    parser.add_argument("--batch_size", type=int, default=32, help="Batch size")
    parser.add_argument("--num_epochs", type=int, required=True, help="Number of epochs")
    parser.add_argument("--dropout_rate", type=float, default=0.5, help="Dropout rate")
    parser.add_argument("--model_save_path", type=str, default="../../model/best_imu_lstm_model.pth", help="Path to save the best model")
    parser.add_argument("--test_root_dir", type=str, default="../../data/Oxford Inertial Odometry Dataset/handheld_test", help="Root directory of the test dataset")

    args = parser.parse_args()
    train(args)
    print("\nStarting model evaluation...")

    sequence_length = args.sequence_length

    # Initialize the model
    model = IMULSTMModel(args.input_size, args.hidden_sizes, args.output_size, args.dropout_rate)
    # Load the trained model
    model.load_state_dict(torch.load(args.model_save_path))
    model.eval()
    test_loss, overall_mse, overall_mae = test_model(model, args.test_root_dir, args.sequence_length, args.output_size)

    # Log test results to TensorBoard
    test_writer.add_scalar("Test/Loss", test_loss, 0)
    test_writer.add_scalar("Test/MSE", overall_mse, 0)
    test_writer.add_scalar("Test/MAE", overall_mae, 0)

    # Add text summary of test results
    test_writer.add_text("Test Results", 
                         f"Test Loss: {test_loss:.4f}\n"
                         f"Overall MSE: {overall_mse:.4f}\n"
                         f"Overall MAE: {overall_mae:.4f}")

    print(f"Test results logged to TensorBoard in {test_log_dir}")

    test_writer.close()