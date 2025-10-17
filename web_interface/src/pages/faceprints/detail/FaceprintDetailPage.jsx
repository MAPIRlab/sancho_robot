import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { useFaceprints } from "../../../contexts/FaceprintsContext";
import { useAPI } from "../../../contexts/APIContext";
import { useToast } from "../../../contexts/ToastContext";

import SummaryDetail from "./summary/SummaryDetail";
import ActivityDetail from "./activity/ActivityDetail";
import MemoryDetail from "./memory/MemoryDetail";

const FaceprintDetailPage = () => {
    const { id } = useParams();

    const { showToast } = useToast();
    const { getFaceprint } = useFaceprints();
    const { faceprints, isResponseOk } = useAPI();

    const [faceprint, setFaceprint] = useState(undefined);

    const [activeTab, setActiveTab] = useState("summary"); // "summary" | "activity"
    const navigate = useNavigate();

    useEffect(() => {
        const getActualFaceprint = async () => {
            let faceprint = getFaceprint(id);
            if (!faceprint) {
                const response = await faceprints.getById(id);
                if (isResponseOk(response)) {
                    faceprint = response.data;
                } else {
                    showToast("Error al obtener faceprint", response.data.detail, "red");
                }
            }

            setFaceprint(faceprint);
        };

        getActualFaceprint();
    }, []);

    if (!faceprint) {
        return (
            <div className="d-flex align-items-center justify-content-center p-5" style={{ marginTop: "76px" }}>
                <div className="spinner-border text-primary me-3" role="status" />
                <span className="fs-5">Cargando información...</span>
            </div>
        );
    }

    return (
        <>
            <div className="container" style={{ marginTop: "76px" }}>

                <div className="d-flex align-items-center justify-content-between py-4">
                    <button className="btn btn-secondary" onClick={() => navigate("/faceprints")}>
                        Volver
                    </button>

                    {/* Tabs */}
                    <ul className="nav nav-pills">
                        <li className="nav-item">
                            <button
                                className={`nav-link ${activeTab === "summary" ? "active" : ""}`}
                                onClick={() => setActiveTab("summary")}
                            >
                                <i className="bi bi-person-badge me-2" />
                                Resumen
                            </button>
                        </li>
                        <li className="nav-item">
                            <button
                                className={`nav-link ${activeTab === "activity" ? "active" : ""}`}
                                onClick={() => setActiveTab("activity")}
                            >
                                <i className="bi bi-activity me-2" />
                                Actividad
                            </button>
                        </li>
                        <li className="nav-item">
                            <button
                                className={`nav-link ${activeTab === "memory" ? "active" : ""}`}
                                onClick={() => setActiveTab("memory")}
                            >
                                <i className="bi bi-sd-card me-2" />
                                Memoria
                            </button>
                        </li>
                    </ul>
                </div>

                {activeTab === "summary" && <SummaryDetail faceprint={faceprint} />}
                {activeTab === "activity" && <ActivityDetail faceprint={faceprint} />}
                {activeTab === "memory" && <MemoryDetail faceprint={faceprint} />}
            </div>
        </>
    );
};

export default FaceprintDetailPage;
