import React, { useRef, useEffect, forwardRef, useImperativeHandle } from "react";
import { useChat } from "../../../contexts/ChatContext";

const ChatTextArea = forwardRef(({ onSend }, ref) => {
    const { textAreaValue, setTextAreaValue } = useChat();
    const textAreaRef = useRef(null);

    useImperativeHandle(ref, () => ({
        send: () => handleSend(),
        clear: () => clearInput(),
        focus: () => focusTextArea(),
        getValue: () => textAreaValue,
    }));

    const handleSend = () => {
        onSend(textAreaValue);
        clearInput();
    };

    const clearInput = () => {
        setTextAreaValue("");
        textAreaRef.current.style.height = "40px";
    };

    const focusTextArea = () => {
        textAreaRef.current?.focus();
        textAreaRef.current?.setSelectionRange(textAreaValue.length, textAreaValue.length);
    };

    const handleChange = (event) => setTextAreaValue(event.target.value);
    const handleKeyDown = (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            handleSend();
        }
    };

    useEffect(() => {
        if (textAreaRef.current) {
            textAreaRef.current.style.height = "40px";
            textAreaRef.current.style.height = `${textAreaRef.current.scrollHeight}px`;
        }
    }, [textAreaValue]);

    return (
        <>
            <textarea
                ref={textAreaRef}
                value={textAreaValue}
                className="chat-textarea"
                placeholder="Escribe un mensaje..."
                onChange={handleChange}
                onKeyDown={handleKeyDown}
                rows="2"
            />

            <style>{`
                    .chat-textarea {
                        resize: none;
                        overflow-y: auto;
                        min-height: 40px;
                        max-height: 150px;
                        border: none;
                        outline: none;
                        width: 100%;
                        padding: 8px;
                        font-size: 14px;
                    }
                    .chat-textarea:focus {
                        box-shadow: none !important;
                    }
                `}</style>
        </>
    );
});

export default ChatTextArea;
