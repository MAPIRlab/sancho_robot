import React, { useState } from "react";

import { useAPI } from "../../../contexts/APIContext";
import { useToast } from "../../../contexts/ToastContext";
import { useLoadingScreen } from "../../../components/LoadingScreen";
import { useModels } from "../../../contexts/ModelsContext";

import ModelItem from "./ModelItem";
import LoadInputButton from "./LoadInputButton";

const LLMPanel = () => {
    const { llmProvidersList, setLlmProvidersList } = useModels();

    const { llmModels, isResponseOk } = useAPI();
    const { showToast } = useToast();
    const { withLoading } = useLoadingScreen();

    const [apiKeys, setApiKeys] = useState({});
    const [showApiInput, setShowApiInput] = useState({});

    const getCachedApiKey = (provider) => localStorage.getItem(`llm_api_key_${provider}`) || "";
    const cacheApiKey = (provider, key) => localStorage.setItem(`llm_api_key_${provider}`, key);

    const onStartLoad = (provider, needsApiKey, model = null) => {
        if (needsApiKey) {
            const cached = getCachedApiKey(provider);
            setApiKeys((prev) => ({ ...prev, [provider]: cached }));
            setShowApiInput((prev) => ({ ...prev, [provider]: model || true }));
        } else {
            onConfirmLoad(provider, "", model);
        }
    };

    const onConfirmLoad = async (provider, apiKey, model = null) => {
        const providerData = llmProvidersList.find((p) => p.provider === provider);
        const needsApiKey = providerData.needs_api_key;

        if (needsApiKey && (!apiKey || apiKey.trim() === "")) {
            showToast("API Key requerida", "Debes introducir una API key para este proveedor.", "yellow");
            return;
        }

        const response = await withLoading(() =>
            llmModels.load({
                provider,
                model: model || providerData.models[0].model,
                api_key: apiKey,
            })
        );

        if (isResponseOk(response)) {
            const { message, success } = response.data;
            if (success) {
                if (needsApiKey) cacheApiKey(provider, apiKey);

                showToast("Modelo cargado", `El modelo '${model || "todos"}' ha sido cargado correctamente.`, "green");

                setLlmProvidersList((list) =>
                    list.map((p) =>
                        p.provider === provider
                            ? {
                                  ...p,
                                  models: p.models.map((m) =>
                                      model ? (m.model === model ? { ...m, loaded: true } : m) : { ...m, loaded: true }
                                  ),
                              }
                            : p
                    )
                );
                setShowApiInput((prev) => ({ ...prev, [provider]: false }));
            } else {
                showToast("Error al cargar modelo", message, "red");
            }
        } else {
            showToast("Error al cargar modelo", response.data.detail, "red");
        }
    };

    const onUnload = async (provider, model) => {
        const response = await withLoading(() =>
            llmModels.unload({
                provider,
                model,
            })
        );

        if (isResponseOk(response)) {
            const { message, success } = response.data;
            if (success) {
                showToast("Modelo liberado", `${provider}/${model} liberado correctamente.`, "green");
                setLlmProvidersList((list) =>
                    list.map((p) =>
                        p.provider === provider
                            ? {
                                  ...p,
                                  models: p.models.map((m) => (m.model === model ? { ...m, loaded: false } : m)),
                              }
                            : p
                    )
                );
            } else {
                showToast("Error al liberar modelo", message, "red");
            }
        } else {
            showToast("Error al liberar modelo", response.data.detail, "red");
        }
    };

    const onActivate = async (provider, model) => {
        const response = await withLoading(() =>
            llmModels.activate({
                provider,
                model,
            })
        );

        if (isResponseOk(response)) {
            const { message, success } = response.data;
            if (success) {
                showToast("Modelo activado", `${provider}/${model} activado correctamente.`, "green");
                setLlmProvidersList((list) =>
                    list.map((p) =>
                        p.provider === provider
                            ? {
                                  ...p,
                                  models: p.models.map((m) => ({
                                      ...m,
                                      active: m.model === model,
                                  })),
                              }
                            : {
                                  ...p,
                                  models: p.models.map((m) => ({ ...m, active: false })),
                              }
                    )
                );
            } else {
                showToast("Error al activar modelo", message, "red");
            }
        } else {
            showToast("Error al activar modelo", response.data.detail, "red");
        }
    };

    if (llmProvidersList === undefined) {
        return (
            <div className="d-flex align-items-center justify-content-center p-4">
                <div className="spinner-border text-primary me-3" role="status" />
                <span className="fs-5">Cargando modelos LLM...</span>
            </div>
        );
    }

    if (llmProvidersList === null) {
        return (
            <div className="alert alert-danger my-4 text-center" role="alert">
                Error al cargar los modelos LLM. Verifica la conexión o pulsa en recargar.
            </div>
        );
    }

    return (
        <div className="list-group shadow-sm">
            {llmProvidersList.map((providerData, index) => (
                <div
                    key={providerData.provider}
                    className={"card " + (index == 0 ? "mb-2" : index == llmProvidersList.length - 1 ? "mt-2" : "my-2")}
                >
                    <div className="card-header d-flex justify-content-between align-items-center">
                        <h5 className="mb-0 text-capitalize">{providerData.provider}</h5>
                        {!providerData.executed_locally && !providerData.models[0].loaded && (
                            <div className="d-flex align-items-center">
                                <LoadInputButton
                                    provider={providerData.provider}
                                    model={null}
                                    showApiInput={showApiInput[providerData.provider]}
                                    apiKey={apiKeys[providerData.provider]}
                                    needsApiKey={providerData.needs_api_key}
                                    setApiKeys={setApiKeys}
                                    onConfirmLoad={onConfirmLoad}
                                    onStartLoad={onStartLoad}
                                />
                            </div>
                        )}
                    </div>
                    <div className="card-body p-2">
                        {providerData.models.map((model) => (
                            <ModelItem
                                provider={providerData.provider}
                                executedLocally={providerData.executed_locally}
                                needsApiKey={providerData.needs_api_key}
                                model={model.model}
                                loaded={model.loaded}
                                active={model.active}
                                setApiKeys={setApiKeys}
                                showApiInput={showApiInput}
                                apiKeys={apiKeys}
                                onConfirmLoad={onConfirmLoad}
                                onStartLoad={onStartLoad}
                                onActivate={onActivate}
                                onUnload={onUnload}
                            />
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
};

export default LLMPanel;
