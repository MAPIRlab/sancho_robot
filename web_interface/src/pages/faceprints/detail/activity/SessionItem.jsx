import React from "react";

const SessionItem = ({ session, onClick }) => {
    const formatDateTime = (timestamp) => {
        const date = new Date(timestamp * 1000);
        return (
            date.toLocaleDateString() +
            " " +
            date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
        );
    };

    const formatDuration = (start, end) => {
        const seconds = (end - start).toFixed(0);
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        const hours = Math.floor(minutes / 60);
        const remainingMinutes = minutes % 60;

        if (hours > 0) return `${hours}h ${remainingMinutes}min ${remainingSeconds}s`;
        if (minutes > 0) return `${minutes}min ${remainingSeconds}s`;
        return `${seconds}s`;
    };

    return (
        <div className="card shadow-sm p-3 mb-2 clickable clickable-05" onClick={onClick}>
            <div className="d-flex flex-column flex-md-row justify-content-between align-items-md-center">
                <div className="text-muted small">
                    <div>
                        <strong>Inicio:</strong> {formatDateTime(session.start_time)}
                    </div>
                    <div>
                        <strong>Fin:</strong> {formatDateTime(session.end_time)}
                    </div>
                </div>

                <div className="text-md-end">
                    <div className="text-muted small">
                        <div>
                            <strong>Duración:</strong> {formatDuration(session.start_time, session.end_time)}
                        </div>
                        <div>
                            <strong>Detecciones:</strong> {session.detections.length}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default SessionItem;
