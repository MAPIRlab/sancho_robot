import React, { useState } from "react";

import { useFaceprints } from "../../contexts/FaceprintsContext";

import NewFaceprintModal from "./components/NewFaceprintModal";
import FaceprintList from "./components/FaceprintList";
import SummaryModal from "./components/SummaryModal";

const FaceprintListPage = () => {
    const { doAddFaceprint, fetchFaceprintsData, loadingFaceprints, faceprintsData } = useFaceprints();

    const [isOpenFaceModal, setIsOpenFaceModal] = useState(false);
    const [isSummaryOpen, setIsSummaryOpen] = useState(false);

    return (
        <>
            <NewFaceprintModal
                isOpen={isOpenFaceModal}
                handleClose={() => setIsOpenFaceModal(false)}
                doAddFaceprint={doAddFaceprint}
            />

            <SummaryModal isOpen={isSummaryOpen} handleClose={() => setIsSummaryOpen(false)} />

            <div className="container" style={{ marginTop: "76px" }}>
                <div className="d-flex justify-content-between align-items-center mb-4 pt-4">
                    <div className="text-start">
                        <h2 className="fw-bold mb-1">Galería de rostros</h2>
                        <p className="text-muted mb-0">Gestiona los rostros aprendidos por el sistema.</p>
                    </div>

                    <div>
                        <button className="btn btn-outline-primary me-2" onClick={() => setIsSummaryOpen(true)}>
                            <i className="bi bi-bar-chart-line" />
                        </button>
                        <button className="btn btn-primary me-2" onClick={() => setIsOpenFaceModal(true)}>
                            <i className="bi bi-database-add me-2" /> Añadir cara
                        </button>
                        <button className="btn btn-outline-secondary mt-2 mt-md-0" onClick={fetchFaceprintsData}>
                            <i className="bi bi-arrow-clockwise me-2" /> Recargar
                        </button>
                    </div>
                </div>

                <div className="mb-5">
                    {loadingFaceprints ? (
                        <div className="d-flex align-items-center justify-content-center p-4">
                            <div className="spinner-border text-primary me-3" role="status" />
                            <span className="fs-5">Cargando rostros...</span>
                        </div>
                    ) : (
                        <FaceprintList faceprints={faceprintsData} />
                    )}
                </div>
            </div>
        </>
    );
};

export default FaceprintListPage;
