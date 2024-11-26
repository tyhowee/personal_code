import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

# Define input and output files
csv_file = '/Users/thowe/MinersAI Dropbox/Tyler Howe/ICB_data/geospatial_data/USA_Idaho_Cobalt_Belt_Mag.csv'
output_file = '/Users/thowe/MinersAI Dropbox/Tyler Howe/ICB_data/geospatial_data/ICB_mag_processed.parquet'  # Change to .geojson if needed

print(f'Input file selected: {csv_file}')

# Define columns to keep
columns_of_interest = ["LAT", "LONG", "MAGMLEV", "AMF"]

print(f"\nSelected columns: {columns_of_interest}\nProcessing file......")

# Step 1: Load CSV and filter columns
data = pd.read_csv(csv_file, usecols=columns_of_interest)

# Step 2: Create geometry column
data["geometry"] = data.apply(lambda row: Point(row["LONG"], row["LAT"]), axis=1)

# Step 3: Convert to GeoDataFrame
gdf = gpd.GeoDataFrame(data, geometry="geometry", crs="EPSG:4326")  # WGS84

# Step 4: Save to GeoParquet or GeoJSON
gdf.to_parquet(output_file)  # For GeoParquet
#gdf.to_file(output_file, driver="GeoJSON")  # Uncomment for GeoJSON - filesize MUCH larger!!

print(f'File successfully exported at {output_file}')