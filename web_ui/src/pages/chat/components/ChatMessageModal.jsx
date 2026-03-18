import React from "react";
import SimpleModal from "../../../components/SimpleModal";
import { emotionToIcon } from "./ChatMessage";

const ChatMessageModal = ({ isOpen, handleClose, message }) => {
    if (!isOpen || !message) return null;

    const isHuman = message.isHuman;

    const formatArgs = (args) =>
        Object.entries(args || {}).map(([key, value]) => (
            <div key={key} className="d-flex justify-content-start mb-1">
                <span className="text-muted fw-bold me-2">{key}:</span>
                <span>{String(value)}</span>
            </div>
        ));

    const renderSection = (title, content, col = 6) => (
        <div className={`col-md-${col}`}>
            <div className="card shadow-sm p-3 h-100" style={{ backgroundColor: "#f8f9fa" }}>
                <h6 className="text-secondary fw-bold mb-2">{title}</h6>
                {content}
            </div>
        </div>
    );

    const renderIntent = () =>
        renderSection(
            "Intención",
            <>
                <div>
                    <strong>{message.intent || "Sin intención detectada"}</strong>
                </div>
                {message.arguments && Object.keys(message.arguments).length > 0 && (
                    <div className="mt-1" style={{ lineHeight: "1rem" }}>
                        {formatArgs(message.arguments)}
                    </div>
                )}
            </>
        );

    const renderSTT = () => {
        const hasSTT = message.sttModel || (message.audio && message.sampleRate);
        return renderSection(
            "Reconocimiento de voz",
            hasSTT ? (
                <>
                    {message.sttModel && (
                        <div className="mb-2">
                            <strong>STT:</strong> {message.sttModel}
                        </div>
                    )}
                    {message.audio && message.sampleRate && (
                        <div>
                            <strong>Audio:</strong> {(message.audio.length / message.sampleRate).toFixed(2)}s
                        </div>
                    )}
                </>
            ) : (
                <span className="text-muted">No se ha hecho reconocimiento de voz</span>
            )
        );
    };

    const renderLLM = () => {
        const hasLLM = message.method || message.provider || message.model;
        return renderSection(
            "Generación de respuesta",
            hasLLM ? (
                <>
                    {message.method && (
                        <div className="mb-1">
                            <strong>Método:</strong> {message.method}
                        </div>
                    )}
                    {message.provider && (
                        <div className="mb-1">
                            <strong>Proveedor:</strong> {message.provider}
                        </div>
                    )}
                    {message.model && (
                        <div className="mb-1">
                            <strong>Modelo:</strong> {message.model}
                        </div>
                    )}
                    {message.value.emotion && (
                        <div>
                            <strong>Emoción:</strong>{" "}
                            <i className={"bi bi-" + emotionToIcon[message.value.emotion]}></i> ({message.value.emotion}
                            )
                        </div>
                    )}
                </>
            ) : (
                <span className="text-muted">No se ha generado respuesta</span>
            )
        );
    };

    const renderTTS = () => {
        const hasTTS = message.ttsModel || message.speaker || (message.audio && message.sampleRate);
        return renderSection(
            "Síntesis de voz",
            hasTTS ? (
                <>
                    {message.ttsModel && (
                        <div className="mb-2">
                            <strong>TTS:</strong> {message.ttsModel}
                        </div>
                    )}
                    {message.speaker && (
                        <div className="mb-2">
                            <strong>Voz:</strong> {message.speaker}
                        </div>
                    )}
                    {message.audio && message.sampleRate && (
                        <div>
                            <strong>Audio:</strong> {(message.audio.length / message.sampleRate).toFixed(2)}s
                        </div>
                    )}
                </>
            ) : (
                <span className="text-muted">No se ha hecho síntesis de voz</span>
            )
        );
    };

    const renderAttachments = () =>
        message.value?.data &&
        Object.keys(message.value.data).length > 0 &&
        renderSection(
            "Datos adjuntos",
            <div className="d-flex flex-wrap">
                {Object.keys(message.value.data).map((key) => (
                    <span key={key} className="badge bg-secondary">
                        {key.toUpperCase()}
                    </span>
                ))}
            </div>,
            12
        );

    return (
        <SimpleModal
            name="chat-message"
            title={`Interaccion ${message.id}`}
            handleClose={handleClose}
            isOpen={isOpen}
            size="lg"
            zIndex={105}
        >
            <div className="row g-3">
                {isHuman && (
                    <>
                        {renderIntent()}
                        {renderSTT()}
                    </>
                )}
                {!isHuman && (
                    <>
                        {renderLLM()}
                        {renderTTS()}
                    </>
                )}
                {renderAttachments()}
            </div>

            <div className="text-end text-muted small mt-3">
                Enviado por: <strong>{isHuman ? "Usuario" : "Sancho"}</strong> ·{" "}
                {new Date(message.timestamp).toLocaleString("es-ES", {
                    day: "2-digit",
                    month: "2-digit",
                    year: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                })}
            </div>
        </SimpleModal>
    );
};

export default ChatMessageModal;
