import React, { useRef } from "react";

import ChatSidebar from "./components/ChatSidebar";
import ChatFooter from "./components/ChatFooter";
import ChatMessageArea from "./components/ChatMessageArea";
import ChatHeader from "./components/ChatHeader";

import { useWindowSize, BREAKPOINTS } from "../../hooks/useWindowSize";
import { useChat } from "../../contexts/ChatContext";

const ChatPage = () => {
    const { setCollapsed, clearMessages, resetChatId } = useChat();
    const { width } = useWindowSize();

    const chatAreaRef = useRef(null);

    const handleNewChat = () => {
        clearMessages();
        resetChatId();
        
        chatAreaRef.current?.clear();
        if (width < BREAKPOINTS.MD) setCollapsed(true);
    };

    return (
        <>
            <div className="d-flex vh-100">
                <ChatSidebar handleNewChat={handleNewChat} />

                <div className="d-flex flex-column flex-grow-1" style={{ overflow: "hidden", marginTop: "76px" }}>
                    <ChatHeader handleNewChat={handleNewChat} />

                    <ChatMessageArea />

                    <ChatFooter chatAreaRef={chatAreaRef} />
                </div>
            </div>
        </>
    );
};

export default ChatPage;
