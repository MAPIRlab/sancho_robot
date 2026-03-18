import React from "react";

import { useWebSocket } from "../../../contexts/WebSocketContext";
import { useChat } from "../../../contexts/ChatContext";

import ChatTextArea from "./ChatTextArea";
import MicrophoneButton from "./MicrophoneButton";

const ChatFullTextArea = ({ chatAreaRef }) => {
    const { isConnected } = useWebSocket();
    const { handleAudio, handleSend, openNCModal, openSettingsModal } = useChat();

    const handleUploadAudio = () => {
        if (!isConnected) return openNCModal();

        const input = Object.assign(document.createElement("input"), {
            type: "file",
            accept: "audio/*",
            onchange: async (e) => {
                const file = e.target.files?.[0];
                if (file) await handleAudio(file);
            },
        });

        input.click();
    };

    return (
        <div
            className="container d-flex flex-column pb-2 py-1 mb-4 shadow-sm border border-2 border-light-subtle"
            style={{ borderRadius: "24px", cursor: "text" }}
            onClick={() => chatAreaRef.current?.focus()}
        >
            <div className="input-group border-body-secondary mb-2">
                <ChatTextArea ref={chatAreaRef} onSend={handleSend} />
            </div>

            <div className="d-flex justify-content-end align-items-end pe-0 pb-0">
                <button className="btn btn-dark rounded-circle me-1" type="button" onClick={() => openSettingsModal()}>
                    <i className="bi bi-gear-fill"></i> {/* Que se abra un modal con settings */}
                    {/* Toggle tts. Toggle auto transcription. Toggle technical data. */}
                </button>

                <MicrophoneButton
                    onFinish={handleAudio}
                    recordCondition={isConnected}
                    noConditionAction={() => openNCModal()}
                />

                <button className="btn btn-dark rounded-circle me-1" type="button" onClick={() => handleUploadAudio()}>
                    <i className="bi bi-file-earmark-music-fill"></i>
                </button>

                <button
                    className="btn btn-dark rounded-circle"
                    type="button"
                    onClick={() => chatAreaRef.current?.send()}
                >
                    <i className="bi bi-send-fill"></i>
                </button>
            </div>
        </div>
    );
};

export default ChatFullTextArea;
