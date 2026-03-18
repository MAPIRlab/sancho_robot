import React, { useEffect } from "react";
import { useMicrophone } from "../../../hooks/useMicrophone";

const MicrophoneButton = ({ onFinish, recordCondition, noConditionAction }) => {
    const { recording, audioBlob, startRecording, stopRecording } = useMicrophone();

    const toggleRecording = () => {
        if (!recordCondition) noConditionAction();
        else {
            if (recording) stopRecording();
            else startRecording();
        }
    };

    useEffect(() => {
        if (audioBlob && onFinish) {
            onFinish(audioBlob);
        }
    }, [audioBlob]);

    return (
        <button className={`btn btn-${recording ? "danger" : "dark"} rounded-circle me-1`} onClick={toggleRecording}>
            <i className="bi bi-mic-fill" />
        </button>
    );
};

export default MicrophoneButton;
