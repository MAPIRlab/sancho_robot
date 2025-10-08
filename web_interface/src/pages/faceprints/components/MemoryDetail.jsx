// MemoryDetail.jsx
import React, { useEffect, useMemo, useState } from "react";

// --- Helpers ---
const fmt = (ts) =>
    new Intl.DateTimeFormat("es-ES", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    }).format(new Date(ts));

// --- Inline subcomponents (mantenido en este mismo archivo) ---
const VersionList = ({ versions, latestVersion, selected, onSelect }) => (
    <div className="card shadow-sm">
        <div className="card-header d-flex align-items-center justify-content-between">
            <span className="fw-semibold">
                Versiones <span className="badge bg-secondary ms-1">{versions.length}</span>
            </span>
        </div>
        <div className="list-group list-group-flush" style={{ maxHeight: 520, overflowY: "auto" }}>
            {versions.map((v) => {
                const isActive = selected === v.version;
                return (
                    <button
                        key={v.version}
                        className={`list-group-item list-group-item-action d-flex justify-content-between align-items-center ${isActive ? "active" : ""
                            }`}
                        onClick={() => onSelect(v.version)}
                    >
                        <div className="text-start">
                            <div className="fw-semibold">v{v.version}</div>
                            <div className="small">{fmt(v.created_at)}</div>
                        </div>
                        {v.version === latestVersion ? (
                            <span className={`badge ${isActive ? "bg-light text-dark" : "bg-light text-dark"} border`}>Actual</span>
                        ) : null}
                    </button>
                );
            })}
        </div>
    </div>
);

const FactListView = ({ memoryText }) => {
    const facts = (memoryText || "")
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);

    if (!facts.length) {
        return <div className="alert alert-secondary mb-0">Esta versión no tiene facts aún.</div>;
    }

    return (
        <ul className="list-group">
            {facts.map((f, idx) => (
                <li key={idx} className="list-group-item d-flex align-items-start">
                    <i className="bi bi-dot fs-4 me-2" />
                    <span>{f}</span>
                </li>
            ))}
        </ul>
    );
};

const FactListEditor = ({ facts, onChange }) => {
    const updateFact = (i, val) => {
        const next = [...facts];
        next[i] = val;
        onChange(next);
    };
    const addFact = () => onChange([...facts, ""]);
    const removeFact = (i) => onChange(facts.filter((_, idx) => idx !== i));
    const moveUp = (i) => {
        if (i === 0) return;
        const next = [...facts];
        [next[i - 1], next[i]] = [next[i], next[i - 1]];
        onChange(next);
    };
    const moveDown = (i) => {
        if (i === facts.length - 1) return;
        const next = [...facts];
        [next[i + 1], next[i]] = [next[i], next[i + 1]];
        onChange(next);
    };

    return (
        <>
            <div className="mb-3">
                <button className="btn btn-outline-primary btn-sm" onClick={addFact}>
                    <i className="bi bi-plus-lg me-1" />
                    Añadir fact
                </button>
            </div>

            {!facts.length && (
                <div className="alert alert-info">
                    No hay facts todavía. Pulsa <strong>Añadir fact</strong> para comenzar.
                </div>
            )}

            <div className="vstack gap-2">
                {facts.map((f, i) => (
                    <div key={i} className="input-group">
                        <span className="input-group-text">{i + 1}</span>
                        <input
                            type="text"
                            className="form-control"
                            value={f}
                            placeholder="Escribe un fact…"
                            onChange={(e) => updateFact(i, e.target.value)}
                        />
                        <button
                            className="btn btn-outline-secondary"
                            type="button"
                            title="Subir"
                            onClick={() => moveUp(i)}
                            disabled={i === 0}
                        >
                            <i className="bi bi-arrow-up" />
                        </button>
                        <button
                            className="btn btn-outline-secondary"
                            type="button"
                            title="Bajar"
                            onClick={() => moveDown(i)}
                            disabled={i === facts.length - 1}
                        >
                            <i className="bi bi-arrow-down" />
                        </button>
                        <button
                            className="btn btn-outline-danger"
                            type="button"
                            title="Eliminar"
                            onClick={() => removeFact(i)}
                        >
                            <i className="bi bi-trash" />
                        </button>
                    </div>
                ))}
            </div>

            <div className="mt-3">
                <small className="text-muted">
                    Se guardará como un texto con líneas separadas por <code>\n</code>.
                </small>
            </div>
        </>
    );
};

