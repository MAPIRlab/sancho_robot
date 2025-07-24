import React from "react";
import { Link } from "react-router-dom";
import sancho from "../assets/sancho.jpg"; // Asegúrate de que la ruta sea correcta
import 'bootstrap/dist/css/bootstrap.min.css';

function MainPage({ isConnected }) {
  return (
    <div className="container my-5">
      <div className="card shadow-lg border-0">
        {/* Imagen del robot MAPIR */}
        <img
          src={sancho}
          className="card-img-top"
          alt="Sancho, robot MAPIR"
          style={{
            maxHeight: '400px',
            objectFit: 'cover',
            borderTopLeftRadius: '0.25rem',
            borderTopRightRadius: '0.25rem'
          }}
        />

        <div className="card-body text-center">
          {/* Cabecera */}
          <h1 className="display-4 mb-2">Panel de Control</h1>
          <p className="lead mb-4 text-secondary">
            Estado general del sistema y accesos rápidos
          </p>
          <span
            className={`badge fs-6 mb-3 ${
              isConnected ? "bg-success" : "bg-danger"
            }`}
          >
            {isConnected ? "Conectado a ROS" : "Desconectado de ROS"}
          </span>

          {/* Botones de navegación */}
          <div className="row g-4 justify-content-center mt-4">
            <div className="col-6 col-md-3">
              <Link to="/mapa" className="text-decoration-none">
                <button
                  className="btn btn-outline-primary w-100"
                  disabled={!isConnected}
                >
                  🗺️ Mapa
                </button>
              </Link>
            </div>
            <div className="col-6 col-md-3">
              <Link to="/telemetria" className="text-decoration-none">
                <button
                  className="btn btn-outline-success w-100"
                  disabled={!isConnected}
                >
                  📡 Telemetría
                </button>
              </Link>
            </div>
            <div className="col-6 col-md-3">
              <Link to="/control" className="text-decoration-none">
                <button
                  className="btn btn-outline-warning w-100"
                  disabled={!isConnected}
                >
                  🎮 Control
                </button>
              </Link>
            </div>
            <div className="col-6 col-md-3">
              <Link to="/ajustes" className="text-decoration-none">
                <button
                  className="btn btn-outline-secondary w-100"
                  disabled={!isConnected}
                >
                  ⚙️ Ajustes
                </button>
              </Link>
            </div>
          </div>

          {/* Alerta de conexión */}
          {!isConnected && (
            <div className="alert alert-warning mt-4" role="alert">
              ⚠️ Conéctate a ROS para acceder a las funciones del sistema.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default MainPage;
