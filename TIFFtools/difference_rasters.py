import rasterio
import numpy as np
from rasterio.enums import Resampling

def raster_difference(tiff_path1, tiff_path2, output_path):
    # Open the first TIFF file
    with rasterio.open(tiff_path1) as src1:
        data1 = src1.read(1)
        profile = src1.profile
    
    # Open the second TIFF file
    with rasterio.open(tiff_path2) as src2:
        data2 = src2.read(1, out_shape=data1.shape, resampling=Resampling.nearest)
    
    # Take the difference
    difference = data1 - data2

    # Print statistical summaries
    min_val = np.min(difference)
    max_val = np.max(difference)
    mean_val = np.mean(difference)
    std_dev = np.std(difference)
    range_val = max_val - min_val
    
    print(f"Difference Layer Statistics:")
    print(f"Min: {min_val}")
    print(f"Max: {max_val}")
    print(f"Mean: {mean_val}")
    print(f"Standard Deviation: {std_dev}")
    print(f"Range: {range_val}")

    # Update profile for output
    profile.update(dtype=rasterio.float32, count=1)

    # Write the result to a new TIFF file
    with rasterio.open(output_path, 'w', **profile) as dst:
        dst.write(difference.astype(rasterio.float32), 1)

raster_1 = r"C:\Users\TyHow\MinersAI Dropbox\Tyler Howe\ML_Pilot_Tyler_Data\1200px_full\full\full_avg.tif"
raster_2 = r"C:\Users\TyHow\MinersAI Dropbox\Tyler Howe\ML_Pilot_Tyler_Data\1200px_full\full_halved_targets\halved_targets_avg.tif"

output_raster = r"C:\Users\TyHow\MinersAI Dropbox\Tyler Howe\ML_Pilot_Tyler_Data\1200px_full\output_difference.tif"
# Example usage
raster_difference(
    raster_1, 
    raster_2, 
    output_raster)

print("Result output at", output_raster)
