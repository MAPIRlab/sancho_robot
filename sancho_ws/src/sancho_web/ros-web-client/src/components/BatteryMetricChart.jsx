import React, { useEffect, useState, useContext } from 'react';
import { Line } from 'react-chartjs-2';
import ROSLIB from 'roslib';
import { RosContext } from '../ros/RosContext';

export default function BatteryMetricChart({
  topic,
  label,
  valueExtractor,
  unit,
  color,
  updateIntervalMs = 1000, 
}) {
  const { ros } = useContext(RosContext);
  const [data, setData] = useState({
    labels: [],
    datasets: [{
      label: `${label}${unit ? ` (${unit})` : ''}`,
      data: [],
      borderColor: color || 'rgba(75,192,192,1)',
      backgroundColor: color ? `${color}33` : 'rgba(75,192,192,0.2)',
      tension: 0.4,
    }],
  });

  useEffect(() => {
    if (!ros) return;

    const listener = new ROSLIB.Topic({
      ros,
      name: topic,
      messageType: 'sensor_msgs/msg/BatteryState',
    });

    let lastUpdate = 0;

    listener.subscribe((msg) => {
      const now = Date.now();
      if (now - lastUpdate < updateIntervalMs) return; 
      lastUpdate = now;

      const value = valueExtractor(msg);
      const time = new Date().toLocaleTimeString();

      setData((prev) => {
        const newLabels = [...prev.labels, time].slice(-20);
        const newData = [...prev.datasets[0].data, value].slice(-20);
        return {
          labels: newLabels,
          datasets: [
            {
              ...prev.datasets[0],
              data: newData,
            },
          ],
        };
      });
    });

    return () => listener.unsubscribe();
  }, [ros, topic, label, unit, valueExtractor, color, updateIntervalMs]);

  return (
    <div className="border rounded shadow p-3 bg-white h-100">
      <Line data={data} options={{ responsive: true, maintainAspectRatio: false }} />
    </div>
  );
}
