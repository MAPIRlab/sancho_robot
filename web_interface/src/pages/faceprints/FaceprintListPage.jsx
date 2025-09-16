import React, { useState } from "react";

import { useFaceprints } from "../../contexts/FaceprintsContext";

import NewFaceprintModal from "./components/NewFaceprintModal";
import FaceprintList from "./components/FaceprintList";
import SummaryModal from "./components/SummaryModal";
import ConfirmDeleteAllModal from "./components/ConfirmDeleteAllModal";

const FaceprintListPage = () => {
    const { doDeleteAllFaceprints, doAddFaceprint, fetchFaceprintsData, loadingFaceprints, faceprintsData } = useFaceprints();

    const [isOpenFaceModal, setIsOpenFaceModal] = useState(false);
    const [isOpenDeleteAllModal, setIsOpenDeleteAllModal] = useState(false);
    const [isSummaryOpen, setIsSummaryOpen] = useState(false);

    return (
        <>
            <NewFaceprintModal
                isOpen={isOpenFaceModal}
                handleClose={() => setIsOpenFaceModal(false)}
                action={doAddFaceprint}
            />

            <ConfirmDeleteAllModal
                isOpen={isOpenDeleteAllModal}
                handleClose={() => setIsOpenDeleteAllModal(false)}
                action={doDeleteAllFaceprints}
            />


            <SummaryModal isOpen={isSummaryOpen} handleClose={() => setIsSummaryOpen(false)} />

            <div className="container" style={{ marginTop: "76px" }}>
                <div className="d-flex justify-content-between align-items-center mb-4 pt-4">
                    <div className="text-start col-6 col-md">
                        <h2 className="fw-bold mb-1">Galería de rostros</h2>
                        <p className="text-muted mb-0">Gestiona los rostros aprendidos por el sistema.</p>
                    </div>
                    <div>
                        <button className="btn btn-primary me-2" onClick={() => setIsOpenFaceModal(true)}>
                            <i className="bi bi-person-plus me-0 me-lg-2" /> <span className="d-none d-lg-inline">Nuevo</span>
                        </button>
                        <button className="btn btn-outline-primary me-2" onClick={() => setIsSummaryOpen(true)}>
                            <i className="bi bi-bar-chart-line me-0 me-lg-2" /> <span className="d-none d-lg-inline">Estadísticas</span>
                        </button>
                        <button className="btn btn-outline-secondary me-2" onClick={fetchFaceprintsData}>
                            <i className="bi bi-arrow-clockwise me-0 me-lg-2" /> <span className="d-none d-lg-inline">Recargar</span>
                        </button>
                        <button className="btn btn-danger" onClick={() => setIsOpenDeleteAllModal(true)}>
                            <i className="bi bi-trash me-0 me-lg-2" /> <span className="d-none d-lg-inline">Eliminar todo</span>
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
