import pandas as pd
import geopandas as gpd

# Replace 'your_file.parquet' with the path to your Parquet file
file_path = '/Users/thowe/MinersAI Dropbox/Tyler Howe/ICB_data/geospatial_data/ICB_mag_processed.parquet'

print(f'\nInspecting file: {file_path}\n')

# Load the Parquet file
df = pd.read_parquet(file_path) #can change to gpd.read for geoparquet files

# Display general information about the file
print("Dataframe Info:")
print(df.info())
print("\nSample Data:")
print(df.head())
print("\nColumns:")

