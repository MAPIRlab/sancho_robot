import React from "react";

const LoadInputButton = ({
    provider,
    model,
    showApiInput,
    apiKey,
    needsApiKey,
    setApiKeys,
    onConfirmLoad,
    onStartLoad,
}) => {
    return (
        <div className="btn-group align-items-center">
            {showApiInput ? (
                <>
                    <input
                        type="password"
                        className="form-control form-control-sm me-2"
                        placeholder="API Key"
                        value={apiKey || ""}
                        onChange={(e) =>
                            setApiKeys((prev) => ({
                                ...prev,
                                [provider]: e.target.value,
                            }))
                        }
                        style={{ maxWidth: "200px" }}
                    />
                    <button
                        className="btn btn-sm btn-outline-success"
                        onClick={() => onConfirmLoad(provider, apiKey, model)}
                    >
                        Confirmar
                    </button>
                </>
            ) : (
                <button
                    className="btn btn-sm btn-outline-success"
                    onClick={() => onStartLoad(provider, needsApiKey, model)}
                >
                    Cargar
                </button>
            )}
        </div>
    );
};

export default LoadInputButton;
