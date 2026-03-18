import base64

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QLineEdit, QPushButton, QMessageBox
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt


class GetNameScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.image_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.title_label = QLabel("¿Cuál es tu nombre?", alignment=Qt.AlignmentFlag.AlignCenter)
        self.input_field = QLineEdit()
        self.send_button = QPushButton("Enviar")
        self.cancel_button = QPushButton("Cancelar")

        self.layout.addWidget(self.image_label)
        self.layout.addWidget(self.title_label)
        self.layout.addWidget(self.input_field)
        self.layout.addWidget(self.send_button)
        self.layout.addWidget(self.cancel_button)

    def update_content(self, photo_base64=None):
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
        self.input_field.clear()

    def show_warning(self, message: str):
        QMessageBox.warning(self, "Atención", message)
