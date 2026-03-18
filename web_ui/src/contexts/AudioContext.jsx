import { createContext, useContext, useRef, useState } from "react";

const AudioContextReact = createContext();

export const AudioProvider = ({ children }) => {
    const currentAudioRef = useRef(null);
    const currentSourceRef = useRef(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [activeAudioId, setActiveAudioId] = useState(null);

    const stopCurrentAudio = () => {
        if (currentSourceRef.current) {
            try {
                currentSourceRef.current.stop();
            } catch (_) {}
            currentSourceRef.current.disconnect();
            currentSourceRef.current = null;
        }
        if (currentAudioRef.current) {
            currentAudioRef.current.close();
            currentAudioRef.current = null;
        }
        setIsPlaying(false);
        setActiveAudioId(null);
    };

    const playAudio = (audio, sampleRate, audioId = null) => {
        stopCurrentAudio();

        const context = new window.AudioContext({ sampleRate });
        const float32 = new Float32Array(audio.length);
        for (let i = 0; i < audio.length; i++) {
            float32[i] = Math.max(-1, Math.min(1, audio[i] / 32768));
        }

        const buffer = context.createBuffer(1, float32.length, sampleRate);
        buffer.copyToChannel(float32, 0);

        const source = context.createBufferSource();
        source.buffer = buffer;
        source.connect(context.destination);

        source.start();

        currentAudioRef.current = context;
        currentSourceRef.current = source;
        setIsPlaying(true);
        setActiveAudioId(audioId);

        source.onended = () => {
            stopCurrentAudio();
        };

        return () => stopCurrentAudio();
    };

    return (
        <AudioContextReact.Provider
            value={{
                playAudio,
                stopCurrentAudio,
                isPlaying,
                activeAudioId,
            }}
        >
            {children}
        </AudioContextReact.Provider>
    );
};

export const useAudio = () => useContext(AudioContextReact);
