import xarray as xr
import matplotlib.pyplot as plt
import imageio
import os

#Specify file paths
file_path = r"C:\Users\TyHow\MinersAI Dropbox\Tyler Howe\ICB_data\with_faults\with_faults.nc"
gif_path = r"C:\Users\TyHow\MinersAI Dropbox\Tyler Howe\ICB_data\with_faults\with_faults.nc\output_gif.gif"

dataset = xr.open_dataset(file_path)

# Extract the necessary variables
layers = dataset["combined_layers"]
x_coords = dataset["x"]
y_coords = dataset["y"]

# Calculate the aspect ratio
x_range = x_coords.values.max() - x_coords.values.min()
y_range = y_coords.values.max() - y_coords.values.min()
aspect_ratio = x_range / y_range

# Create a temporary folder for images
os.makedirs("temp_gif_frames", exist_ok=True)

# Plot each layer and save frames
frames = []
for i in range(layers.shape[0]):
    plt.figure(figsize=(8, 8 / aspect_ratio))
    plt.imshow(layers[i, :, :], extent=[x_coords.min(), x_coords.max(), y_coords.min(), y_coords.max()], cmap="viridis", origin="lower")
    plt.title(f"Layer {i+1}: {layers.long_name if 'long_name' in layers.attrs else 'Unnamed Layer'}")
    plt.xlabel("X Coordinate")
    plt.ylabel("Y Coordinate")
    plt.colorbar(label="Value")
    plt.tight_layout()

    # Save the frame
    frame_path = f"temp_gif_frames/frame_{i:03d}.png"
    plt.savefig(frame_path)
    plt.close()
    frames.append(frame_path)

# Create the GIF
with imageio.get_writer(gif_path, mode="I", duration=0.5) as writer:
    for frame_path in frames:
        image = imageio.imread(frame_path)
        writer.append_data(image)

# Clean up temporary frames
for frame_path in frames:
    os.remove(frame_path)
os.rmdir("temp_gif_frames")

print(f"GIF saved as {gif_path}")
