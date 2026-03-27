import React from "react";
import SimpleModal from "../../../components/SimpleModal";

const ChatSettingsModal = ({ isOpen, handleClose, settings, toggleSetting }) => {
    return (
        <SimpleModal
            name="chat-settings"
            title="Ajustes del chat"
            handleClose={handleClose}
            isOpen={isOpen}
            zIndex={105}
        >
            <div className="d-flex flex-column gap-4">
                <div className="form-check form-switch">
                    <input
                        className="form-check-input"
                        type="checkbox"
                        id="showTechInfo"
                        checked={settings.showTechInfo}
                        onChange={() => toggleSetting("showTechInfo")}
                    />
                    <label className="form-check-label fw-semibold" htmlFor="showTechInfo">
                        Mostrar detalles técnicos
                    </label>
                    <div className="form-text">Muestra modelos usados entre otros datos internos.</div>
                </div>

                <div className="form-check form-switch">
                    <input
                        className="form-check-input"
                        type="checkbox"
                        id="enableTTS"
                        checked={settings.enableTTS}
                        onChange={() => toggleSetting("enableTTS")}
                    />
                    <label className="form-check-label fw-semibold" htmlFor="enableTTS">
                        Respuesta en audio
                    </label>
                    <div className="form-text">Sancho responderá también con voz (TTS).</div>
                </div>

                <div className="form-check form-switch">
                    <input
                        className="form-check-input"
                        type="checkbox"
                        id="autoSendTranscription"
                        checked={settings.autoSendTranscription}
                        onChange={() => toggleSetting("autoSendTranscription")}
                    />
                    <label className="form-check-label fw-semibold" htmlFor="autoSendTranscription">
                        Enviar audio directamente
                    </label>
                    <div className="form-text">Transcribe automáticamente sin mostrar el texto antes.</div>
                </div>
            </div>
        </SimpleModal>
    );
};

export default ChatSettingsModal;
