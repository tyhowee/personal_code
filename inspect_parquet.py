import pandas as pd

# Replace 'your_file.parquet' with the path to your Parquet file
file_path = '/Users/thowe/MinersAI Dropbox/Tyler Howe/ICB_data/cube_testing/08_zero_layers/(200, 200)/checker1_df.parquet'

# Load the Parquet file
df = pd.read_parquet(file_path)

# Display general information about the file
print("Dataframe Info:")
print(df.info())
print("\nSample Data:")
print(df.head())
print("\nColumns:")

print(f'GEOL DTYPE: {df['ICB_GEOL_dumbed_dumb_geol'].dtype}')
print(df.columns)