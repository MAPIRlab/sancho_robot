import { useContext, createContext, useState, useEffect, useRef } from "react";
import { useWebSocket } from "./WebSocketContext";
import { useEventBus } from "./EventBusContext";
import { useAudio } from "./AudioContext";
import { BREAKPOINTS, useWindowSize } from "../hooks/useWindowSize";

import { v4 as uuidv4 } from "uuid";
import NotConnectedModal from "../pages/chat/components/NotConnectedModal";
import ChatSettingsModal from "../pages/chat/components/ChatSettingsModal";
import { useToast } from "./ToastContext";

const ChatContext = createContext();

const defaultSettings = {
    showTechInfo: false,
    enableTTS: true,
    autoSendTranscription: false,
};

export const ChatProvider = ({ children }) => {
    const { playAudio } = useAudio();
    const { sendMessage, isConnected } = useWebSocket();
    const { subscribe } = useEventBus();
    const { width } = useWindowSize();
    const { showToast } = useToast();

    const [chatId, setChatId] = useState(uuidv4());
    const resetChatId = () => setChatId(uuidv4());

    const [messages, setMessages] = useState([]);
    const clearMessages = () => setMessages([]);
    const addHumanMessage = (message) => {
        setMessages((prevMessages) => [...prevMessages, { ...message, timestamp: Date.now(), isHuman: true }]);
    };

    const [settings, setSettings] = useState(defaultSettings); // Si futuro + sett, hacer SettingsContext
    const toggleSetting = (key) => setSettings((prev) => ({ ...prev, [key]: !prev[key] }));

    const [collapsed, setCollapsed] = useState(width < BREAKPOINTS.MD);
    const [textAreaValue, setTextAreaValue] = useState("");
    const transcriptionReqId = useRef(undefined);

    const [isOpenNCModal, setIsOpenNCModal] = useState(false);
    const [isOpenSettings, setIsOpenSettings] = useState(false);
    const openNCModal = () => setIsOpenNCModal(true);
    const openSettingsModal = () => setIsOpenSettings(true);

    useEffect(() => {
        const saved = localStorage.getItem("chatSettings");
        if (saved) setSettings(JSON.parse(saved));
    }, []);

    useEffect(() => {
        localStorage.setItem("chatSettings", JSON.stringify(settings));
    }, [settings]);

    useEffect(() => {
        const processR = (e) => {
            setMessages((prevMessages) => {
                const { intent, arguments: args, ...rest } = e;
                const updatedMessages = prevMessages.map((m) =>
                    m.isHuman && m.id === e.id ? { ...m, intent: intent, arguments: args } : m
                );

                return [...updatedMessages, { ...rest, timestamp: Date.now(), isHuman: false }];
            });
        };
        const processPT = (e) => {
            if (transcriptionReqId.current === e.id) {
                setTextAreaValue((text) => text + e.value);
                transcriptionReqId.current = undefined;
            } else if (!e.value) {
                showToast("Transcripción vacía", "El audio enviado no contenía voz reconocible.", "red");
                setMessages((prev) => prev.filter((m) => m.id !== e.id));
            } else {
                const value = { data: {}, text: e.value };
                setMessages((prev) =>
                    prev.map((m) => (m.isHuman && m.id === e.id ? { ...m, sttModel: e.model, value } : m))
                );
            }
        };
        const processAR = (e) => {
            setMessages((prevMessages) =>
                prevMessages.map((m) =>
                    !m.isHuman && m.id === e.id
                        ? { ...m, ttsModel: e.model, speaker: e.speaker, audio: e.audio, sampleRate: e.sampleRate }
                        : m
                )
            );

            playAudio(e.audio, e.sampleRate, e.id + false);
        };

        const unsubscribeR = subscribe("ROS_MESSAGE_RESPONSE", processR);
        const unsubscribePT = subscribe("ROS_MESSAGE_PROMPT_TRANSCRIPTION", processPT);
        const unsubscribeARC = subscribe("ROS_MESSAGE_AUDIO_RESPONSE", processAR);

        return () => {
            unsubscribeR();
            unsubscribePT();
            unsubscribeARC();
        };
    }, []);

    const handleAudio = async (blob) => {
        if (!isConnected) return setIsOpenNCModal(true);

        const buffer = await blob.arrayBuffer();
        const audioCtx = new AudioContext();
        const audioBuffer = await audioCtx.decodeAudioData(buffer);

        const floatData = audioBuffer.getChannelData(0);
        const int16Data = Int16Array.from(floatData, (s) => Math.max(-1, Math.min(1, s)) * 0x7fff);

        const id = uuidv4();
        const audio = Array.from(int16Data);
        const sampleRate = audioBuffer.sampleRate;

        if (settings.autoSendTranscription) {
            const message = {
                type: "AUDIO_PROMPT",
                data: { id, chatId, wantTts: settings.enableTTS, audio, sampleRate },
            };

            if (sendMessage(JSON.stringify(message))) {
                const value = { data: {}, text: undefined };
                addHumanMessage({ id, audio, sampleRate, value });
            }
        } else {
            const message = {
                type: "TRANSCRIPTION_REQUEST",
                data: { id, audio, sampleRate },
            };

            if (sendMessage(JSON.stringify(message))) {
                transcriptionReqId.current = id;
            }
        }
    };

    const handleSend = (inputMessage) => {
        if (inputMessage.length > 0) {
            const id = uuidv4();
            const wantTts = settings.enableTTS;

            const messageWithId = {
                type: "PROMPT",
                data: { id, chatId, wantTts, value: inputMessage },
            };

            if (sendMessage(JSON.stringify(messageWithId))) {
                const value = { data: {}, text: inputMessage };
                addHumanMessage({ id, value }, true);
            }
        }
    };

    return (
        <ChatContext.Provider
            value={{
                messages,
                clearMessages,
                
                collapsed,
                setCollapsed,
                textAreaValue,
                setTextAreaValue,

                settings,

                openNCModal,
                openSettingsModal,

                handleAudio,
                handleSend,
                resetChatId,
            }}
        >
            <NotConnectedModal isOpen={isOpenNCModal} handleClose={() => setIsOpenNCModal(false)} />
            <ChatSettingsModal
                isOpen={isOpenSettings}
                handleClose={() => setIsOpenSettings(false)}
                settings={settings}
                toggleSetting={toggleSetting}
            />

            {children}
        </ChatContext.Provider>
    );
};

export const useChat = () => useContext(ChatContext);
