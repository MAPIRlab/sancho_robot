#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exporta PNGs desde un header tipo robotEye2.h:
- sclera.png (RGB565 -> RGB)
- iris_polar.png (RGB565 -> RGB)
- iris_cartesian_preview.png (reconstrucción rápida del iris en disco desde el mapa polar)
- eyelid_mask.png  (si hay máscara simétrica, 8 bits)
- eyelid_upper_mask.png / eyelid_lower_mask.png (si hay máscaras separadas, 8 bits)
- preview_composite.png (sclera + iris centrado, solo para ver rápido)
"""

import re
import os
import math
import argparse
from pathlib import Path
from PIL import Image

# ---------- Utilidades de parsing ----------

def read_text(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def parse_define(text, name, default=None):
    m = re.search(rf"#\s*define\s+{re.escape(name)}\s+(\d+)", text)
    return int(m.group(1)) if m else default

def extract_array(text, ctype, name):
    """
    Extrae valores de un array C:
    const <ctype> <name>[...] PROGMEM = { ... };
    PROGMEM opcional, admite comentarios, hex y decimales.
    Devuelve lista de enteros o None si no encuentra.
    """
    pattern = rf"const\s+{ctype}\s+{name}\s*\[[^\]]*\]\s*(?:PROGMEM)?\s*=\s*\{{(.*?)\}};"
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        return None
    body = m.group(1)
    # Quitar comentarios
    body = re.sub(r"//.*?$|/\*.*?\*/", "", body, flags=re.MULTILINE | re.DOTALL)
    # Tokens numéricos
    tokens = re.findall(r"0x[0-9A-Fa-f]+|\d+", body)
    vals = []
    for t in tokens:
        vals.append(int(t, 16) if t.lower().startswith("0x") else int(t))
    return vals

# ---------- Conversión de formatos ----------

def rgb565_to_rgb888(v):
    r = (v >> 11) & 0x1F
    g = (v >> 5) & 0x3F
    b = v & 0x1F
    r = (r * 255) // 31
    g = (g * 255) // 63
    b = (b * 255) // 31
    return (r, g, b)

def save_rgb565_as_png(vals, w, h, path):
    if not vals or len(vals) < w * h:
        return False
    px = [rgb565_to_rgb888(v) for v in vals[:w*h]]
    im = Image.new("RGB", (w, h))
    im.putdata(px)
    im.save(path)
    return True

def save_u8_as_png(vals, w, h, path):
    if not vals or len(vals) < w * h:
        return False
    im = Image.new("L", (w, h))
    im.putdata(vals[:w*h])
    im.save(path)
    return True

# ---------- Reconstrucciones / previews ----------

def polar_to_cartesian_preview(polar_img, iris_radius_px, out_path):
    """
    Reconstruye un disco del iris desde su mapa polar.
    polar_img: Image RGB donde X = ángulo [0..W-1], Y = radio [0..H-1]
    iris_radius_px: radio del iris en píxeles (IRIS_HEIGHT en tu header)
    """
    W, H = polar_img.size
    diam = 2 * iris_radius_px
    cart = Image.new("RGB", (diam, diam), (0, 0, 0))
    ppx = polar_img.load()

    # Centro subpixel para evitar bandas
    cx = cy = (diam - 1) / 2.0

    for y in range(diam):
        for x in range(diam):
            dx = x - cx
            dy = y - cy
            r = math.hypot(dx, dy)
            if r <= iris_radius_px - 0.5:
                theta = (math.degrees(math.atan2(dy, dx)) + 360.0) % 360.0
                px_x = int(theta / 360.0 * W) % W
                ry = int((r / max(iris_radius_px - 1e-6, 1.0)) * (H - 1))
                ry = max(0, min(H - 1, ry))
                cart.putpixel((x, y), ppx[px_x, ry])

    cart.save(out_path)
    return True

def composite_preview(sclera_path, iris_cart_path, out_path):
    scl = Image.open(sclera_path).convert("RGB")
    iris = Image.open(iris_cart_path).convert("RGBA")
    sw, sh = scl.size
    iw, ih = iris.size
    x = (sw - iw) // 2
    y = (sh - ih) // 2
    comp = scl.copy()
    comp.paste(iris, (x, y), iris)
    comp.save(out_path)
    return True

# ---------- Flujo principal ----------

def export_from_header(header_path, out_dir):
    text = read_text(header_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    generated = []

    # Dimensiones
    SCLERA_W = parse_define(text, "SCLERA_WIDTH", 336)
    SCLERA_H = parse_define(text, "SCLERA_HEIGHT", 336)
    SCREEN_W = parse_define(text, "SCREEN_WIDTH", 240)
    SCREEN_H = parse_define(text, "SCREEN_HEIGHT", 240)
    IRIS_MAP_W = parse_define(text, "IRIS_MAP_WIDTH", 360)
    IRIS_MAP_H = parse_define(text, "IRIS_MAP_HEIGHT", 90)
    IRIS_W = parse_define(text, "IRIS_WIDTH", 112)
    IRIS_H = parse_define(text, "IRIS_HEIGHT", 112)

    # 1) Sclera
    sclera_vals = extract_array(text, r"uint16_t", "sclera")
    if sclera_vals and save_rgb565_as_png(sclera_vals, SCLERA_W, SCLERA_H, out / "sclera.png"):
        generated.append("sclera.png")

    # 2) Iris polar
    iris_vals = extract_array(text, r"uint16_t", "iris")
    iris_polar_ok = False
    if iris_vals and save_rgb565_as_png(iris_vals, IRIS_MAP_W, IRIS_MAP_H, out / "iris_polar.png"):
        generated.append("iris_polar.png")
        iris_polar_ok = True

    # 2b) Iris cartesiano (preview)
    if iris_polar_ok:
        polar_img = Image.open(out / "iris_polar.png").convert("RGB")
        if polar_to_cartesian_preview(polar_img, IRIS_H, out / "iris_cartesian_preview.png"):
            generated.append("iris_cartesian_preview.png")

    # 3) Máscaras de párpados
    #    a) máscara simétrica
    eyelid_vals = extract_array(text, r"uint8_t", "eyelid")
    if eyelid_vals and save_u8_as_png(eyelid_vals, SCREEN_W, SCREEN_H, out / "eyelid_mask.png"):
        generated.append("eyelid_mask.png")
    else:
        #    b) superiores/inferiores
        upper_vals = extract_array(text, r"uint8_t", "upper")
        lower_vals = extract_array(text, r"uint8_t", "lower")
        if upper_vals and save_u8_as_png(upper_vals, SCREEN_W, SCREEN_H, out / "eyelid_upper_mask.png"):
            generated.append("eyelid_upper_mask.png")
        if lower_vals and save_u8_as_png(lower_vals, SCREEN_W, SCREEN_H, out / "eyelid_lower_mask.png"):
            generated.append("eyelid_lower_mask.png")

    # 4) Composite rápido (si hay sclera + iris preview)
    sclera_png = out / "sclera.png"
    iris_cart_png = out / "iris_cartesian_preview.png"
    if sclera_png.exists() and iris_cart_png.exists():
        if composite_preview(sclera_png, iris_cart_png, out / "preview_composite.png"):
            generated.append("preview_composite.png")

    print("Listo. Archivos generados en:", out.resolve())
    for g in generated:
        print(" -", g)

def main():
    ap = argparse.ArgumentParser(description="Exporta PNGs desde robotEye2.h")
    ap.add_argument("--input", "-i", required=True, help="Ruta al header (robotEye2.h)")
    ap.add_argument("--out", "-o", default="eye_export", help="Directorio de salida")
    args = ap.parse_args()

    export_from_header(args.input, args.out)

if __name__ == "__main__":
    main()
