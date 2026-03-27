import React, { createContext, useContext, useEffect, useRef, useState } from "react";
import { useToast } from "./ToastContext";
import { useAPI } from "./APIContext";
import { useWebSocket } from "./WebSocketContext";

const ModelsContext = createContext();

export const ModelsProvider = ({ children }) => {
    const { isConnected } = useWebSocket();
    const { ttsModels, sttModels, llmModels, isResponseOk } = useAPI();
    const { showToast } = useToast();

    const [activeTab, setActiveTab] = useState("tts");
    const [ttsModelsList, setTtsModelsList] = useState(undefined);
    const [sttModelsList, setSttModelsList] = useState(undefined);
    const [llmProvidersList, setLlmProvidersList] = useState(undefined);

    const getActiveTtsModel = () => {
        if (ttsModelsList === undefined || ttsModelsList === null) return ttsModelsList;
        const active = ttsModelsList.find((m) => m.active);
        return active || "";
    };

    const getActiveSttModel = () => {
        if (sttModelsList === undefined || sttModelsList === null) return sttModelsList;
        const active = sttModelsList.find((m) => m.active);
        return active || "";
    };

    const getActiveLlmModel = () => {
        if (llmProvidersList === undefined || llmProvidersList === null) return llmProvidersList;

        const active = llmProvidersList.flatMap((p) =>
            p.models.filter((m) => m.active).map((m) => ({ ...p, ...m }))
        )[0];

        return active || "";
    };

    const buildFetchFunc = (kind, apiObj, setFunc) => {
        return async () => {
            setFunc(undefined);

            const response = await apiObj.getAll();
            if (isResponseOk(response)) {
                setFunc(response.data);
            } else {
                setFunc(null);
                showToast("Error al obtener modelos " + kind.toUpperCase(), "No se han podido cargar los datos", "red");
            }
        };
    };

    const fetchFunctions = {
        tts: buildFetchFunc("tts", ttsModels, setTtsModelsList),
        stt: buildFetchFunc("stt", sttModels, setSttModelsList),
        llm: buildFetchFunc("llm", llmModels, setLlmProvidersList),
    };

    const firstRun = useRef(true);
    const wasConnected = useRef(false);
    useEffect(() => {
        if (firstRun.current || (wasConnected.current && isConnected == false))
            Object.values(fetchFunctions).forEach((f) => f());

        firstRun.current = false;
        wasConnected.current = isConnected;
    }, [isConnected]);

    return (
        <ModelsContext.Provider
            value={{
                activeTab,
                setActiveTab,

                getActiveTtsModel,
                getActiveSttModel,
                getActiveLlmModel,

                ttsModelsList,
                setTtsModelsList,
                sttModelsList,
                setSttModelsList,
                llmProvidersList,
                setLlmProvidersList,

                fetchFunctions,
            }}
        >
            {children}
        </ModelsContext.Provider>
    );
};
export const useModels = () => useContext(ModelsContext);
