import os
import exifread
import pandas as pd


def scan_metadata(directory):
    valid_extensions = {
        ".jpg",
        ".jpeg",
        ".tif",
        ".tiff",
        ".png",
        ".arw",
        ".nef",
        ".cr2",
    }  # Add more as needed
    data = []

    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            # Check file extension
            if not any(file.lower().endswith(ext) for ext in valid_extensions):
                print(f"Skipping non-image file: {file_path}")
                continue
            try:
                with open(file_path, "rb") as f:
                    tags = exifread.process_file(f)
                    data.append(
                        {
                            "File": file_path,
                            "ISO": tags.get("EXIF ISOSpeedRatings", "N/A"),
                            "FocalLength": tags.get("EXIF FocalLength", "N/A"),
                            "FNumber": tags.get("EXIF FNumber", "N/A"),
                            "ShutterSpeed": tags.get("EXIF ShutterSpeedValue", "N/A"),
                        }
                    )
                    print(f"Processed {file_path}")
            except Exception as e:
                print(f"Error reading {file_path}: {e}")

    return pd.DataFrame(data)


# Define the directory to scan and output file path
directory_to_scan = "/Volumes/NAS_Folder/NAS Photo-Video/Photo/Camera Import/Sony"
# test ---  directory_to_scan = "/Users/thowe/Library/Containers/jp.buffalo.NasNavigator2.AS/Data/Documents/NAS_Folder/NAS Photo-Video/Photo/Camera Import/Sony/2019-12-23"
output_csv_path = "/Users/thowe/Desktop/photo_metadata.csv"

# Run the metadata scan and save to CSV
result = scan_metadata(directory_to_scan)
result.to_csv(output_csv_path, index=False)
print("Metadata extraction complete. Results saved to photo_metadata.csv.")
