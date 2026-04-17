#!/usr/bin/env python3
import cv2
import numpy as np
import yaml
import sys
import os

def main():
    if len(sys.argv) != 4:
        print("Usage: python3 create_keepout.py <detailed_map.yaml> <constricted_map.yaml> <output_mask_name>")
        sys.exit(1)

    detailed_yaml = sys.argv[1]
    constricted_yaml = sys.argv[2]
    output_base = sys.argv[3]

    # Read YAML files
    with open(detailed_yaml, 'r') as f:
        det_info = yaml.safe_load(f)
    with open(constricted_yaml, 'r') as f:
        con_info = yaml.safe_load(f)

    # Resolve image paths relative to their yaml files
    base_dir = os.path.dirname(os.path.abspath(detailed_yaml))
    con_dir = os.path.dirname(os.path.abspath(constricted_yaml))
    
    det_img_path = os.path.join(base_dir, det_info['image'])
    con_img_path = os.path.join(con_dir, con_info['image'])

    # Load images in grayscale
    img_det = cv2.imread(det_img_path, cv2.IMREAD_GRAYSCALE)
    img_con = cv2.imread(con_img_path, cv2.IMREAD_GRAYSCALE)

    if img_det is None or img_con is None:
        print("Error loading images. Check the paths in the YAML files.")
        sys.exit(1)

    if img_det.shape != img_con.shape:
        print(f"Error: Map images must have the exact same dimensions.")
        print(f"Detailed: {img_det.shape}, Constricted: {img_con.shape}")
        sys.exit(1)

    # Initialize the mask to 255 (completely free space)
    mask = np.full(img_det.shape, 255, dtype=np.uint8)

    # Logic: Where constricted is occupied (< 128) AND detailed is free (> 200)
    # Set those pixels to 0 (Keepout zone)
    keepout_condition = (img_con < 128) & (img_det > 200)
    mask[keepout_condition] = 0

    # Save the new output image
    out_img_name = f"{output_base}.pgm"
    cv2.imwrite(os.path.join(base_dir, out_img_name), mask)

    # Copy the detailed map's yaml config, but point it to the new mask image
    mask_info = det_info.copy()
    mask_info['image'] = out_img_name
    
    out_yaml_path = os.path.join(base_dir, f"{output_base}.yaml")
    with open(out_yaml_path, 'w') as f:
        yaml.dump(mask_info, f)

    print(f"Success! Keepout mask created:")
    print(f" - Image: {os.path.join(base_dir, out_img_name)}")
    print(f" - YAML:  {out_yaml_path}")

if __name__ == '__main__':
    main()