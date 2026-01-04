import React, { useContext, useEffect, useState } from "react";
import ROSLIB from "roslib";
import { RosContext } from "../ros/RosContext";

export default function SettingsPage() {
  const { ros } = useContext(RosContext);
  const [url, setUrl] = useState(localStorage.getItem("rosbridge_url") || "ws://localhost:9090");
  const [topics, setTopics] = useState([]);
  const [services, setServices] = useState([]);
  const [actions, setActions] = useState([]);
  const [loading, setLoading] = useState(false);

  const [autoRefresh, setAutoRefresh] = useState(5);
  const [darkMode, setDarkMode] = useState(false);

  const client = new ROSLIB.Ros({ url });

  const fetchTopics = () => {
    if (!ros) return;
    setLoading(true);
    client.getTopics((res) => {
      setTopics(res?.topics || []);
      setLoading(false);
    });
  };

  const fetchServices = () => {
    if (!ros) return;
    setLoading(true);
    client.getServices((res) => {
      setServices(res?.services || []);
      setLoading(false);
    });
  };

  const fetchActions = () => {
    if (!ros) return;
    setLoading(true);

    const serviceClient = new ROSLIB.Service({
      ros: client,
      name: "/rosapi/get_action_servers",
      serviceType: "rosapi/GetActionServers",
    });

    const request = new ROSLIB.ServiceRequest({});

    serviceClient.callService(request, (res) => {
      setActions(res?.action_servers || []);
      setLoading(false);
    }, (err) => {
      console.error("Error al obtener acciones:", err);
      setLoading(false);
    });
  };

  const applyUrl = () => {
    localStorage.setItem("rosbridge_url", url);
    window.location.reload();
  };

  useEffect(() => {
    fetchTopics();
  }, [ros]);

  return (
    <div className="container my-5">
      <div className="card shadow p-4 bg-white rounded">
        <h1 className="card-title mb-4 text-secondary"> Ajustes y Topics 🛠️</h1>
        <div className="row gx-5 gy-4">
          {/* Columna de configuración */}
          <div className="col-md-6">
            <div className="mb-3">
              <label htmlFor="rosbridgeUrl" className="form-label">URL de Rosbridge</label>
              <input
                type="text"
                className="form-control"
                id="rosbridgeUrl"
                value={url}
                onChange={e => setUrl(e.target.value)}
              />
              <button
                className="btn btn-success mt-2"
                onClick={applyUrl}
              >
                Aplicar URL y recargar
              </button>
            </div>

            <div className="mb-3">
              <label htmlFor="autoRefresh" className="form-label">
                Intervalo Auto-Refresh <small className="text-muted">(s)</small>
              </label>
              <div className="input-group">
                <input
                  type="number"
                  id="autoRefresh"
                  className="form-control"
                  value={autoRefresh}
                  onChange={e => setAutoRefresh(parseInt(e.target.value, 10))}
                />
                <span className="input-group-text">seg</span>
              </div>
            </div>

            <div className="form-check form-switch mb-4">
              <input
                className="form-check-input"
                type="checkbox"
                id="darkMode"
                checked={darkMode}
                onChange={e => setDarkMode(e.target.checked)}
              disabled/>
              <label className="form-check-label" htmlFor="darkMode">
                Modo Oscuro
              </label>
            </div>

            <div className="d-grid gap-2">
              <button className="btn btn-primary" onClick={fetchTopics} disabled={loading}>
                {loading ? (
                  <><span className="spinner-border spinner-border-sm me-2"></span>Cargando Topics...</>
                ) : (
                  "Refrescar Topics"
                )}
              </button>
              <button className="btn btn-secondary" onClick={fetchServices} disabled>
                {loading ? "Cargando Servicios..." : "Listar Servicios"}
              </button>
              <button className="btn btn-secondary" onClick={fetchActions} disabled>
                {loading ? "Cargando Acciones..." : "Listar Acciones"}
              </button>
            </div>
          </div>

          {/* Columna de visualización */}
          <div className="col-md-6">
            <div className="p-3 bg-light rounded" style={{ maxHeight: '350px', overflowY: 'auto' }}>
              <h5 className="mb-3 text-primary">🔌 Topics</h5>
              {topics.length > 0 ? (
                <ul className="list-group list-group-flush">
                  {topics.map(topic => (
                    <li key={topic} className="list-group-item list-group-item-primary">
                      {topic}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-muted">No se encontraron topics.</p>
              )}
            </div>

            <div className="p-3 bg-light rounded mt-4" style={{ maxHeight: '200px', overflowY: 'auto' }}>
              <h5 className="mb-3 text-info">⚙️ Servicios</h5>
              {services.length > 0 ? (
                <ul className="list-group list-group-flush">
                  {services.map(service => (
                    <li key={service} className="list-group-item list-group-item-info">
                      {service}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-muted">No se encontraron servicios.</p>
              )}
            </div>

            <div className="p-3 bg-light rounded mt-4" style={{ maxHeight: '200px', overflowY: 'auto' }}>
              <h5 className="mb-3 text-warning">🤖 Acciones</h5>
              {actions.length > 0 ? (
                <ul className="list-group list-group-flush">
                  {actions.map(action => (
                    <li key={action} className="list-group-item list-group-item-warning">
                      {action}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-muted">No se encontraron acciones.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
