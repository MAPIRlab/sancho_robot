import React from 'react';
import BatteryMetricChart from '../components/BatteryMetricChart';

export default function TelemetryPage() {
  return (
    <div className="container my-5">
      <div className="card shadow p-4 bg-white rounded">
        <h1 className="card-title mb-4 text-secundary">Telemetria 📊</h1>
        <div className="row mt-4">
          <div className="col-md-6 mb-4">
            <BatteryMetricChart
              topic="/battery_state"
              label="Voltaje"
              unit="V"
              valueExtractor={(msg) => msg.voltage}
              color="rgba(255, 99, 132, 1)" // rojo
              updateIntervalMs={1000}


            />
          </div>
          <div className="col-md-6 mb-4">
            <BatteryMetricChart
              topic="/battery_state"
              label="Temperatura"
              unit="°C"
              valueExtractor={(msg) => msg.temperature}
              color="rgba(255, 159, 64, 1)" // naranja
              updateIntervalMs={10000}


            />
          </div>
          <div className="col-md-6 mb-4">
            <BatteryMetricChart
              topic="/battery_state"
              label="Corriente"
              unit="A"
              valueExtractor={(msg) => msg.current}
              color="rgba(54, 162, 235, 1)" // azul
              updateIntervalMs={1000}


            />
          </div>
          <div className="col-md-6 mb-4">
            <BatteryMetricChart
              topic="/battery_state"
              label="Carga"
              unit="%"
              valueExtractor={(msg) => msg.percentage}
              color="rgba(75, 192, 192, 1)" // verde agua
              updateIntervalMs={10000}


            />
          </div>
        </div>
      </div>
    </div>
  );
}
