#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera un header .h de ojo (tipo robotEye*.h) a partir de imágenes en un directorio.
- Convierte sclera (RGB) -> RGB565
- Convierte iris (si es polar ya) -> RGB565
- O bien, si das iris_cartesian (disco redondo) -> lo "desenrolla" a mapa polar (RGB565)
- Convierte máscaras de párpados (L/8-bit) -> uint8_t (simétrica o upper/lower)
No genera la tabla LUT `polar[]`; normalmente debes reutilizar la de tu proyecto.

USO:
  python make_eye_header.py \
    --in ./mis_imagenes \
    --out ./robotEye_custom.h \
    --screen 240 240 \
    --sclera 336 336 \
    --iris-map 360 90 \
    --iris-size 112 112 \
    [--iris-mode polar|cartesian] \
    [--names sclera.png iris_polar.png eyelid_mask.png eyelid_upper_mask.png eyelid_lower_mask.png]

Convenciones por defecto de nombres (dentro de --in):
  - sclera.png                 (RGB)            -> obligatorio
  - iris_polar.png             (RGB, polar)     -> opcional si usas --iris-mode polar
  - iris_cartesian.png         (RGB, disco)     -> opcional si usas --iris-mode cartesian
  - eyelid_mask.png            (L, simétrica)   -> opcional
  - eyelid_upper_mask.png      (L, superior)    -> opcional
  - eyelid_lower_mask.png      (L, inferior)    -> opcional

