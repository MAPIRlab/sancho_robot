import React from "react";
import SimpleModal from "../../../components/SimpleModal";
import ScoresChart from "./ScoresChart";

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

const SessionModal = ({ session, handleClose, isOpen }) => {
    if (!session) return null;

    const calcStats = (arr) => {
        if (!arr.length) return {};
        const mean = arr.reduce((a, b) => a + b, 0) / arr.length;
        const sorted = [...arr].sort((a, b) => a - b);
        const median =
            sorted.length % 2 === 0
                ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
                : sorted[Math.floor(sorted.length / 2)];
        const min = Math.min(...arr);
        const max = Math.max(...arr);
        const std = Math.sqrt(arr.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / arr.length);
        return { mean, median, min, max, std };
    };

    const duration = (parseFloat(session.end_time) - parseFloat(session.start_time)).toFixed(2);
    const numDetections = session.detections.length;

    const times = session.detections.map((d) => parseFloat(d[0]) - parseFloat(session.start_time));
    const detectionScores = session.detections.map((d) => d[1]);
    const classificationScores = session.detections.map((d) => d[2]);

    const detectionStats = calcStats(detectionScores);
    const classificationStats = calcStats(classificationScores);

    const renderStatsCard = (title, stats) => (
        <div className="card p-3 shadow-sm mb-3" style={{ backgroundColor: "#f8f9fa" }}>
            <h6 className="mb-3 text-primary fw-bold">{title}</h6>
            <div className="row">
                <div className="col-6 mb-2">
                    <strong>Media:</strong> {stats.mean.toFixed(3)}
                </div>
                <div className="col-6 mb-2">
                    <strong>Mediana:</strong> {stats.median.toFixed(3)}
                </div>
                <div className="col-6 mb-2">
                    <strong>Mínimo:</strong> {stats.min.toFixed(3)}
                </div>
                <div className="col-6 mb-2">
                    <strong>Máximo:</strong> {stats.max.toFixed(3)}
                </div>
                <div className="col-12">
                    <strong>Desv. estándar:</strong> {stats.std.toFixed(3)}
                </div>
            </div>
        </div>
    );

    return (
        <SimpleModal
            name="session-info"
            size="xl"
            title="Información sobre la sesión"
            handleClose={handleClose}
            isOpen={isOpen}
            zIndex={100}
        >
            <div className="mb-3">
                <div className="card p-3 shadow-sm mb-4" style={{ backgroundColor: "#f8f9fa" }}>
                    <h5 className="mb-3 text-primary fw-bold">Detalles generales</h5>
                    <div className="row">
                        <div className="col-6 mb-2">
                            <strong>ID de sesión:</strong> {session.id}
                        </div>
                        <div className="col-6 mb-2">
                            <strong>Duración:</strong> {formatDuration(session.start_time, session.end_time)} segundos
                        </div>
                        <div className="col-6 mb-2">
                            <strong>Detecciones:</strong> {numDetections}
                        </div>
                        <div className="col-6 mb-2">
                            <strong>Frecuencia media:</strong> {(numDetections / duration).toFixed(2)} detecciones/seg
                        </div>
                    </div>
                </div>

                {renderStatsCard("Estadísticas de detección", detectionStats)}
                {renderStatsCard("Estadísticas de clasificación", classificationStats)}

                <div className="card p-3 shadow-sm mb-4" style={{ backgroundColor: "#f8f9fa", height: "320px" }}>
                    <h5 className="mb-3 text-primary fw-bold">Gráfico puntuación de detección</h5>
                    <div style={{ height: "100%" }}>
                        <ScoresChart
                            times={times}
                            scores={detectionScores}
                            label="Detección"
                        />
                    </div>
                </div>

                <div className="card p-3 shadow-sm" style={{ backgroundColor: "#f8f9fa", height: "320px" }}>
                    <h5 className="mb-3 text-primary fw-bold">Gráfico puntuación de clasificación</h5>
                    <div style={{ height: "100%" }}>
                        <ScoresChart
                            times={times}
                            scores={classificationScores}
                            label="Clasificación"
                        />
                    </div>
                </div>
            </div>
        </SimpleModal>
    );
};

export default SessionModal;
