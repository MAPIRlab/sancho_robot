import base64

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QTimer


class PhotoScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.image_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.image_label)

    def update_content(self, photo_base64=None):
        if photo_base64:
            try:
                pixmap = QPixmap()
                pixmap.loadFromData(base64.b64decode(photo_base64))
                if not pixmap.isNull():
                    self.image_label.setPixmap(pixmap.scaled(
                        800, 600, Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    ))
            except Exception as e:
                print(f"Error updating content: {e}")