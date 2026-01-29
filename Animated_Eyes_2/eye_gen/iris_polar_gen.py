# Pipeline script:
# - Takes a 112x112 cartesian iris image (any format supported by matplotlib.image)
# - Unwraps it to a polar color texture (128x360) and saves PNG
# - Generates polar lookup (112x112, packed uint16) and saves as polar.h
# - Reconstructs the cartesian iris (112x112) sampling back from the polar color texture
# 
# Outputs (saved in /mnt/data):
#   - iris_polar_128x360.png
#   - polar.h
#   - iris_cartesian_reconstructed_112x112.png
#
# Demo: it will run once using the synthetic /mnt/data/iris_cartesian_112x112.png produced earlier.
#
# Notes:
# - If your input image isn't exactly 112x112, it will be resized with bilinear filtering.
# - The pipeline assumes the iris circle is centered and fits inside the 112x112 square.
# - You can change IRIS_MAP_WIDTH/HEIGHT if needed, but 128x360 is recommended.

import numpy as np
import math
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

IRIS_WIDTH, IRIS_HEIGHT = 112, 112          # cartesian iris size
IRIS_MAP_HEIGHT, IRIS_MAP_WIDTH = 128, 360  # polar color texture size

def load_cartesian_image(path, target_w=IRIS_WIDTH, target_h=IRIS_HEIGHT):
    img = mpimg.imread(path)
    # Convert to uint8 0..255 if needed
    if img.dtype == np.float32 or img.dtype == np.float64:
        img = np.clip(img * (255 if img.max() <= 1.0 else 1.0), 0, 255).astype(np.uint8)
    elif img.dtype != np.uint8:
        img = img.astype(np.uint8)

    # Remove alpha if present
    if img.ndim == 2:
        img = np.stack([img, img, img], axis=-1)
    if img.shape[-1] == 4:
        img = img[..., :3]

    h, w, _ = img.shape
    if (w, h) != (target_w, target_h):
        # Bilinear resize to 112x112
        img = bilinear_resize(img, target_w, target_h)
    return img

def bilinear_resize(img, new_w, new_h):
    h, w, c = img.shape
    x_ratio = (w - 1) / (new_w - 1) if new_w > 1 else 0
    y_ratio = (h - 1) / (new_h - 1) if new_h > 1 else 0
    out = np.zeros((new_h, new_w, c), dtype=np.uint8)
    for j in range(new_h):
        for i in range(new_w):
            x = x_ratio * i
            y = y_ratio * j
            x0, y0 = int(math.floor(x)), int(math.floor(y))
            x1, y1 = min(x0 + 1, w - 1), min(y0 + 1, h - 1)
            fx, fy = x - x0, y - y0
            c00 = img[y0, x0].astype(np.float32)
            c10 = img[y0, x1].astype(np.float32)
            c01 = img[y1, x0].astype(np.float32)
            c11 = img[y1, x1].astype(np.float32)
            c0 = c00 * (1 - fx) + c10 * fx
            c1 = c01 * (1 - fx) + c11 * fx
            c  = c0 * (1 - fy) + c1 * fy
            out[j, i] = np.clip(c + 0.5, 0, 255).astype(np.uint8)
    return out

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
            r01 = min(1.0, max(0.0, rad / radMax))
            rNorm = int(round(r01 * 127.0))

            if dx == 0 and dy_inv == 0:
                ang = 0.0
            else:
                ang = math.atan2(dy_inv, dx)  # [-pi,pi]
                if ang < 0: ang += 2.0 * math.pi

            thetaIdx = int(round(ang * 512.0 / (2.0*math.pi))) & 511
            polar_u16[iy, ix] = (thetaIdx << 7) | rNorm
    return polar_u16

def write_polar_header(polar_u16, path):
    h, w = polar_u16.shape
    with open(path, "w") as f:
        f.write("#pragma once\n#include <stdint.h>\n#include <pgmspace.h>\n\n")
        f.write(f"#define IRIS_WIDTH  {w}\n")
        f.write(f"#define IRIS_HEIGHT {h}\n\n")
        f.write(f"const uint16_t polar[{w*h}] PROGMEM = {{\n")
        flat = polar_u16.flatten()
        for i, val in enumerate(flat):
            f.write(f"0x{int(val):04X}")
            if i != len(flat)-1:
                f.write(", ")
            if (i+1) % 12 == 0:
                f.write("\n")
        f.write("\n};\n")

