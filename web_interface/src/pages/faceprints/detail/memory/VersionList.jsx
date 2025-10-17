import React from "react";

const fmt = (ts) =>
    new Intl.DateTimeFormat("es-ES", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    }).format(new Date(ts));

const VersionList = ({ versions, latestVersion, selected, onSelect }) => {
    return (
        <div className="card shadow-sm">
            <div className="card-header d-flex align-items-center justify-content-between">
                <span className="fw-semibold py-1">
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
                                <div className="small">{fmt(v.created_at * 1000)}</div>
                            </div>
                            {v.version === latestVersion ? (
                                <span className={`badge ${isActive ? "bg-light text-dark" : "bg-light text-dark"} border`}>
                                    Actual
                                </span>
                            ) : null}
                        </button>
                    );
                })}
            </div>
        </div>
    );
}

export default VersionList;