import React, { useContext, useEffect, useState } from "react";
import ROSLIB from "roslib";
import { RosContext } from "../ros/RosContext";

export default function NavStatus() {
  const { ros } = useContext(RosContext);
  const [status, setStatus] = useState("Desconocido");

  useEffect(() => {
    if (!ros) return;
    const topic = new ROSLIB.Topic({ ros, name: "/nav_status", messageType: "std_msgs/String" });
    topic.subscribe((msg) => setStatus(msg.data));
    return () => topic.unsubscribe();
  }, [ros]);

  const variant =
    status.toLowerCase().includes("error")
      ? "danger"
      : status.toLowerCase().includes("aceptado")
      ? "primary"
      : status.toLowerCase().includes("activo")
      ? "success"
      : "secondary";

  return (
    <div className="card shadow-sm mb-4">
      <div className="card-body text-center">
        <h5 className="card-title">Estado de Navegación</h5>
        <span className={`badge bg-${variant} fs-5`}>{status}</span>
      </div>
    </div>
  );
}