def unwrap_cartesian_to_polar(cart_img, H=IRIS_MAP_HEIGHT, W=IRIS_MAP_WIDTH):
    # cart_img is 112x112, centered circular iris
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
            y = cy - rad * math.sin(theta)  # invert Y
            # Bilinear sample from cart_img
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

def wrap_polar_to_cartesian(polar_tex, out_w=IRIS_WIDTH, out_h=IRIS_HEIGHT):
    # Reconstruct 112x112 cartesian from polar color texture (H=128, W=360)
    H, W, _ = polar_tex.shape
    cx, cy = (out_w-1)/2.0, (out_h-1)/2.0
    radMax = min(out_w, out_h)/2.0 - 0.5
    out = np.zeros((out_h, out_w, 3), dtype=np.uint8)
    for y in range(out_h):
        for x in range(out_w):
            dx, dy = x - cx, y - cy
            r = math.hypot(dx, dy)
            if r > radMax:
                out[y, x] = (0, 0, 0)
                continue
            r01 = r / radMax
            d = r01 * (H-1)

            theta = math.atan2(-(dy), dx)
            if theta < 0: theta += 2.0*math.pi
            a = theta / (2.0*math.pi) * (W-1)

            # Bilinear sample from polar_tex at (d,a)
            d0, a0 = int(math.floor(d)), int(math.floor(a))
            d1, a1 = min(d0 + 1, H - 1), min(a0 + 1, W - 1)
            fd, fa = d - d0, a - a0

            c00 = polar_tex[d0, a0].astype(np.float32)
            c10 = polar_tex[d1, a0].astype(np.float32)
            c01 = polar_tex[d0, a1].astype(np.float32)
            c11 = polar_tex[d1, a1].astype(np.float32)

            c0 = c00*(1-fd) + c10*fd
            c1 = c01*(1-fd) + c11*fd
            c  = c0*(1-fa) + c1*fa
            out[y, x] = np.clip(c + 0.5, 0, 255).astype(np.uint8)
    return out

def process(input_path):
    input_path = Path(input_path)

    #Create output directory in input file's parent
    out_dir = input_path.parent / "iris_out_data"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Load/resize to 112x112
    cart = load_cartesian_image(input_path)

    # 2) Build polar lookup and export header
    polar_u16 = build_polar_lookup(IRIS_WIDTH, IRIS_HEIGHT)
    header_path = out_dir / "polar.h"
    write_polar_header(polar_u16, header_path.as_posix())

    # 3) Unwrap to polar color texture (128x360)
    polar_tex = unwrap_cartesian_to_polar(cart, IRIS_MAP_HEIGHT, IRIS_MAP_WIDTH)
    polar_png = out_dir / "iris_polar_128x360.png"
    plt.imsave(polar_png.as_posix(), polar_tex)

    # 4) Reconstruct cartesian (112x112) from polar color texture
    cart_recon = wrap_polar_to_cartesian(polar_tex, IRIS_WIDTH, IRIS_HEIGHT)
    recon_png = out_dir / "iris_cartesian_reconstructed_112x112.png"
    plt.imsave(recon_png.as_posix(), cart_recon)

    # Also save a normalized input copy for reference
    norm_input_png = out_dir / "iris_cartesian_input_112x112.png"
    plt.imsave(norm_input_png.as_posix(), cart)

    return {
        "input_norm": norm_input_png.as_posix(),
        "polar_png": polar_png.as_posix(),
        "polar_header": header_path.as_posix(),
        "reconstructed_png": recon_png.as_posix()
    }

# Demo run using the synthetic iris we created earlier:
demo_input = "/home/mapir/sancho_robot/Animated_Eyes_2/normal_eye_files/iris2.png"  # this was created in a prior step
outputs = process(demo_input)
outputs
