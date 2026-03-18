import React, { useState } from "react";

import { useAPI } from "../../../contexts/APIContext";
import { useToast } from "../../../contexts/ToastContext";
import { useLoadingScreen } from "../../../components/LoadingScreen";
import { useModels } from "../../../contexts/ModelsContext";

const STTPanel = () => {
    const { sttModelsList, setSttModelsList } = useModels();
    const { sttModels, isResponseOk } = useAPI();
    const { withLoading } = useLoadingScreen();
    const { showToast } = useToast();

    const [apiKeys, setApiKeys] = useState({});
    const [showApiInput, setShowApiInput] = useState({});

    const getCachedApiKey = (model) => {
        return localStorage.getItem(`stt_api_key_${model}`) || "";
    };

    const cacheApiKey = (model, apiKey) => {
        localStorage.setItem(`stt_api_key_${model}`, apiKey);
    };

    const onStartLoad = (model, needsApiKey) => {
        if (needsApiKey) {
            const cached = getCachedApiKey(model);
            setApiKeys((prev) => ({ ...prev, [model]: cached }));
            setShowApiInput((prev) => ({ ...prev, [model]: true }));
        } else {
            onConfirmLoad(model, needsApiKey, "");
        }
    };

    const onConfirmLoad = async (model, needsApiKey, apiKey) => {
        if (needsApiKey && (!apiKey || apiKey.trim() === "")) {
            showToast("API Key requerida", "Debes introducir una API key para este modelo.", "yellow");
            return;
        }

        const response = await withLoading(() =>
            sttModels.load({
                model: model,
                api_key: apiKey,
            })
        );

        if (isResponseOk(response)) {
            const { message, success } = response.data;
            if (success) {
                if (apiKey) cacheApiKey(model, apiKey);

                showToast("Modelo cargado", `El modelo '${model}' se ha cargado correctamente.`, "green");
                setSttModelsList((list) => list.map((m) => (m.model === model ? { ...m, loaded: true } : m)));
                setShowApiInput((prev) => ({ ...prev, [model]: false }));
            } else {
                showToast("Error al cargar modelo", message, "red");
            }
        } else {
            showToast("Error al cargar modelo", response.data.detail, "red");
        }
    };

    const onUnload = async (model) => {
        const response = await withLoading(() =>
            sttModels.unload({
                model: model,
            })
        );

        if (isResponseOk(response)) {
            const { message, success } = response.data;
            if (success) {
                showToast("Modelo liberado", `El modelo '${model}' se ha liberado correctamente.`, "green");
                setSttModelsList((list) => list.map((m) => (m.model === model ? { ...m, loaded: false } : m)));
            } else {
                showToast("Error al liberar modelo", message, "red");
            }
        } else {
            showToast("Error al liberar modelo", response.data.detail, "red");
        }
    };

    const onActivate = async (model) => {
        const response = await withLoading(() =>
            sttModels.activate({
                model: model,
            })
        );

        if (isResponseOk(response)) {
            const { message, success } = response.data;
            if (success) {
                showToast("Modelo activado", `El modelo '${model}' se ha activado correctamente.`, "green");
                setSttModelsList((list) =>
                    list.map((m) =>
                        m.model === model ? { ...m, active: true } : m.active ? { ...m, active: false } : m
                    )
                );
            } else {
                showToast("Error al activar modelo", message, "red");
            }
        } else {
            showToast("Error al activar modelo", response.data.detail, "red");
        }
    };

    if (sttModelsList === undefined) {
        return (
            <div className="d-flex align-items-center justify-content-center p-4">
                <div className="spinner-border text-primary me-3" role="status" />
                <span className="fs-5">Cargando modelos STT...</span>
            </div>
        );
    }

    if (sttModelsList === null) {
        return (
            <div className="alert alert-danger my-4 text-center" role="alert">
                Error al cargar los modelos STT. Verifica la conexión o pulsa en recargar.
            </div>
        );
    }

    return (
        <div className="list-group shadow-sm">
            {sttModelsList.map((model) => (
                <div
                    key={model.model}
                    className={`list-group-item d-flex justify-content-between align-items-center ${
                        model.active ? "list-group-item-primary" : ""
                    }`}
                >
                    <div className="me-3">
                        <h5 className="mb-1 text-capitalize">{model.model}</h5>
                        <div>
                            <span className={`badge me-2 ${model.loaded ? "bg-success" : "bg-secondary"}`}>
                                {model.loaded ? "Cargado" : "No cargado"}
                            </span>
                            {model.active && <span className="badge bg-primary">Activo</span>}
                        </div>
                    </div>

                    <div className="btn-group align-items-center">
                        {!model.loaded && !showApiInput[model.model] && (
                            <button
                                className="btn btn-sm btn-outline-success"
                                onClick={() => onStartLoad(model.model, model.needs_api_key)}
                            >
                                Cargar
                            </button>
                        )}

                        {!model.loaded && showApiInput[model.model] && (
                            <>
                                <input
                                    type="password"
                                    className="form-control form-control-sm"
                                    placeholder="API Key"
                                    value={apiKeys[model.model] || ""}
                                    onChange={(e) =>
                                        setApiKeys((prev) => ({
                                            ...prev,
                                            [model.model]: e.target.value,
                                        }))
                                    }
                                    style={{ maxWidth: "150px", marginRight: "0.5rem" }}
                                />
                                <button
                                    className="btn btn-sm btn-outline-success"
                                    onClick={() => onConfirmLoad(model.model, model.needsApiKey, apiKeys[model.model])}
                                >
                                    Confirmar
                                </button>
                            </>
                        )}

                        {model.loaded && !model.active && (
                            <>
                                <button
                                    className="btn btn-sm btn-outline-primary"
                                    onClick={() => onActivate(model.model)}
                                >
                                    Activar
                                </button>
                                <button className="btn btn-sm btn-outline-danger" onClick={() => onUnload(model.model)}>
                                    Liberar
                                </button>
                            </>
                        )}
                    </div>
                </div>
            ))}
        </div>
    );
};

export default STTPanel;
