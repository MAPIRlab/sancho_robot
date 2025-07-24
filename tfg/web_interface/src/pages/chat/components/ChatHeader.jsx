import React from "react";
import { useWindowSize, BREAKPOINTS } from "../../../hooks/useWindowSize";
import { useWebSocket } from "../../../contexts/WebSocketContext";
import { useModels } from "../../../contexts/ModelsContext";
import { useChat } from "../../../contexts/ChatContext";
import ModelBadge from "./ModelBadge";

const ChatHeader = ({ handleNewChat }) => {
    const { collapsed, setCollapsed, settings } = useChat();
    const { getActiveTtsModel, getActiveSttModel, getActiveLlmModel } = useModels();
    const { width } = useWindowSize();
    const { isConnected } = useWebSocket();

    const activeTtsModel = getActiveTtsModel();
    const activeSttModel = getActiveSttModel();
    const activeLlmModel = getActiveLlmModel();

    return (
        <div
            className="w-100 px-md-5 px-3 d-flex align-items-center justify-content-between"
            style={{ minHeight: "82px", height: "82px", borderBottom: "1px solid #EAEAEA" }}
        >
            <div className="d-flex align-items-center justify-content-between justify-content-md-start w-100">
                <button
                    className="btn btn-white me-3"
                    style={{ display: collapsed || width < BREAKPOINTS.MD ? "block" : "none" }}
                    onClick={() => setCollapsed((collapsed) => !collapsed)}
                >
                    <i className="bi bi-list"></i>
                </button>

                <div className="d-flex justify-content-center align-items-center">
                    <div className="d-flex flex-md-row flex-column justify-content-center align-items-center">
                        {/* Connected and Sancho text */}
                        <div className="d-flex align-items-center justify-content-center">
                            <div
                                className={`rounded-circle border border-dark ${
                                    isConnected == undefined ? "bg-primary" : isConnected ? "bg-success" : "bg-danger"
                                }`}
                                title={
                                    isConnected == undefined ? "Conectando" : isConnected ? "Conectado" : "Desconectado"
                                }
                                style={{
                                    cursor: "help",
                                    width: "16px",
                                    height: "16px",
                                    boxShadow: "0 0 5px rgba(0, 0, 0, 0.5)",
                                    transition: "background-color 0.3s ease",
                                }}
                            />
                            <span
                                className="fw-bold fs-2 ms-3 my-0 py-0"
                                style={{
                                    whiteSpace: "nowrap",
                                    display: collapsed || width < BREAKPOINTS.MD ? "block" : "none",
                                }}
                            >
                                Sancho
                            </span>
                        </div>

                        {/* Badges */}
                        {settings.showTechInfo && (
                            <div className="ms-md-3">
                                <ModelBadge model={activeTtsModel} type={"tts"} />
                                <ModelBadge model={activeSttModel} type={"stt"} />
                                <ModelBadge model={activeLlmModel} type={"llm"} />
                            </div>
                        )}
                    </div>
                </div>

                <button
                    className="btn btn-white text-start"
                    style={{ display: width < BREAKPOINTS.MD ? "block" : "none" }}
                    onClick={() => handleNewChat()}
                >
                    <i className="bi bi-chat-dots"></i>
                </button>
            </div>
        </div>
    );
};

export default ChatHeader;
