import os
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from ..model.app_model import AppModel
from ..view.main_window import MainWindow
from ..view.splash_screen import SplashScreen


class AppController:
    def __init__(self, name_callback, question_callback):
        self.name_callback = name_callback
        self.question_callback = question_callback

        self.app = QApplication(sys.argv)
        self.model = AppModel()
        self.view = MainWindow()
        self.splash = SplashScreen()
        
        self.view.get_name_screen.send_button.clicked.connect(self.submit_name)
        self.view.ask_if_name_screen.button_yes.clicked.connect(lambda: self.submit_confirmation(True))
        self.view.ask_if_name_screen.button_no.clicked.connect(lambda: self.submit_confirmation(False))

        self.apply_styles()
    
    def start(self):
        self.start_splash()
        sys.exit(self.app.exec())

    def apply_styles(self):
        style_path = os.path.join(os.path.dirname(os.path.dirname(__file__),), "app_style.qss")
        with open(style_path, "r") as style_file:
            self.app.setStyleSheet(style_file.read())

    def start_splash(self):
        self.splash.show()
        QTimer.singleShot(2000, lambda: self.finish_splash())

    def finish_splash(self):
        self.splash.close()
        self.view.showMaximized()
        self.set_mode_normal()

    def is_priority_mode(self):
        return self.model.mode in ["get_name", "ask_if_name"]

    def set_mode_normal(self):
        self.model.mode = "normal"
        self.view.set_screen("normal")

    def set_mode_get_name(self, photo_base64):
        if self.is_priority_mode():
            print(f"Se ha intentado poner en modo ask name pero hay una pantalla prioritaria activa: {self.model.mode}")
            return False
        
        self.model.mode = "get_name"
        self.model.photo_base64 = photo_base64
        self.view.set_screen("get_name", photo_base64=photo_base64)
        
        return True

    def set_mode_ask_if_name(self, photo_base64, name):
        if self.is_priority_mode():
            print(f"Se ha intentado poner en modo ask IF name pero hay una pantalla prioritaria activa: {self.model.mode}")
            return False
        
        self.model.mode = "ask_if_name"
        self.model.photo_base64 = photo_base64
        self.model.ask_if_name_person = name
        self.view.set_screen("ask_if_name", photo_base64=photo_base64, name=name)

        return True

    def set_mode_show_photo(self, photo_base64):
        if self.is_priority_mode():
            print(f"Se ha intentado poner en modo show photo pero hay una pantalla prioritaria activa: {self.model.mode}")
            return False
        
        self.model.mode = "show_photo"
        self.model.photo_base64 = photo_base64
        self.view.set_screen("photo", photo_base64=photo_base64)

        return True

    def submit_name(self):
        if self.model.mode != "get_name":
            return
        name = self.view.get_name_screen.input_field.text().strip()
        if not name:
            self.view.get_name_screen.show_warning("El nombre no puede estar vacío.")
            return
        if len(name) > 20:
            self.view.get_name_screen.show_warning("El nombre es demasiado largo.")
            return

        print(f"[get_name] Nombre: {name}")
        self.name_callback(name)

        self.set_mode_normal()

    def submit_confirmation(self, answer: bool):
        if self.model.mode != "ask_if_name":
            return

        print(f"[ask_if_name] Respuesta del usuario: {'Sí' if answer else 'No'}")
        self.question_callback(answer)

        self.set_mode_normal()