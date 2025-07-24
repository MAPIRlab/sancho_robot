// AppContent.jsx
import React, { useContext } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import { ToastContainer } from 'react-toastify';
import { RosContext } from './ros/RosContext';
import 'react-toastify/dist/ReactToastify.css';

import MainPage from './pages/MainPage'; 
import MapPage from './pages/MapPage';
import TelemetryPage from './pages/TelemetryPage';
import ControlPage from './pages/ControlPage';
import SettingsPage from './pages/SettingsPage';
import './chartConfig';

export default function App() {
  const { isConnected, connect, disconnect } = useContext(RosContext);

  return (
    <BrowserRouter>
      <nav className="navbar navbar-expand-lg navbar-dark bg-dark">
        <div className="container-fluid">
          <a class="navbar-brand" href="/">
      <img src="favicon.ico" alt="Logo" width="30" height="30" class="d-inline-block align-text-top"/>
    </a>
          <Link className="navbar-brand" to="/">Sancho Web</Link>
          <button
            className="navbar-toggler"
            type="button"
            data-bs-toggle="collapse"
            data-bs-target="#main-nav"
            aria-controls="main-nav"
            aria-expanded="false"
            aria-label="Toggle navigation"
          >
            <span className="navbar-toggler-icon"></span>
          </button>

          <div className="collapse navbar-collapse" id="main-nav">
            <ul className="navbar-nav me-auto mb-2 mb-lg-0">
              <li className="nav-item">
                <Link className="nav-link" to="/mapa">Mapa</Link>
              </li>
              <li className="nav-item">
                <Link className="nav-link" to="/telemetria">Telemetría</Link>
              </li>
              <li className="nav-item">
                <Link className="nav-link" to="/control">Control</Link>
              </li>
              <li className="nav-item">
                <Link className="nav-link" to="/ajustes">Ajustes</Link>
              </li>
            </ul>
            <div className="d-flex align-items-center">
              <span className="me-3 text-white">
                Estado: {isConnected ? '🟢 En línea' : '🔴 Desconectado'}
              </span>
              {isConnected ? (
                <button
                  className="btn btn-sm btn-danger"
                  onClick={disconnect}
                >
                  Desconectar
                </button>
              ) : (
                <button
                  className="btn btn-sm btn-success"
                  onClick={connect}
                >
                  Conectar
                </button>
              )}
            </div>
          </div>
        </div>
      </nav>

      <div className="container my-4">
        <Routes>
          <Route path="/" element={<MainPage isConnected={isConnected} />} />
          <Route path="/mapa" element={<MapPage />} />
          <Route path="/telemetria" element={<TelemetryPage />} />
          <Route path="/control" element={<ControlPage />} />
          <Route path="/ajustes" element={<SettingsPage />} />
          <Route path="*" element={<Navigate replace to="/" />} />
        </Routes>
      </div>

      <ToastContainer
        position="top-right"
        autoClose={5000}
        hideProgressBar={false}
        newestOnTop={false}
        closeOnClick
        pauseOnHover
      />
    </BrowserRouter>
  );
}
