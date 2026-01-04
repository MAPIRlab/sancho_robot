# Create a reusable Python script that:
# - Loads: sclera image (RGB), upper & lower eyelid maps (grayscale), iris cartesian (112x112 RGB)
# - Converts iris cartesian to polar color texture (128x360)
# - Builds polar lookup (112x112) packed as uint16
# - Exports a single .h file with all arrays in PROGMEM and the requested #defines
#
# Usage example (after downloading this file):
#   python make_eye_assets.py \
#       --sclera /path/to/sclera.png \
#       --upper /path/to/upper.png \
#       --lower /path/to/lower.png \
#       --iris  /path/to/iris_cartesian_112x112.png \
#       --out   /path/to/eye_assets.h
#
# Notes:
# - SCLERA will be resized to 336x336 (bilinear) and converted to RGB565.
# - UPPER/LOWER will be resized to 240x240, converted to 8-bit (0..255) without inversion.
# - IRIS input will be resized to 112x112 if needed (bilinear).
# - IRIS polar texture will be 128x360 (RGB565) per your requested parameters.
# - POLAR lookup will be 112x112 (uint16) with packing (thetaIdx<<7)|rNorm.
# - All arrays are emitted in hex, wrapped to 12 items per line.
#
# The script also writes the intermediate PNGs (polar texture, normalized iris) next to the header for debugging.

from pathlib import Path
import argparse
import numpy as np
import math
import matplotlib.image as mpimg

SCLERA_WIDTH, SCLERA_HEIGHT = 336, 336
SCREEN_WIDTH, SCREEN_HEIGHT = 240, 240
IRIS_WIDTH, IRIS_HEIGHT = 112, 112
IRIS_MAP_WIDTH, IRIS_MAP_HEIGHT = 360, 128

def load_image(path):
    img = mpimg.imread(path)
    if img.dtype == np.float32 or img.dtype == np.float64:
        if img.max() <= 1.0:
            img = (img * 255.0).clip(0,255).astype(np.uint8)
        else:
            img = img.clip(0,255).astype(np.uint8)
    elif img.dtype != np.uint8:
        img = img.astype(np.uint8)
    if img.ndim == 2:  # grayscale to RGB
        img = np.stack([img, img, img], axis=-1)
    if img.shape[-1] == 4:  # drop alpha
        img = img[..., :3]
    return img

def load_gray(path):
    img = mpimg.imread(path)
    if img.ndim == 3:
        # Convert RGB(A) to luma (Rec. 709)
        if img.shape[-1] == 4:
            img = img[..., :3]
        # If float
        if img.dtype == np.float32 or img.dtype == np.float64:
            if img.max() <= 1.0:
                img = img * 255.0
        # Linear luma
        r, g, b = img[...,0], img[...,1], img[...,2]
        gray = 0.2126*r + 0.7152*g + 0.0722*b
    else:
        gray = img.astype(np.float32)
        if gray.max() <= 1.0:
            gray *= 255.0
    gray = np.clip(gray, 0, 255).astype(np.uint8)
    return gray

def bilinear_resize(img, new_w, new_h):
    if img.ndim == 2:
        img = img[..., None]
    h, w, c = img.shape
    out = np.zeros((new_h, new_w, c), dtype=np.uint8)
    x_ratio = (w - 1) / (new_w - 1) if new_w > 1 else 0
    y_ratio = (h - 1) / (new_h - 1) if new_h > 1 else 0
    for j in range(new_h):
        for i in range(new_w):
            x = x_ratio * i
            y = y_ratio * j
            x0, y0 = int(x), int(y)
            x1, y1 = min(x0 + 1, w - 1), min(y0 + 1, h - 1)
            fx, fy = x - x0, y - y0

            c00 = img[y0, x0].astype(np.float32)
            c10 = img[y0, x1].astype(np.float32)
            c01 = img[y1, x0].astype(np.float32)
            c11 = img[y1, x1].astype(np.float32)

            c0 = c00*(1-fx) + c10*fx
            c1 = c01*(1-fx) + c11*fx
            c  = c0*(1-fy) + c1*fy
            out[j, i] = np.clip(c + 0.5, 0, 255).astype(np.uint8)
    if out.shape[-1] == 1:
        return out[...,0]
    return out