// --- Main ---
const MemoryDetail = ({ faceprint }) => {
    // MOCK: sustituye por tus llamadas reales
    const makeMock = () => [
        {
            faceprint_id: faceprint.id,
            version: 1,
            memory_text: "Vive en Málaga\nLe gusta el café",
            created_at: Date.now() - 1000 * 60 * 60 * 24 * 14,
        },
        {
            faceprint_id: faceprint.id,
            version: 2,
            memory_text: "Vive en Málaga\nLe gusta el café\nEs experto en fútbol",
            created_at: Date.now() - 1000 * 60 * 60 * 24 * 7,
        },
        {
            faceprint_id: faceprint.id,
            version: 3,
            memory_text: "Vive en Málaga\nLe gusta el café\nEs experto en fútbol\nEstá retomando calistenia",
            created_at: Date.now() - 1000 * 60 * 60 * 24 * 2,
        },
    ];

    const [versions, setVersions] = useState(undefined);
    const [selectedVersion, setSelectedVersion] = useState(undefined);
    const [isEditing, setIsEditing] = useState(false);
    const [draftFacts, setDraftFacts] = useState([]);

    // Carga mock
    useEffect(() => {
        const data = makeMock().sort((a, b) => b.version - a.version);
        setVersions(data);
        setSelectedVersion(data[0].version);
    }, [faceprint.id]);

    const latestVersion = useMemo(
        () => (versions && versions.length ? versions[0].version : undefined),
        [versions]
    );

    const current = useMemo(
        () => (versions ? versions.find((v) => v.version === selectedVersion) : undefined),
        [versions, selectedVersion]
    );

    // Edición (solo la última)
    const startEdit = () => {
        const facts = (current?.memory_text || "")
            .split("\n")
            .map((s) => s.trim())
            .filter((s) => s.length > 0);
        setDraftFacts(facts);
        setIsEditing(true);
    };

    const cancelEdit = () => {
        setIsEditing(false);
        setDraftFacts([]);
    };

    const handleSaveNewVersion = () => {
        const joined = draftFacts.map((s) => s.trim()).filter(Boolean).join("\n");
        if (!joined.length) return;

        // MOCK: crear nueva versión (reemplaza por POST al backend)
        const next = (latestVersion || 0) + 1;
        const newV = {
            faceprint_id: faceprint.id,
            version: next,
            memory_text: joined,
            created_at: Date.now(),
        };
        const updated = [newV, ...(versions || [])].sort((a, b) => b.version - a.version);
        setVersions(updated);
        setSelectedVersion(next);
        setIsEditing(false);
        setDraftFacts([]);
    };

    const handleReload = () => {
        const data = makeMock().sort((a, b) => b.version - a.version);
        setVersions(data);
        setSelectedVersion(data[0].version);
        setIsEditing(false);
        setDraftFacts([]);
    };

    if (!versions) {
        return (
            <div className="d-flex align-items-center justify-content-center p-4">
                <div className="spinner-border text-primary me-3" role="status" />
                <span className="fs-5">Cargando memoria...</span>
            </div>
        );
    }

    return (
        <div>
            {/* Toolbar */}
            <div className="d-flex justify-content-between align-items-center mb-3">
                <h4 className="mb-0">Memoria</h4>
                <button className="btn btn-outline-secondary" onClick={handleReload}>
                    <i className="bi bi-arrow-clockwise me-2" /> Recargar
                </button>
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
                            setIsEditing(false);
                            setDraftFacts([]);
                        }}
                    />
                </div>

                {/* Derecha: visor / editor */}
                <div className="col-12 col-md-8 col-lg-9">
                    <div className="card shadow-sm">
                        <div className="card-header d-flex justify-content-between align-items-center">
                            <div>
                                <span className="fw-semibold">v{current.version}</span>
                                <span className="text-muted ms-2">{fmt(current.created_at)}</span>
                                {current.version === latestVersion && <span className="badge bg-secondary ms-2">Actual</span>}
                            </div>
                            <div className="btn-group">
                                {current.version === latestVersion && !isEditing && (
                                    <button className="btn btn-primary btn-sm" onClick={startEdit}>
                                        <i className="bi bi-pencil-square me-1" />
                                        Editar
                                    </button>
                                )}
                                {isEditing && (
                                    <>
                                        <button className="btn btn-success btn-sm" onClick={handleSaveNewVersion}>
                                            <i className="bi bi-save2 me-1" />
                                            Guardar nueva versión
                                        </button>
                                        <button className="btn btn-outline-secondary btn-sm" onClick={cancelEdit}>
                                            Cancelar
                                        </button>
                                    </>
                                )}
                            </div>
                        </div>

                        <div className="card-body">
                            {isEditing ? (
                                <FactListEditor facts={draftFacts} onChange={setDraftFacts} />
                            ) : (
                                <FactListView memoryText={current.memory_text} />
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default MemoryDetail;
