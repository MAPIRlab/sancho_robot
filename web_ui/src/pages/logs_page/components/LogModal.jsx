import React from "react";
import SimpleModal from "../../../components/SimpleModal";

const LogModal = ({ log, onClose }) => {
    if (!log) return null;

    const formatTime = (ts) => {
        try {
            return new Date(Number(ts) * 1000).toLocaleString();
        } catch {
            return ts;
        }
    };

    const renderDetail = (label, value, options = {}) => (
        <div className={`col-${options.full ? "12" : "6"} mb-2`}>
            <strong>{label}:</strong>{" "}
            <span className={options.muted ? "text-muted" : ""}>{value || <em className="text-muted">—</em>}</span>
        </div>
    );

    return (
        <SimpleModal
            name="log-info"
            size="lg"
            title={`Log #${log.id}`}
            handleClose={onClose}
            isOpen={!!log}
            zIndex={100}
        >
            <div className="mb-3">
                <div className="card p-3 shadow-sm" style={{ backgroundColor: "#f8f9fa" }}>
                    <h5 className="mb-3 text-primary fw-bold">Información general</h5>
                    <div className="row">
                        {renderDetail("ID", log.id)}
                        {renderDetail("Fecha", formatTime(log.timestamp))}
                        {renderDetail("Nivel", log.level)}
                        {renderDetail("Origen", log.origin)}
                        {renderDetail("Actor", log.actor)}
                        {renderDetail("Acción", log.action)}
                        {renderDetail("Target", log.target)}
                        {renderDetail("Mensaje", log.message, { full: true })}
                    </div>
                </div>

                <div className="card p-3 shadow-sm mt-4" style={{ backgroundColor: "#f8f9fa" }}>
                    <h5 className="mb-3 text-primary fw-bold">Metadatos</h5>
                    <pre className="bg-white border rounded p-3 small mb-0">
                        {log.metadata || <em className="text-muted">(vacío)</em>}
                    </pre>
                </div>
            </div>
        </SimpleModal>
    );
};

export default LogModal;
