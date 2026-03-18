import React, { useEffect, useMemo, useState } from "react";

import VersionList from "./VersionList";
import FactItem from "./FactItem";
import { useAPI } from "../../../../contexts/APIContext";
import { useToast } from "../../../../contexts/ToastContext";
import { useLoadingScreen } from "../../../../components/LoadingScreen";

const MemoryDetail = ({ faceprint }) => {
    const { memory, isResponseOk } = useAPI();
    const { withLoading } = useLoadingScreen();
    const { showToast } = useToast();

    const [versions, setVersions] = useState(undefined); // undefined = cargando, [] = sin memorias
    const [selectedVersion, setSelectedVersion] = useState(undefined);

    const [editingIndex, setEditingIndex] = useState(null);
    const [tempValue, setTempValue] = useState("");
    const [addingNew, setAddingNew] = useState(false);

    const fetchMemoryData = async (id) => {
        setVersions(undefined);

        const memoryResponse = await memory.getVersions(id);
        if (isResponseOk(memoryResponse)) {
            setVersions(memoryResponse.data);
            setSelectedVersion(memoryResponse.data[0]?.version); // si viene vacío, queda undefined

            setEditingIndex(null);
            setAddingNew(false);
            setTempValue("");
        } else {
            showToast("Error al obtener la memoria", memoryResponse.data.detail, "red");
            setVersions(null);
            setSelectedVersion(undefined);
        }
    };

    useEffect(() => {
        fetchMemoryData(faceprint.id);
    }, []);

    const latestVersion = useMemo(
        () => (versions && versions.length ? versions[0].version : undefined),
        [versions]
    );

    const current = useMemo(
        () => (versions ? versions.find((v) => v.version === selectedVersion) : undefined),
        [versions, selectedVersion]
    );

    const currentFacts = useMemo(
        () =>
            (current?.memory_text || "")
                .split("\n")
                .map((s) => s.trim())
                .filter(Boolean),
        [current]
    );

    const canEdit = (current?.version === latestVersion) || !(versions?.length);

    const updateActualVersion = async (factsArray) => {
        const joined = factsArray.map((s) => s.trim()).filter(Boolean).join("\n");

        const response = await withLoading(() => memory.update(faceprint.id, { memory_text: joined }));
        if (isResponseOk(response)) {
            const updatedFromServer = response.data; // debería traer { faceprint_id, version, memory_text, created_at/... }
            setVersions(prev => [updatedFromServer, ...(prev?.slice(1) ?? [])]);
            showToast("Memoria actualizada", "Has actualizado la memoria de " + (faceprint.name || faceprint.id) + " satisfactoriamente", "green");
        } else {
            showToast("Error", response.data.detail, "red");
        }

        return response;
    };

    const handleConfirmEdit = () => {
        if (editingIndex === null && !addingNew) return;

        const baseFacts = currentFacts; // [] si no hay current
        let nextFacts = [...baseFacts];

        if (addingNew) {
            nextFacts.push((tempValue || "").trim());
        } else {
            nextFacts[editingIndex] = (tempValue || "").trim();
        }
        nextFacts = nextFacts.filter((s) => s.length > 0);

        updateActualVersion(nextFacts);
        handleCancelEdit();
    };

    const handleDelete = (i) => {
        if (!canEdit) return;
        const nextFacts = currentFacts.filter((_, idx) => idx !== i);
        updateActualVersion(nextFacts);
    };

    const handleAddFact = () => {
        if (!canEdit) return;
        setEditingIndex(null);
        setAddingNew(true);
        setTempValue("");
    };

    const handleStartEdit = (i) => {
        if (!canEdit) return;
        setAddingNew(false);
        setEditingIndex(i);
        setTempValue(currentFacts[i] ?? "");
    };

    const handleCancelEdit = () => {
        setEditingIndex(null);
        setAddingNew(false);
        setTempValue("");
    };

    if (versions === undefined) {
        return (
            <div className="d-flex align-items-center justify-content-center p-4">
                <div className="spinner-border text-primary me-3" role="status" />
                <span className="fs-5">Cargando memoria...</span>
            </div>
        );
    }

    if (versions === null) {
        return (
            <div className="alert alert-danger my-4 text-center" role="alert">
                Error al cargar la memoria. Verifica la conexión o pulsa en recargar.
            </div>
        );
    }

    return (
        <div>
            <div className="d-flex justify-content-between align-items-center mb-3">
                <h4 className="mb-0">Memoria</h4>
            </div>

            <div className="row g-3">
                {/* Izquierda: versiones */}
                <div className="col-12 col-md-4 col-lg-3">
                    <VersionList
                        versions={versions}
                        latestVersion={latestVersion}
                        selected={selectedVersion}
                        onSelect={(v) => {
                            setSelectedVersion(v);
                            handleCancelEdit();
                        }}
                    />
                </div>

                {/* Derecha: facts + acciones */}
                <div className="col-12 col-md-8 col-lg-9">
                    <div className="card shadow-sm">
                        <div className="d-flex justify-content-between card-header d-flex align-items-center">
                            <div className="d-flex align-items-center justify-content-start">
                                {current ? (
                                    <span className="fw-semibold">v{current.version}</span>
                                ) : (
                                    <span className="fw-semibold text-muted">Sin versiones</span>
                                )}
                            </div>

                            <div className="d-flex justify-content-end align-items-center">
                                {canEdit ? (
                                    <button className="btn btn-outline-primary btn-sm" onClick={handleAddFact}>
                                        <i className="bi bi-plus-lg me-1" />
                                        Añadir fact
                                    </button>
                                ) : (
                                    <button className="btn btn-outline-primary btn-sm invisible">
                                        <i className="bi bi-plus-lg me-1" />
                                        Añadir fact
                                    </button>
                                )}
                                <button
                                    className="btn btn-outline-secondary btn-sm ms-2"
                                    onClick={() => fetchMemoryData(faceprint.id)}
                                >
                                    <i className="bi bi-arrow-clockwise me-0 me-sm-2" /> Recargar
                                </button>
                            </div>
                        </div>

                        <div className="card-body p-0">
                            {/* Lista de facts */}
                            {currentFacts.length ? (
                                <ul className="list-group list-group-flush">
                                    {currentFacts.map((f, i) => (
                                        <FactItem
                                            key={i}
                                            text={f}
                                            canEdit={canEdit}
                                            isEditing={editingIndex === i && !addingNew}
                                            onStartEdit={() => handleStartEdit(i)}
                                            onCancelEdit={handleCancelEdit}
                                            onConfirmEdit={handleConfirmEdit}
                                            onDelete={() => handleDelete(i)}
                                            tempValue={tempValue}
                                            setTempValue={setTempValue}
                                        />
                                    ))}
                                </ul>
                            ) : (
                                <div className="alert alert-secondary mb-0">
                                    {versions.length ? "Memoria vacía" : "Aún no hay ninguna memoria para esta persona."}
                                </div>
                            )}

                            {/* Fila para añadir nuevo fact */}
                            {addingNew && (
                                <ul className="list-group list-group-flush">
                                    <li className="list-group-item d-flex align-items-center py-2">
                                        <div className="flex-grow-1 me-3">
                                            <input
                                                type="text"
                                                className="form-control form-control-sm"
                                                value={tempValue}
                                                placeholder="Escribe un fact nuevo…"
                                                onChange={(e) => setTempValue(e.target.value)}
                                                autoFocus
                                            />
                                        </div>
                                        <div className="d-flex justify-content-end ms-auto">
                                            <div className="btn-group btn-group-sm">
                                                <button className="btn btn-success" onClick={handleConfirmEdit} title="Añadir">
                                                    <i className="bi bi-check-lg" />
                                                </button>
                                                <button className="btn btn-outline-secondary" onClick={handleCancelEdit} title="Cancelar">
                                                    <i className="bi bi-x-lg" />
                                                </button>
                                            </div>
                                        </div>
                                    </li>
                                </ul>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default MemoryDetail;
