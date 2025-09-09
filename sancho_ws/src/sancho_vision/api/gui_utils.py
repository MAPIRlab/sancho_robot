import os
import string
import random

import tkinter as tk
import cv2
import numpy as np
from PIL import Image, ImageTk, ImageFont, ImageDraw

def getClassifiedText(distance, classified=None, showDistance=None):
    return str(classified if classified is not None else "Desconocido") + ("" if not showDistance or distance is None or classified is None else ": " + str(round(100*distance, 2)) + "%")

def getClassifiedColor(distance, MIDDLE_BOUND, UPPER_BOUND):
    return (0, 255, 255) if distance is None or MIDDLE_BOUND <= distance <= UPPER_BOUND else (0, 255, 0) if distance > MIDDLE_BOUND else (0, 0, 255)

def getScoreColor(score):
    return (0, 255, 255) if score is None or 0.6 <= score <= 0.85 else (0, 0, 255) if score < 1 else (0, 255, 0)

def drawTexts(frame, position, distance, MIDDLE_BOUND, UPPER_BOUND, classified=None, score=None, wantedWidth=None, showDistance=False, showScore=False):
    text = getClassifiedText(distance, classified=classified, showDistance=showDistance)
    colorClassified = getClassifiedColor(distance, MIDDLE_BOUND, UPPER_BOUND)
    colorScore = getScoreColor(score)

    x, y, w, h = drawText(frame, text, position, colorClassified, wantedWidth=wantedWidth)
    if showScore and score is not None:
        drawText(frame, "Score: " + str(round(score, 5)), [position[0], position[1] + int(h*1.5)], colorScore, wantedWidth=wantedWidth)

def mark_face(frame, position, distance, MIDDLE_BOUND, UPPER_BOUND, classified=None, drawRectangle=True, score=None, showDistance=False, showScore=False, interlocutor=None, inter_time=0):
    x, y, w, h = position
    if drawRectangle:
        cv2.rectangle(frame, (x, y), (x + w, y + h), getClassifiedColor(distance, MIDDLE_BOUND, UPPER_BOUND), 2)
    drawTexts(frame, (x, y + h + 10), distance, MIDDLE_BOUND, UPPER_BOUND, classified=classified, 
              score=score, wantedWidth=w, showDistance=showDistance, showScore=showScore)
    if interlocutor is not None and classified is not None and interlocutor == classified:
        drawText(frame, "INTERLOCUTOR " + str(round(inter_time, 2)) + "s", (x-20, y), (0, 255, 255), wantedWidth=w+40)

def drawText(image, text, position, textColor, bgColor=(0,0,0), wantedWidth=None):
    font = cv2.FONT_HERSHEY_SIMPLEX
    textThickness = 2
    scale = 1

    (width, height), _ = cv2.getTextSize(text, font, scale, textThickness)
    if wantedWidth is not None:
        scale = wantedWidth / (width)
        textThickness = int(textThickness*scale)
        (width, height), _ = cv2.getTextSize(text, font, scale, textThickness)

    if bgColor is not None:
        backgroundPosition = (position[0], position[1] - int(height*1.2))
        backgroundSize = (width, int(height*1.4))
        cv2.rectangle(image, backgroundPosition, (backgroundPosition[0] + backgroundSize[0], backgroundPosition[1] + backgroundSize[1]), bgColor, cv2.FILLED)

    cv2.putText(image, text, position, font, scale, textColor, textThickness, cv2.LINE_AA)

    return position[0], position[1], width, height

def submit(root):
    root.event_generate('<Return>')

def ask_if_name(face, class_name, initial_value=None):
    if not os.environ.get("DISPLAY"):
        return True
    
    root = tk.Tk()
    root.title("Confirmar")

    if initial_value is not None:
        root.after(2500, lambda: submit(root))

    result = None

    def set_result(bool_value):
        nonlocal result
        result = bool_value
        print(">> USUARIO:", result)
        root.destroy()

    face_copy = cv2.resize(face, (512, 512))
    font_path = 'install/hri_vision/share/hri_vision/fonts/Benguiat Bold.ttf'
    font = ImageFont.truetype(font_path, 35)

    pil_image = Image.fromarray(face_copy)
    draw = ImageDraw.Draw(pil_image)
    
    text = "¿Eres " + str(class_name) + "?"

    # Crear un objeto ImageFont
    font = ImageFont.truetype(font_path, 35)

    # Calcular el tamaño del texto
    text_width = int(draw.textlength(text, font=font))
    text_height = 35

    # Calcular la posición para centrar el texto
    x = (512 - text_width) // 2
    y = (512 - text_height - 30)

    draw.text((x, y), text, font=font, fill=(0, 255, 255))

    image = np.asarray(pil_image)
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    image = Image.fromarray(image)
    photo = ImageTk.PhotoImage(image)

    label = tk.Label(root, image=photo)
    label.pack()

    # Crear un frame para alinear los botones horizontalmente
    button_frame = tk.Frame(root)
    button_frame.pack(pady=10)

    yes_button = tk.Button(button_frame, text="Sí", command=lambda: set_result(True))
    yes_button.pack(side=tk.LEFT, padx=10)

    no_button = tk.Button(button_frame, text="No", command=lambda: set_result(False))
    no_button.pack(side=tk.LEFT, padx=10)

    root.mainloop()
    
    if result is None:
        result = False

    return result

def submit_name(root):
    root.destroy()

def get_name(face, initial_value=None):
    if not os.environ.get("DISPLAY"):
        rnd_name = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        return rnd_name

    root = tk.Tk()
    root.title("Nombre")

    if initial_value is not None:
        root.after(2500, lambda: submit_name(root))

    nombre = None
    def get_input():
        nonlocal nombre
        nombre = nombre_entry.get()
        print(">> USUARIO:", nombre)
        root.destroy()

    face_copy = cv2.resize(face, (512, 512))
    font_path = 'install/hri_vision/share/hri_vision/fonts/Benguiat Bold.ttf'
    font = ImageFont.truetype(font_path, 35)

    pil_image = Image.fromarray(face_copy)
    draw = ImageDraw.Draw(pil_image)
    
    text = "¿Cual es tu nombre?"

    x = (face_copy.shape[1] - 430) // 2
    y = face_copy.shape[0] - 35 - 30

    draw.text((x, y), text, font=font, fill=(0, 255, 255))  # Amarillo

    image = np.asarray(pil_image)
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    image = Image.fromarray(image)
    photo = ImageTk.PhotoImage(image)

    label = tk.Label(root, image=photo)
    label.pack()

    nombre_entry = tk.Entry(root, width=30)
    nombre_entry.pack(pady=10)

    submit_button = tk.Button(root, text="Enviar", command=get_input)
    submit_button.pack()

    root.mainloop()

    if nombre == None or nombre.strip() == "":
        nombre = None

    return nombre
