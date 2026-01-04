import React, { useContext, useState } from "react";
import ROSLIB from "roslib";
import { RosContext } from "../ros/RosContext";

export default function NavGoalForm() {
  const { ros } = useContext(RosContext);
  const [pose, setPose] = useState({ x: 0, y: 0, theta: 0 });
  const [status, setStatus] = useState("");

  const handleChange = (e) => {
    const { name, value } = e.target;
    setPose((prev) => ({ ...prev, [name]: parseFloat(value) }));
  };

  const sendGoal = () => {
    if (!ros) return;
    const pub = new ROSLIB.Topic({ ros, name: "/goal_pose", messageType: "geometry_msgs/Pose" });
    pub.publish({
      position: { x: pose.x, y: pose.y, z: 0 },
      orientation: { x: 0, y: 0, z: Math.sin(pose.theta / 2), w: Math.cos(pose.theta / 2) }
    });
    setStatus("Objetivo publicado en /goal_pose");
  };

  return (
    <div className="card shadow-sm mb-4">
      <div className="card-body">
        <h5 className="card-title">Enviar Objetivo</h5>
        <form>
          <div className="mb-3">
            <label htmlFor="x" className="form-label">X</label>
            <input
              type="number" step="0.01" className="form-control" id="x" name="x" value={pose.x} onChange={handleChange} disabled={!ros}
            />
          </div>
          <div className="mb-3">
            <label htmlFor="y" className="form-label">Y</label>
            <input
              type="number" step="0.01" className="form-control" id="y" name="y" value={pose.y} onChange={handleChange} disabled={!ros}
            />
          </div>
          <div className="mb-3">
            <label htmlFor="theta" className="form-label">Theta</label>
            <input
              type="number" step="0.01" className="form-control" id="theta" name="theta" value={pose.theta} onChange={handleChange} disabled={!ros}
            />
          </div>
          <button type="button" className="btn btn-primary w-100" onClick={sendGoal} disabled={!ros}>
            Enviar
          </button>
        </form>
        {status && <p className="mt-3 text-success">{status}</p>}
      </div>
    </div>
  );
}