def rgb888_to_rgb565(img_rgb):
    # img_rgb: HxWx3 uint8
    r = (img_rgb[...,0].astype(np.uint16) & 0xF8) << 8
    g = (img_rgb[...,1].astype(np.uint16) & 0xFC) << 3
    b = (img_rgb[...,2].astype(np.uint16) >> 3)
    return (r | g | b).astype(np.uint16)

def unwrap_cartesian_to_polar(cart_img, H=IRIS_MAP_HEIGHT, W=IRIS_MAP_WIDTH):
    # cart_img: 112x112x3 RGB
    h, w, _ = cart_img.shape
    cx, cy = (w-1)/2.0, (h-1)/2.0
    radMax = min(w, h)/2.0 - 0.5
    polar_tex = np.zeros((H, W, 3), dtype=np.uint8)
    for d in range(H):
        r01 = d / (H-1)
        rad = r01 * radMax
        for a in range(W):
            theta = 2.0 * math.pi * (a / W)
            x = cx + rad * math.cos(theta)
            y = cy - rad * math.sin(theta)  # invert Y axis
            x0, y0 = int(math.floor(x)), int(math.floor(y))
            x1, y1 = min(x0 + 1, w - 1), min(y0 + 1, h - 1)
            fx, fy = x - x0, y - y0

            def clamp(v, lo, hi): return lo if v < lo else (hi if v > hi else v)
            x0c = clamp(x0, 0, w-1); x1c = clamp(x1, 0, w-1)
            y0c = clamp(y0, 0, h-1); y1c = clamp(y1, 0, h-1)

            c00 = cart_img[y0c, x0c].astype(np.float32)
            c10 = cart_img[y0c, x1c].astype(np.float32)
            c01 = cart_img[y1c, x0c].astype(np.float32)
            c11 = cart_img[y1c, x1c].astype(np.float32)

            c0 = c00*(1-fx) + c10*fx
            c1 = c01*(1-fx) + c11*fx
            c  = c0*(1-fy) + c1*fy
            polar_tex[d, a] = np.clip(c + 0.5, 0, 255).astype(np.uint8)
    return polar_tex

def build_polar_lookup(w=IRIS_WIDTH, h=IRIS_HEIGHT):
    cx, cy = (w-1)/2.0, (h-1)/2.0
    radMax = min(w, h)/2.0 - 0.5
    polar_u16 = np.zeros((h, w), dtype=np.uint16)
    for iy in range(h):
        for ix in range(w):
            dx = ix - cx
            dy = iy - cy
            dy_inv = -dy
            rad = math.hypot(dx, dy)
            if rad > radMax + 1e-6:
                rNorm = 127          # ← fuera del disco (sentinela)
            else:
                r01 = rad / radMax   # 0..1
                rNorm = min(126, int(round(r01 * 126.0)))  # 0..126 solo dentro

            if dx == 0 and dy_inv == 0:
                ang = 0.0
            else:
                ang = math.atan2(dy_inv, dx)
                if ang < 0: ang += 2.0 * math.pi
            thetaIdx = int(round(ang * 512.0 / (2.0*math.pi))) & 511
            polar_u16[iy, ix] = (thetaIdx << 7) | rNorm
    return polar_u16

def write_array_hex_u16(f, name, arr):
    flat = arr.flatten().astype(np.uint16)
    f.write(f"const uint16_t {name}[{len(flat)}] PROGMEM = {{\n")
    for i, v in enumerate(flat):
        f.write(f"0x{int(v):04X}")
        if i != len(flat)-1:
            f.write(", ")
        if (i+1) % 12 == 0:
            f.write("\n")
    f.write("\n};\n\n")

