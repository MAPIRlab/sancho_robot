import os
import socket
import webbrowser
from flask import Flask, send_from_directory, abort
from werkzeug.serving import make_server


class HTTPServer:
    def __init__(self, host="0.0.0.0", port=8080, webclient_dir=None, open_on_start=False):
        self.host = host
        self.port = port

        self.webclient_dir = webclient_dir or self._find_client_dist()
        self.open_on_start = open_on_start

        self.app = Flask(__name__, static_folder=None) 
        self.app.add_url_rule('/', 'index', self.serve_html)
        self.app.add_url_rule('/<path:path>', 'static', self.serve_static)

        self.server = make_server(self.host, self.port, self.app)

    def _find_client_dist(self):
        env_path = os.environ.get("WEBCLIENT_DIST_PATH")
        if env_path and os.path.exists(env_path):
            return env_path

        current = os.path.abspath(__file__)
        candidates = [
            os.path.join(current, '../../../../../../../../web_interface/dist'),
            os.path.join(current, '../../../../../../../web_interface/dist'),
            os.path.join(current, '../../../../../../web_interface/dist'),
            os.path.join(current, '../../../../../web_interface/dist'),
            os.path.join(current, '../../../../web_interface/dist'),
            os.path.join(current, '../../../web_interface/dist'),
            os.path.join(current, '../../web_interface/dist'),
            os.path.join(os.path.dirname(current), '../../web_interface/dist'),
        ]
        for c in candidates:
            path = os.path.abspath(c)
            if os.path.exists(path):
                return path

        print("No se pudo encontrar el directorio 'web_interface/dist'.")

    def serve_html(self):
        index_path = os.path.join(self.webclient_dir, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(self.webclient_dir, 'index.html')
        else:
            abort(404, description="index.html no encontrado")

    def serve_static(self, path):
        full_path = os.path.join(self.webclient_dir, path)

        if os.path.exists(full_path) and os.path.isfile(full_path):
            return send_from_directory(self.webclient_dir, path)
        
        index_path = os.path.join(self.webclient_dir, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(self.webclient_dir, 'index.html')
        else:
            abort(404, description="index.html no encontrado")

    def get_local_ip(self):
        ip = "127.0.0.1"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        return ip

    def stop(self):
        if self.server:
            self.server.shutdown()

    def run(self):
        print(f"Sirviendo desde: {self.webclient_dir}")

        if self.open_on_start:
            webbrowser.open(f"http://localhost:{self.port}")
            
        self.server.serve_forever()
