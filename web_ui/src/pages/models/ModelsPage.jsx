import React from "react";

import { useModels } from "../../contexts/ModelsContext";

import TTSPanel from "./components/TTSPanel";
import STTPanel from "./components/STTPanel";
import LLMPanel from "./components/LLMPanel";

const PANELS = [
    { key: "tts", label: "TTS", icon: "bi-volume-up-fill", component: <TTSPanel /> },
    { key: "stt", label: "STT", icon: "bi-mic-fill", component: <STTPanel /> },
    { key: "llm", label: "LLM", icon: "bi-cpu-fill", component: <LLMPanel /> },
];

const ModulesPage = () => {
    const { activeTab, setActiveTab, fetchFunctions } = useModels();

    const activePanel = PANELS.find((panel) => panel.key === activeTab);

    return (
        <div className="container pt-4" style={{ marginTop: "76px" }}>
            <div className="text-start mb-4">
                <h2 className="fw-bold mb-1 text-center text-md-start">Gestión de modelos</h2>
                <p className="text-muted mb-0 text-center text-md-start">Carga, activa y libera modelos del sistema.</p>
            </div>

            <div className="row">
                <div className="col-md-3">
                    <div className="list-group shadow-sm">
                        {PANELS.map(({ key, label, icon }) => (
                            <button
                                key={key}
                                className={`list-group-item list-group-item-action ${
                                    activeTab === key ? "active" : ""
                                }`}
                                onClick={() => setActiveTab(key)}
                            >
                                <i className={`bi ${icon} me-2`} />
                                {label}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="col-md-9 mt-2 mt-md-0">
                    <div className="card border rounded shadow-sm mb-5">
                        <div className="card-header d-flex justify-content-between align-items-center bg-light fw-semibold">
                            <div>
                                <i className="bi bi-gear me-2" />
                                Modelos {activePanel?.label || ""}
                            </div>

                            <button className="btn btn-outline-secondary" onClick={() => fetchFunctions[activeTab]()}>
                                <i className="bi bi-arrow-clockwise me-2" /> Recargar
                            </button>
                        </div>
                        <div className="card-body">{activePanel?.component || null}</div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ModulesPage;
