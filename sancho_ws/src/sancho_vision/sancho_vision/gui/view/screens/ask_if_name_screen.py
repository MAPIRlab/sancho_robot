import base64

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt


class AskIfNameScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.image_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.question_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.button_yes = QPushButton("Sí")
        self.button_no = QPushButton("No")
        self.button_cancel = QPushButton("Cancelar")
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.button_yes)
        button_layout.addWidget(self.button_no)
        button_layout.addWidget(self.button_cancel)

        self.layout.addWidget(self.image_label)
        self.layout.addWidget(self.question_label)
        self.layout.addLayout(button_layout)

    def update_content(self, photo_base64=None, name=""):
        if photo_base64:
            try:
                pixmap = QPixmap()
                pixmap.loadFromData(base64.b64decode(photo_base64))
                if not pixmap.isNull():
                    self.image_label.setPixmap(pixmap.scaled(
                        640, 480, Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    ))
            except Exception as e:
                print(f"Error updating content: {e}")
        self.question_label.setText(f"¿Eres {name}?")