def write_array_hex_u8(f, name, arr):
    flat = arr.flatten().astype(np.uint8)
    f.write(f"const uint8_t {name}[{len(flat)}] PROGMEM = {{\n")
    for i, v in enumerate(flat):
        f.write(f"0x{int(v):02X}")
        if i != len(flat)-1:
            f.write(", ")
        if (i+1) % 24 == 0:
            f.write("\n")
    f.write("\n};\n\n")

def main(args):
    sclera_img = load_image(args.sclera)
    upper_img  = load_gray(args.upper)
    lower_img  = load_gray(args.lower)
    iris_img   = load_image(args.iris)

    # Resize to target sizes
    sclera_img = bilinear_resize(sclera_img, SCLERA_WIDTH, SCLERA_HEIGHT)
    upper_img  = bilinear_resize(upper_img,  SCREEN_WIDTH, SCREEN_HEIGHT)
    lower_img  = bilinear_resize(lower_img,  SCREEN_WIDTH, SCREEN_HEIGHT)
    iris_img   = bilinear_resize(iris_img,   IRIS_WIDTH, IRIS_HEIGHT)

    # Convert RGB to RGB565
    sclera_565 = rgb888_to_rgb565(sclera_img)
    # Unwrap iris to polar texture (RGB888 -> RGB565)
    iris_polar_rgb = unwrap_cartesian_to_polar(iris_img, IRIS_MAP_HEIGHT, IRIS_MAP_WIDTH)
    iris_polar_565 = rgb888_to_rgb565(iris_polar_rgb)

    # Build polar lookup
    polar_lookup = build_polar_lookup(IRIS_WIDTH, IRIS_HEIGHT)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Write header
    with open(out_path, "w") as f:
        f.write("#pragma once\n#include <stdint.h>\n#include <pgmspace.h>\n\n")
        # Defines
        f.write(f"#define SCLERA_WIDTH  {SCLERA_WIDTH}\n")
        f.write(f"#define SCLERA_HEIGHT {SCLERA_HEIGHT}\n\n")
        write_array_hex_u16(f, "sclera", sclera_565)

        f.write(f"#define IRIS_MAP_WIDTH  {IRIS_MAP_WIDTH}\n")
        f.write(f"#define IRIS_MAP_HEIGHT {IRIS_MAP_HEIGHT}\n\n")
        write_array_hex_u16(f, "iris", iris_polar_565)

        f.write(f"#define SCREEN_WIDTH  {SCREEN_WIDTH}\n")
        f.write(f"#define SCREEN_HEIGHT {SCREEN_HEIGHT}\n\n")
        write_array_hex_u8(f, "upper", upper_img)
        write_array_hex_u8(f, "lower", lower_img)

        f.write(f"#define IRIS_WIDTH  {IRIS_WIDTH}\n")
        f.write(f"#define IRIS_HEIGHT {IRIS_HEIGHT}\n")
        write_array_hex_u16(f, "polar", polar_lookup)

    # Save intermediates next to header for inspection
    mpimg.imsave((out_path.parent / "iris_polar_128x360.png").as_posix(), iris_polar_rgb)
    mpimg.imsave((out_path.parent / "iris_cartesian_112x112_norm.png").as_posix(), iris_img)
    mpimg.imsave((out_path.parent / "sclera_336x336_preview.png").as_posix(), sclera_img)
    mpimg.imsave((out_path.parent / "upper_240x240_preview.png").as_posix(), upper_img, cmap="gray")
    mpimg.imsave((out_path.parent / "lower_240x240_preview.png").as_posix(), lower_img, cmap="gray")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build eye assets header from images.")
    parser.add_argument("--sclera", required=True, help="Path to sclera image")
    parser.add_argument("--upper",  required=True, help="Path to upper eyelid mask image (grayscale)")
    parser.add_argument("--lower",  required=True, help="Path to lower eyelid mask image (grayscale)")
    parser.add_argument("--iris",   required=True, help="Path to cartesian iris image (112x112 RGB preferred)")
    parser.add_argument("--out",    required=True, help="Output header path, e.g., eye_assets.h")
    args = parser.parse_args()
    main(args)
