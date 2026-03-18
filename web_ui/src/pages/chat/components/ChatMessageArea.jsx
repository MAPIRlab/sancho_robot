import React, { useRef, useEffect, useState, useMemo } from "react";
import ChatMessage from "./ChatMessage";
import ChatMessageModal from "./ChatMessageModal";
import { useChat } from "../../../contexts/ChatContext";

const greetings = [
    "¡Hola! Soy Sancho.",
    "¡Encantado de verte! Soy Sancho.",
    "¡Buenas! Soy tu asistente Sancho.",
    "¡Eh! ¿Hablamos un rato?",
    "¡Sancho está en línea!",
];

const prompts = [
    "¿Qué tal estás hoy?",
    "¿En qué puedo ayudarte?",
    "¿Te apetece charlar un poco?",
    "¿Listo para hacer algo genial?",
    "¿Tienes alguna duda o idea?",
];

const getRandomItem = (array) => array[Math.floor(Math.random() * array.length)];

const ChatMessageArea = () => {
    const { messages } = useChat();
    const [selectedMessage, setSelectedMessage] = useState(undefined);

    const messagesEndRef = useRef(null);
    const firstScrollRef = useRef(false);

    const greeting = useMemo(() => getRandomItem(greetings), []);
    const prompt = useMemo(() => getRandomItem(prompts), []);

    useEffect(() => {
        if (messagesEndRef.current) {
            messagesEndRef.current.scrollIntoView({ behavior: firstScrollRef.current ? "smooth" : "auto" });
            firstScrollRef.current = true;
        }
    }, [messages]);

    if (messages.length === 0) {
        return (
            <div className="mb-4" style={{ marginTop: "20dvh" }}>
                <h2 className="text-center">{greeting}</h2>
                <p className="text-muted text-center">{prompt}</p>
            </div>
        );
    }

    return (
        <>
            <ChatMessageModal
                isOpen={selectedMessage !== undefined}
                handleClose={() => setSelectedMessage(undefined)}
                message={selectedMessage}
            />

            <div className="flex-grow-1 d-flex flex-column" style={{ backgroundColor: "white", overflow: "auto" }}>
                <div className="container px-md-5 px-4 d-flex flex-column flex-grow-1 py-3">
                    {messages.map((message, index) => (
                        <ChatMessage key={index} message={message} onSelect={() => setSelectedMessage(message)} />
                    ))}

                    <div ref={messagesEndRef} />
                </div>
            </div>
        </>
    );
};

export default ChatMessageArea;
