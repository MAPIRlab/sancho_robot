import React, { useEffect, useContext, createContext, useRef, useState } from "react";
import R2WSocket from "../utils/R2WSocket";

import { useEventBus } from "./EventBusContext";
import { useToast } from "./ToastContext";

const WebSocketContext = createContext();

export const MESSAGE_TYPE = {
    RESPONSE: "RESPONSE",
    FACEPRINT_EVENT: "FACEPRINT_EVENT",
    PROMPT_TRANSCRIPTION: "PROMPT_TRANSCRIPTION",
    AUDIO_RESPONSE: "AUDIO_RESPONSE",
};

export const FACEPRINT_EVENT = {
    CREATE: "CREATE",
    UPDATE: "UPDATE",
    DELETE: "DELETE",
};

export const WebSocketProvider = ({ children }) => {
    const { publish } = useEventBus();
    const { showToast } = useToast();

    const [isConnected, setConnected] = useState(undefined);

    const socketRef = useRef(null);

    useEffect(() => {
        const connectWebSocket = () => {
            const serverIP = window.location.hostname;
            const ws = new R2WSocket("ws://" + serverIP + ":8765"); // Intentar meter en el R2WSocket el retry tmb por defecto
            console.log("Intentando conectar con el servidor WebSocket:", "ws://" + serverIP + ":8765");
            showToast("Intentando conectar", "Intentando establecer conexión con ROS", "blue");

            ws.onopen = () => {
                console.log("Conexión establecida con el servidor WebSocket");
                showToast("Conectado", "Conexión establecida con ROS", "green");

                setConnected(true);
                socketRef.current = ws;
            };

            ws.onclose = () => {
                console.log("Conexión cerrada, intentando reconectar...");
                showToast("No conectado", "Iniciando nuevo intento de conexión...", "red");

                setConnected(false);
                setTimeout(connectWebSocket, 3000); // Intenta reconectar después de 3 segundos
            };

            ws.onerror = (error) => {
                console.log("R2WSocket error:", error);
                setConnected(false);
                ws.close();
            };

            ws.ontopic = (event) => onTopic(event);
            ws.onmessage = (event) => onMessage(event);
        };

        if (!socketRef.current) connectWebSocket();

        return () => {
            if (socketRef.current) {
                console.log("Closing socket...");

                setConnected(false);
                socketRef.current.close();
            }
        };
    }, []);

    const onTopic = (event) => {
        publish(`ROS_TOPIC_${event.name}`, event.value);
    };

    const onMessage = (event) => {
        if (event.type in MESSAGE_TYPE) {
            publish(`ROS_MESSAGE_${event.type}`, event.data);
        } else {
            console.log("Tipo de mensaje desconocido:", event.type, event.data);
            showToast(
                "Mensaje no reconocido",
                "Se ha recibido un mensaje con tipo " + event.type + ", no reconocido",
                "red"
            );
        }
    };

    const sendMessage = (message, show = true) => {
        if (socketRef.current) return socketRef.current.send(message);
        else if (show) {
            console.log("No conectado al R2WSocket");
            showToast("Sin conexión", "No estás conectado a ROS", "red");
            return false;
        }
    };

    return (
        <WebSocketContext.Provider
            value={{
                isConnected,
                sendMessage,
            }}
        >
            {children}
        </WebSocketContext.Provider>
    );
};

export const useWebSocket = () => useContext(WebSocketContext);
