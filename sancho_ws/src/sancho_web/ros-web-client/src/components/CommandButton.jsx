import React, { useContext } from "react";
import ROSLIB from "roslib";
import { RosContext } from "../ros/RosContext";

export default function CommandButton({ topic, label, messageData, type, disabled }) {
  const { ros } = useContext(RosContext);
  const handleClick = () => {
    if (!ros) return;
    const cmdTopic = new ROSLIB.Topic({ ros, name: topic, messageType: "std_msgs/String" });
    cmdTopic.publish(messageData);
  };
  return (
    <button className={`btn ${type} w-100 shadow-sm`} onClick={handleClick} disabled={!ros || disabled}>
      {label}
    </button>
  );
}