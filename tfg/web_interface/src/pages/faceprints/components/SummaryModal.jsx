import React, { useEffect, useState } from "react";

import SimpleModal from "../../../components/SimpleModal";

import { useAPI } from "../../../contexts/APIContext";
import { useToast } from "../../../contexts/ToastContext";
import { useFaceprints } from "../../../contexts/FaceprintsContext";

const formatTimestamp = (ts) => {
    const date = new Date(parseFloat(ts) * 1000);
    return date.toLocaleString("es-ES", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
    });
};

const SummaryModal = ({ isOpen, handleClose }) => {
    const { sessions, isResponseOk } = useAPI();
    const { faceprintsData } = useFaceprints();
    const { showToast } = useToast();

    const [sessionMap, setSessionMap] = useState(undefined);

    const fetchSummary = async () => {
        setSessionMap(undefined);
        const sessionResponse = await sessions.getSummary();
        if (isResponseOk(sessionResponse)) {
            const map = {};
            for (const item of sessionResponse.data) {
                map[item.faceprint_id] = item;
            }
            setSessionMap(map);
        } else {
            showToast("Error al obtener sesiones", sessionResponse.data.detail, "red");
            setSessionMap(null);
        }
    };

    useEffect(() => {
        if (isOpen) fetchSummary();
    }, [isOpen]);

    return (
        <SimpleModal
            name="summary-info"
            title="Resumen de actividad de personas"
            handleClose={handleClose}
            isOpen={isOpen}
            size="xl"
        >
            <div className="mb-3">
                <div className="d-flex justify-content-end mb-3">
                    <button className="btn btn-outline-secondary" onClick={fetchSummary}>
                        <i className="bi bi-arrow-clockwise me-2" /> Recargar
                    </button>
                </div>

                {sessionMap === undefined ? (
                    <div className="d-flex align-items-center justify-content-center p-4">
                        <div className="spinner-border text-primary me-3" role="status" />
                        <span className="fs-5">Cargando resumen de sesiones...</span>
                    </div>
                ) : sessionMap === null ? (
                    <div className="alert alert-danger text-center">
                        Error al cargar el resumen de sesiones. Verifica la conexión o pulsa en recargar.
                    </div>
                ) : faceprintsData.length === 0 ? (
                    <div className="alert alert-warning text-center" role="alert">
                        No hay rostros registrados en el sistema.
                    </div>
                ) : (
                    <div className="table-responsive rounded border shadow-sm">
                        <table className="table table-hover align-middle mb-0">
                            <thead className="table-light text-secondary small text-uppercase">
                                <tr className="text-center">
                                    <th>Imagen</th>
                                    <th>Nombre</th>
                                    <th>Sesiones</th>
                                    <th>Detecciones</th>
                                    <th>Primera vez visto</th>
                                    <th>Última vez visto</th>
                                    <th>Duración total</th>
                                    <th>Duración media</th>
                                    <th>Detecciones/sesión</th>
                                </tr>
                            </thead>
                            <tbody>
                                {faceprintsData.map((fp) => {
                                    const item = sessionMap[fp.id];
                                    return (
                                        <tr key={fp.id} className="text-center">
                                            <td>
                                                <img
                                                    src={`data:image/jpeg;base64,${fp.face}`}
                                                    alt={fp.name}
                                                    className="rounded-circle border shadow"
                                                    style={{ width: "48px", height: "48px", objectFit: "cover" }}
                                                />
                                            </td>
                                            <td className="fw-bold">{fp.name}</td>
                                            {item ? (
                                                <>
                                                    <td>{item.sessions_count}</td>
                                                    <td>{item.times_seen}</td>
                                                    <td>{formatTimestamp(item.first_seen)}</td>
                                                    <td>{formatTimestamp(item.last_seen)}</td>
                                                    <td>{item.total_duration.toFixed(2)}s</td>
                                                    <td>{item.avg_session_duration.toFixed(2)}s</td>
                                                    <td>{item.avg_detections_per_session.toFixed(2)}</td>
                                                </>
                                            ) : (
                                                <td colSpan="7" className="text-muted">
                                                    Sin actividad registrada
                                                </td>
                                            )}
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </SimpleModal>
    );
};

export default SummaryModal;
