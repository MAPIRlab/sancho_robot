import React, { useEffect, useState } from "react";
import SessionList from "./SessionList";

import { useAPI } from "../../../../contexts/APIContext";

const ActivityDetail = ({ faceprint }) => {
    const { sessions, isResponseOk } = useAPI();

    const [sessionList, setSessionList] = useState(undefined);

    const fetchSessionData = async (id) => {
        setSessionList(undefined);

        const sessionResponse = await sessions.getAll(`?faceprint_id=${id}`);
        if (isResponseOk(sessionResponse)) {
            setSessionList(sessionResponse.data);
        } else {
            showToast("Error al obtener sesiones", sessionResponse.data.detail, "red");
        }
    };

    useEffect(() => {
        fetchSessionData(faceprint.id);
    }, []);

    return (
        <div className="">
            <div className="d-flex justify-content-between align-items-center mb-3">
                <h4 className="mb-0">Actividad</h4>
                <button className="btn btn-outline-secondary" onClick={() => fetchSessionData(faceprint.id)}>
                    <i className="bi bi-arrow-clockwise me-2" /> Recargar
                </button>
            </div>

            <div className="mb-5">
                {!sessionList ? (
                    <div className="d-flex align-items-center justify-content-center p-4">
                        <div className="spinner-border text-primary me-3" role="status" />
                        <span className="fs-5">Cargando lista de sesiones...</span>
                    </div>
                ) : (
                    <SessionList faceprint={faceprint} sessions={sessionList} />
                )}
            </div>
        </div>
    );
};

export default ActivityDetail;
