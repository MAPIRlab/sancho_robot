import React from "react";
import LoadInputButton from "./LoadInputButton";

const ModelItem = ({
    provider,
    executedLocally,
    needsApiKey,
    model,
    loaded,
    active,
    setApiKeys,
    showApiInput,
    apiKeys,
    onConfirmLoad,
    onStartLoad,
    onActivate,
    onUnload,
}) => {
    return (
        <div
            key={provider + model}
            className={`list-group-item d-flex justify-content-between align-items-center ${
                active ? "list-group-item-primary" : ""
            }`}
        >
            <div className="me-3">
                <h6 className="mb-1 text-capitalize">{model}</h6>
                <div>
                    <span className={`badge me-2 ${loaded ? "bg-success" : "bg-secondary"}`}>
                        {loaded ? "Cargado" : "No cargado"}
                    </span>
                    {active && <span className="badge bg-primary">Activo</span>}
                </div>
            </div>

            <div className="btn-group align-items-center">
                {executedLocally && !loaded && (
                    <LoadInputButton
                        provider={provider}
                        model={model}
                        showApiInput={showApiInput[provider] == model}
                        apiKey={apiKeys[provider]}
                        needsApiKey={needsApiKey}
                        setApiKeys={setApiKeys}
                        onConfirmLoad={onConfirmLoad}
                        onStartLoad={onStartLoad}
                    />
                )}

                {executedLocally && loaded && !active && (
                    <>
                        <button className="btn btn-sm btn-outline-primary" onClick={() => onActivate(provider, model)}>
                            Activar
                        </button>
                        <button className="btn btn-sm btn-outline-danger" onClick={() => onUnload(provider, model)}>
                            Liberar
                        </button>
                    </>
                )}

                {!executedLocally && loaded && !active && (
                    <button className="btn btn-sm btn-outline-primary" onClick={() => onActivate(provider, model)}>
                        Activar
                    </button>
                )}
            </div>
        </div>
    );
};

export default ModelItem;
