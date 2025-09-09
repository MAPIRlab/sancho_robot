from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt

class NormalScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        label = QLabel("¡Hola! Soy Sancho.", alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(label)

    def update_content(self):
        pass
