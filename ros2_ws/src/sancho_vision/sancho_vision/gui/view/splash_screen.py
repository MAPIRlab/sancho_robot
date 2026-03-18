from PyQt6.QtWidgets import QSplashScreen, QApplication
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
import os

class SplashScreen(QSplashScreen):
    def __init__(self):
        splash_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "splash_logo.png")
        pixmap = QPixmap(splash_path)

        max_width = 500
        if pixmap.width() > max_width:
            pixmap = pixmap.scaledToWidth(max_width, Qt.TransformationMode.SmoothTransformation)

        super().__init__(pixmap)

        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)

        screen_geometry = QApplication.primaryScreen().geometry()
        splash_geometry = self.geometry()
        self.move(
            (screen_geometry.width() - splash_geometry.width()) // 2,
            (screen_geometry.height() - splash_geometry.height()) // 2
        )
