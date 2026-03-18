import { useState, useRef } from "react";

export const useMicrophone = () => {
    const [recording, setRecording] = useState(false);
    const [audioBlob, setAudioBlob] = useState(null);
    const mediaRecorderRef = useRef(null);
    const audioChunksRef = useRef([]);
    const streamRef = useRef(null);

    const startRecording = async () => {
        if (recording) return;

        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        streamRef.current = stream;

        const mediaRecorder = new MediaRecorder(stream);
        mediaRecorderRef.current = mediaRecorder;

        audioChunksRef.current = [];
        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunksRef.current.push(event.data);
            }
        };

        mediaRecorder.onstop = () => {
            const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
            setAudioBlob(audioBlob);

            streamRef.current?.getTracks().forEach((track) => track.stop());
            streamRef.current = null;
        };

        mediaRecorder.start();
        setRecording(true);
    };

    const stopRecording = () => {
        if (!recording || !mediaRecorderRef.current) return;
        mediaRecorderRef.current.stop();
        setRecording(false);
    };

    return {
        recording,
        audioBlob,
        startRecording,
        stopRecording,
    };
};
