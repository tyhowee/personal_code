import pandas as pd

# Replace 'your_file.parquet' with the path to your Parquet file
file_path = r"C:\Users\TyHow\MinersAI Dropbox\Tyler Howe\ICB_data\full_mines_cubes_2\set_1\(200, 200)\complete_df.parquet"

print(f'\nInspecting file: {file_path}\n')

# Load the Parquet file
df = pd.read_parquet(file_path)

# Display general information about the file
print("Dataframe Info:")
print(df.info())
print("\nSample Data:")
print(df.head())
print("\nColumns:")

