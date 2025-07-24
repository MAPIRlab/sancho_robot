import React, { useState, useEffect } from "react";
import CommandButton from "../components/CommandButton";

export default function ControlPage() {
  const [speed, setSpeed] = useState(0.5);

  // Habilitar tooltips de Bootstrap
  useEffect(() => {
    // @ts-ignore
    const tooltipTriggerList = Array.from(
      document.querySelectorAll('[data-bs-toggle="tooltip"]')
    );
    // @ts-ignore
    tooltipTriggerList.forEach((el) => new window.bootstrap.Tooltip(el));
  }, []);

  const makeTwistMsg = (linearX = 0, angularZ = 0) => ({
    linear: { x: linearX, y: 0, z: 0 },
    angular: { x: 0, y: 0, z: angularZ }
  });

  return (
    <div className="container my-5">
      <div className="card shadow p-4 bg-white rounded">
        <h1 className="card-title mb-4 text-secundary">Interfaz de Control Remoto 📊</h1>

        {/* SECCIÓN: Control de Movimiento */}
        <div className="card mb-4">
          <div className="card-header">Control de Movimiento</div>
          <div className="card-body">
            {/* Deslizador de velocidad */}
            <div className="mb-3">
              <label htmlFor="speedRange" className="form-label">
                Velocidad: <strong>{speed.toFixed(1)}</strong>
              </label>
              <input
                type="range"
                id="speedRange"
                className="form-range"
                min={0}
                max={1}
                step={0.1}
                value={speed}
                onChange={(e) => setSpeed(parseFloat(e.target.value))}
                data-bs-toggle="tooltip"
                data-bs-placement="top"
                title="Ajusta la velocidad del robot"
              />
            </div>
            {/* Botones direccionales en formato D-pad */}
            <div className="d-flex justify-content-center">
              <div className="btn-group-vertical me-2">
                <CommandButton
                  topic="/cmd_vel"
                  label="↑ Adelante"
                  messageData={{ data: makeTwistMsg(speed, 0) }}
                  type="btn-outline-primary mb-2"
                  data-bs-toggle="tooltip"
                  data-bs-placement="left"
                  title="Mover hacia adelante"
                />
                <CommandButton
                  topic="/cmd_vel"
                  label="↓ Atrás"
                  messageData={{ data: makeTwistMsg(-speed, 0) }}
                  type="btn-outline-primary"
                  data-bs-toggle="tooltip"
                  data-bs-placement="left"
                  title="Mover hacia atrás"
                />
              </div>
              <div className="btn-group-vertical">
                <CommandButton
                  topic="/cmd_vel"
                  label="← Girar Izquierda"
                  messageData={{ data: makeTwistMsg(0, speed) }}
                  type="btn-outline-primary mb-2"
                  data-bs-toggle="tooltip"
                  data-bs-placement="top"
                  title="Girar a la izquierda"
                />
                <CommandButton
                  topic="/cmd_vel"
                  label="→ Girar Derecha"
                  messageData={{ data: makeTwistMsg(0, -speed) }}
                  type="btn-outline-primary"
                  data-bs-toggle="tooltip"
                  data-bs-placement="top"
                  title="Girar a la derecha"
                />
              </div>
            </div>
            {/* Botón Stop */}
            <div className="text-center mt-3">
              <CommandButton
                topic="/cmd_vel"
                label="¡STOP!"
                messageData={{ data: makeTwistMsg(0, 0) }}
                type="btn-danger"
                data-bs-toggle="tooltip"
                data-bs-placement="bottom"
                title="Parada de emergencia"
              />
            </div>
          </div>
        </div>

        {/* SECCIÓN: Funciones Adicionales */}
        <div className="card">
          <div className="card-header">Funciones Adicionales</div>
          <div className="card-body">
            <div className="row gy-3">
              <div className="col-md-4 d-grid">
                <CommandButton
                  topic="/lights_toggle"
                  label="Toggle Luces"
                  messageData={{ data: { toggle: true } }}
                  type="btn-outline-secondary"
                  data-bs-toggle="tooltip"
                  data-bs-placement="top"
                  title="Enciende o apaga las luces"
                  disabled={true}
                />
              </div>
              <div className="col-md-4 d-grid">
                <CommandButton
                  topic="/camera_snapshot"
                  label="Tomar Foto"
                  messageData={{ data: { capture: true } }}
                  type="btn-outline-secondary"
                  data-bs-toggle="tooltip"
                  data-bs-placement="top"
                  title="Captura imagen de la cámara"
                  disabled={true}
                />
              </div>
              <div className="col-md-4 d-grid">
                <CommandButton
                  topic="/test_cmd"
                  label="Enviar Test"
                  messageData={{ data: "¡Hola desde web!" }}
                  type="btn-outline-secondary"
                  data-bs-toggle="tooltip"
                  data-bs-placement="top"
                  title="Envía un comando de prueba"
                  disabled={true}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}