Requisitos: Pillow
"""
import argparse, sys, os, math, textwrap
from pathlib import Path
from PIL import Image

def to_rgb565_tuple(r,g,b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

def image_to_rgb565_list(img, size):
    im = img.convert("RGB").resize(size, Image.LANCZOS)
    pixels = list(im.getdata())
    return [to_rgb565_tuple(r,g,b) for (r,g,b) in pixels]

def image_to_u8_list(img, size):
    im = img.convert("L").resize(size, Image.LANCZOS)
    return list(im.getdata())

def write_c_array_uint16(f, name, w, h, data, add_progmem=True):
    f.write(f"#define {name.upper()}_WIDTH  {w}\n")
    f.write(f"#define {name.upper()}_HEIGHT {h}\n\n")
    prog = " PROGMEM" if add_progmem else ""
    f.write(f"const uint16_t {name}[{name.upper()}_HEIGHT * {name.upper()}_WIDTH]{prog} = {{\n")
    # 12 por línea
    for i, v in enumerate(data):
        if i % 12 == 0: f.write("  ")
        f.write(f"0x{v:04X}")
        if i != len(data)-1: f.write(", ")
        if (i+1) % 12 == 0: f.write("\n")
    if len(data) % 12 != 0: f.write("\n")
    f.write("};\n\n")

def write_c_array_uint8(f, name, w, h, data, add_progmem=True):
    prog = " PROGMEM" if add_progmem else ""
    f.write(f"const uint8_t {name}[{h} * {w}]{prog} = {{\n")
    for i, v in enumerate(data):
        if i % 24 == 0: f.write("  ")
        f.write(f"{v}")
        if i != len(data)-1: f.write(", ")
        if (i+1) % 24 == 0: f.write("\n")
    if len(data) % 24 != 0: f.write("\n")
    f.write("};\n\n")

def cartesian_to_polar_map(img_disc, iris_radius_px, map_w, map_h):
    """
    Convierte un iris circular (cartesiano, imagen cuadrada con disco) a mapa polar (ancho=ángulo, alto=radio).
    img_disc: Image RGB cuadrada que contiene el disco del iris centrado (se usará min(w,h)/2 como radio de entrada)
    iris_radius_px: radio del iris que deseas en pantalla (IRIS_HEIGHT). Se usa para escalar el radio origen.
    map_w, map_h: dimensiones del mapa polar de salida (e.g., 360x90)
    """
    src = img_disc.convert("RGB")
    sw, sh = src.size
    cx, cy = (sw-1)/2.0, (sh-1)/2.0
    r_max_src = min(sw, sh) * 0.5 - 1.0  # radio máximo disponible en la imagen fuente

    out = Image.new("RGB", (map_w, map_h))
    out_px = out.load()
    src_px = src.load()

    for v in range(map_h):
        # r_norm 0..1 desde centro a borde del iris
        r_norm = v / max(map_h-1, 1)
        # radio en la fuente mapeado proporcionalmente
        r_src = r_norm * r_max_src
        for u in range(map_w):
            theta = (u / map_w) * 2.0 * math.pi  # 0..2pi
            x = cx + r_src * math.cos(theta)
            y = cy + r_src * math.sin(theta)
            xi = int(round(x))
            yi = int(round(y))
            if 0 <= xi < sw and 0 <= yi < sh:
                out_px[u, v] = src_px[xi, yi]
            else:
                out_px[u, v] = (0, 0, 0)
    return out

def main():
    ap = argparse.ArgumentParser(description="Genera un .h para los ojos desde imágenes.")
    ap.add_argument("--in", dest="indir", required=True, help="Directorio con imágenes")
    ap.add_argument("--out", dest="outfile", required=True, help="Ruta del .h de salida")
    ap.add_argument("--screen", nargs=2, type=int, default=[240,240], help="SCREEN_WIDTH SCREEN_HEIGHT (por defecto 240 240)")
    ap.add_argument("--sclera", nargs=2, type=int, default=[336,336], help="SCLERA_WIDTH SCLERA_HEIGHT (por defecto 336 336)")
    ap.add_argument("--iris-map", nargs=2, type=int, default=[360,90], help="IRIS_MAP_WIDTH IRIS_MAP_HEIGHT (por defecto 360 90)")
    ap.add_argument("--iris-size", nargs=2, type=int, default=[112,112], help="IRIS_WIDTH IRIS_HEIGHT (por defecto 112 112)")
    ap.add_argument("--iris-mode", choices=["polar","cartesian"], default="polar", help="Origen del iris: 'polar' usa iris_polar.png; 'cartesian' usa iris_cartesian.png y lo convierte a polar.")
    ap.add_argument("--names", nargs=5, metavar=("SCLERA","IRIS","EYELID","UPPER","LOWER"),
                    default=["sclera.png","iris_polar.png","eyelid_mask.png","eyelid_upper_mask.png","eyelid_lower_mask.png"],
                    help="Nombres de archivos dentro del directorio de entrada (ver ayuda).")
    args = ap.parse_args()

    indir = Path(args.indir)
    if not indir.is_dir():
        print("ERROR: --in no es un directorio válido", file=sys.stderr)
        sys.exit(1)

    sclera_name, iris_name, eyelid_name, upper_name, lower_name = args.names
    sclera_path = indir / sclera_name

    if not sclera_path.exists():
        print(f"ERROR: Falta {sclera_name} en {indir}", file=sys.stderr)
        sys.exit(1)

    # Cargar imágenes
    sclera_img = Image.open(sclera_path)

    if args.iris_mode == "polar":
        iris_path = indir / iris_name
        if not iris_path.exists():
            print(f"ERROR: Modo polar seleccionado pero falta {iris_name}", file=sys.stderr)
            sys.exit(1)
        iris_img_polar = Image.open(iris_path)
    else:
        iris_cartesian_path = indir / "iris_cartesian.png"
        if not iris_cartesian_path.exists():
            print(f"ERROR: Modo cartesian seleccionado pero falta iris_cartesian.png", file=sys.stderr)
            sys.exit(1)
        iris_img_cart = Image.open(iris_cartesian_path)
        iris_img_polar = cartesian_to_polar_map(
            iris_img_cart,
            iris_radius_px=args.iris_size[1],
            map_w=args.iris_map[0],
            map_h=args.iris_map[1]
        )

    # máscaras (opcionales)
    eyelid_path = indir / eyelid_name
    upper_path  = indir / upper_name
    lower_path  = indir / lower_name

    # Crear salida
    out = Path(args.outfile)
    out.parent.mkdir(parents=True, exist_ok=True)

    SW, SH = args.screen
    SCLW, SCLH = args.sclera
    IMW, IMH = args.iris_map
    IW, IH = args.iris_size

    with open(out, "w", encoding="utf-8") as f:
        # Cabecera
        f.write("// AUTO-GENERATED by make_eye_header.py\n")
        f.write("// Ajusta dimensiones por CLI si lo necesitas.\n\n")
        f.write(f"#define SCREEN_WIDTH  {SW}\n")
        f.write(f"#define SCREEN_HEIGHT {SH}\n\n")

        # Sclera
        sclera_data = image_to_rgb565_list(sclera_img, (SCLW, SCLH))
        write_c_array_uint16(f, "sclera", SCLW, SCLH, sclera_data, add_progmem=True)

        # Iris MAP (polar)
        iris_data = image_to_rgb565_list(iris_img_polar, (IMW, IMH))
        f.write(f"#define IRIS_MAP_WIDTH  {IMW}\n")
        f.write(f"#define IRIS_MAP_HEIGHT {IMH}\n")
        f.write(f"#define IRIS_WIDTH  {IW}\n")
        f.write(f"#define IRIS_HEIGHT {IH}\n\n")
        write_c_array_uint16(f, "iris", IMW, IMH, iris_data, add_progmem=True)

        # Eyelids
        wrote_any_mask = False
        if eyelid_path.exists():
            eyelid_img = Image.open(eyelid_path)
            eyelid_data = image_to_u8_list(eyelid_img, (SW, SH))
            write_c_array_uint8(f, "eyelid", SW, SH, eyelid_data, add_progmem=True)
            f.write("// Define SYMMETRICAL_EYELID para usar esta máscara única.\n\n")
            wrote_any_mask = True

        if upper_path.exists():
            up_img = Image.open(upper_path)
            up_data = image_to_u8_list(up_img, (SW, SH))
            write_c_array_uint8(f, "upper", SW, SH, up_data, add_progmem=True)
            wrote_any_mask = True

        if lower_path.exists():
            lo_img = Image.open(lower_path)
            lo_data = image_to_u8_list(lo_img, (SW, SH))
            write_c_array_uint8(f, "lower", SW, SH, lo_data, add_progmem=True)
            wrote_any_mask = True

        if not wrote_any_mask:
            f.write("// (No se incluyeron máscaras de párpados; añade eyelid_mask o upper/lower si quieres)\n\n")

        # Nota sobre polar[]
        f.write(textwrap.dedent("""\
            // NOTA: Esta herramienta NO genera la LUT 'polar[]'. Normalmente se reutiliza la que ya tienes en tu proyecto.
            // Si quieres copiar 'polar[]' de otro header, pégala debajo de este comentario sin tocar los defines de arriba.
            // -----------------------------------------------------------------------
        """))

    print("OK. Header generado en:", out)

if __name__ == "__main__":
    main()
