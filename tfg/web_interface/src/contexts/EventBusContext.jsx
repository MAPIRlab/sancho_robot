import React, { createContext, useContext, useRef } from "react";

const EventBusContext = createContext();

export const EventBusProvider = ({ children }) => {
    const subscribersRef = useRef(new Map());

    const subscribe = (eventName, callback) => {
        if (!subscribersRef.current.has(eventName)) {
            subscribersRef.current.set(eventName, new Set());
        }
        subscribersRef.current.get(eventName).add(callback);

        return () => {
            subscribersRef.current.get(eventName)?.delete(callback);
            if (subscribersRef.current.get(eventName)?.size === 0) {
                subscribersRef.current.delete(eventName);
            }
        };
    };

    const publish = (eventName, payload) => {
        const callbacks = subscribersRef.current.get(eventName);
        if (callbacks) {
            callbacks.forEach((cb) => cb(payload));
        }
    };

    return (
        <EventBusContext.Provider
            value={{
                publish,
                subscribe,
            }}
        >
            {children}
        </EventBusContext.Provider>
    );
};

export const useEventBus = () => useContext(EventBusContext);
