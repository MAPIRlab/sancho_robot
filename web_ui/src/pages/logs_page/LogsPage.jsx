import React, { useEffect, useState } from "react";

import { useAPI } from "../../contexts/APIContext";
import { useToast } from "../../contexts/ToastContext";

import LogModal from "./components/LogModal";
import Pagination from "../../components/Pagination";

const LogsPage = () => {
    const { logs, isResponseOk } = useAPI();
    const { showToast } = useToast();

    const [logsList, setLogsList] = useState(undefined);
    const [currentPage, setCurrentPage] = useState(1);
    const [selectedLog, setSelectedLog] = useState(undefined);
    const perPage = 10;

    const fetchLogs = async () => {
        setLogsList(undefined);
        const response = await logs.getAll();
        if (isResponseOk(response)) {
            setLogsList(response.data);
        } else {
            showToast("Error al cargar logs", "No se han podido cargar los datos", "red");
            setLogsList(null);
        }
    };

    useEffect(() => {
        fetchLogs();
    }, []);

    const totalPages = logsList ? Math.ceil(logsList.length / perPage) : 0;
    const pageData = logsList ? logsList.slice((currentPage - 1) * perPage, currentPage * perPage) : [];

    return (
        <div className="container py-4" style={{ marginTop: "76px" }}>
            <div className="d-flex justify-content-between align-items-center mb-4">
                <div className="text-start">
                    <h2 className="fw-bold mb-1">Historial del sistema</h2>
                    <p className="text-muted mb-0">Consulta cada evento registrado por Sancho.</p>
                </div>
                <button className="btn btn-outline-secondary" onClick={fetchLogs}>
                    <i className="bi bi-arrow-clockwise me-2" />
                    Recargar
                </button>
            </div>

            <LogModal log={selectedLog} onClose={() => setSelectedLog(undefined)} />

            {logsList === undefined ? (
                <div className="d-flex align-items-center justify-content-center p-4">
                    <div className="spinner-border text-primary me-3" role="status" />
                    <span className="fs-5">Cargando logs...</span>
                </div>
            ) : logsList === null ? (
                <div className="alert alert-danger text-center">
                    Error al cargar los logs. Verifica la conexión o pulsa en recargar.
                </div>
            ) : logsList.length === 0 ? (
                <div className="alert alert-warning text-center">No hay logs registrados aún.</div>
            ) : (
                <>
                    <div className="table-responsive rounded border shadow-sm">
                        <table className="table table-hover align-middle mb-0">
                            <thead className="table-light text-secondary small text-uppercase">
                                <tr>
                                    <th>ID</th>
                                    <th>Hora</th>
                                    <th>Nivel</th>
                                    <th>Origen</th>
                                    <th>Actor</th>
                                    <th>Acción</th>
                                    <th className="text-center">Detalles</th>
                                </tr>
                            </thead>
                            <tbody>
                                {pageData.map((log) => (
                                    <tr key={log.id} className="align-middle">
                                        <td>{log.id}</td>
                                        <td className="text-muted">{formatTime(log.timestamp)}</td>
                                        <td>
                                            <span
                                                className={`badge bg-${getLevelColor(
                                                    log.level
                                                )} bg-opacity-25 border border-${getLevelColor(
                                                    log.level
                                                )} text-${getLevelColor(log.level)}`}
                                            >
                                                <i className={`bi ${getLevelIcon(log.level)} me-1`}></i>
                                                {log.level}
                                            </span>
                                        </td>
                                        <td>{log.origin}</td>
                                        <td>{log.actor || <em className="text-muted">—</em>}</td>
                                        <td className="fw-semibold">{log.action}</td>
                                        <td className="text-center">
                                            <button
                                                className="btn btn-sm btn-outline-primary rounded-circle"
                                                title="Ver detalles"
                                                onClick={() => setSelectedLog(log)}
                                            >
                                                <i className="bi bi-eye-fill"></i>
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    {totalPages > 1 && (
                        <div className="d-flex justify-content-center mt-4">
                            <Pagination
                                currentPage={currentPage}
                                totalPages={totalPages}
                                onPageChange={setCurrentPage}
                            />
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

const formatTime = (ts) => {
    try {
        return new Date(Number(ts) * 1000).toLocaleString();
    } catch {
        return ts;
    }
};

const getLevelColor = (level) => {
    switch (level) {
        case "INFO":
            return "primary";
        case "WARNING":
            return "warning";
        case "ERROR":
            return "danger";
        case "DEBUG":
            return "secondary";
        default:
            return "light";
    }
};

const getLevelIcon = (level) => {
    switch (level) {
        case "INFO":
            return "bi-info-circle";
        case "WARNING":
            return "bi-exclamation-triangle";
        case "ERROR":
            return "bi-x-circle";
        case "DEBUG":
            return "bi-terminal";
        default:
            return "bi-dot";
    }
};

export default LogsPage;
