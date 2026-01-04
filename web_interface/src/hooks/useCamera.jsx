import { useRef, useState, useEffect } from "react";
import { useToast } from "../contexts/ToastContext";

export const useCamera = () => {
    const { showToast } = useToast();

    const [isActive, setIsActive] = useState(false);

    const videoRef = useRef(null);
    const streamRef = useRef(null);

    const startCamera = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true });
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
                streamRef.current = stream;
                setIsActive(true);
            }
        } catch (error) {
            showToast("Error", "No se pudo acceder a la cámara", "red");
        }
    };

    const stopCamera = () => {
        if (streamRef.current) {
            streamRef.current.getTracks().forEach((track) => track.stop());
            streamRef.current = null;
        }
        setIsActive(false);
    };

    const takePhoto = () => {
        if (!videoRef.current) return null;
        const video = videoRef.current;
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        return new Promise((resolve) => {
            canvas.toBlob((blob) => {
                if (blob) {
                    const file = new File([blob], "captured_photo.jpg", { type: "image/jpeg" });
                    resolve(file);
                } else {
                    resolve(null);
                }
            }, "image/jpeg");
        });
    };

    useEffect(() => {
        return () => stopCamera();
    }, []);

    return { videoRef, isActive, startCamera, stopCamera, takePhoto };
};
