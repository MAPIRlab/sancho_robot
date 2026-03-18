import React, { useEffect, useRef, useState } from "react";
import { useEventBus } from "../contexts/EventBusContext";
import { useWindowSize } from "../hooks/useWindowSize";

import DraggableItem from "./DraggableItem";

const WebSocketVideoViewer = () => {
    const { subscribe } = useEventBus();
    const { width } = useWindowSize();

    const [imgDimensions, setImgDimensions] = useState(null);
    const [showVideo, setShowVideo] = useState(false);
    const [imageData, setImageData] = useState(null);

    const timeoutRef = useRef(null);

    useEffect(() => {
        const handleImage = (base64) => {
            const img = new Image();
            img.src = `data:image/jpeg;base64,${base64}`;

            img.onload = () => {
                setImgDimensions({ width: img.width, height: img.height });
                setImageData(base64);
                setShowVideo(true);

                if (timeoutRef.current) clearTimeout(timeoutRef.current);
                timeoutRef.current = setTimeout(() => {
                    setShowVideo(false);
                }, 5000);
            };

            img.onerror = (err) => {
                console.error("Error al cargar imagen del WebSocket:", err);
            };
        };

        const unsubscribe = subscribe("ROS_TOPIC_IMAGE", handleImage);
        return () => {
            unsubscribe();
            clearTimeout(timeoutRef.current);
        };
    }, []);

    const calculatedWidth = Math.max(width * 0.2, 160);
    const calculatedHeight = imgDimensions && (calculatedWidth * imgDimensions.height) / imgDimensions.width;

    return (
        <>
            {showVideo && imgDimensions && imageData && (
                <DraggableItem childrenWidth={calculatedWidth} childrenHeight={calculatedHeight}>
                    <img
                        className="border border-dark bg-dark border-4 rounded shadow-lg"
                        src={`data:image/jpeg;base64,${imageData}`}
                        width={calculatedWidth}
                        height={calculatedHeight}
                        alt="WebSocket Video"
                    />
                </DraggableItem>
            )}
        </>
    );
};

export default WebSocketVideoViewer;
