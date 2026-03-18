import React from "react";

import { useWindowSize, BREAKPOINTS } from "../../../hooks/useWindowSize";
import { useChat } from "../../../contexts/ChatContext";

const ChatSidebar = ({ handleNewChat }) => {
    const { collapsed, setCollapsed } = useChat();
    const { width } = useWindowSize();

    return (
        <>
            <div className="d-flex" style={{ zIndex: "6", marginTop: "77px" }}>
                <div
                    className="sidebar bg-light border-end p-3 d-flex flex-column"
                    style={{
                        transform: collapsed ? "translateX(-16rem)" : "translateX(0)",
                        transition: "transform " + (collapsed ? "0s" : "0.3s") + " ease",
                        width: "16rem",
                        position: "fixed",
                        height: "100vh",
                        overflowX: "hidden",
                    }}
                >
                    <div>
                        <div className="d-flex justify-content-between align-items-center">
                            <span className="fw-bold fs-2" style={{ marginLeft: "12px", whiteSpace: "nowrap" }}>
                                Sancho
                            </span>

                            <button className="btn btn-light" onClick={() => setCollapsed((collapsed) => !collapsed)}>
                                <i className="bi bi-list"></i>
                            </button>
                        </div>

                        <div className="flex-column mt-3" style={{ display: collapsed ? "none" : "flex" }}>
                            <button className="btn btn-light text-start" onClick={handleNewChat}>
                                <i className="bi bi-chat-dots me-2"></i>
                                <span>Nuevo Chat</span>
                            </button>
                        </div>
                    </div>
                </div>

                {/* Manage moving chat along with sidebar*/}
                <div
                    style={{
                        width: collapsed || width < BREAKPOINTS.MD ? "0rem" : "16rem",
                        transition: "width " + (collapsed ? "0s" : "0.3s") + " ease",
                        overflow: "hidden",
                        flexShrink: 0,
                    }}
                ></div>
            </div>

            {/* Gray background */}
            <div
                className="vw-100 position-absolute"
                onClick={() => setCollapsed(true)}
                style={{
                    display: !collapsed && width < BREAKPOINTS.MD ? "block" : "none",
                    zIndex: "5",
                    height: window.innerHeight - 76,
                    bottom: 0,
                    backgroundColor: "rgba(224, 224, 224, 0.5)",
                }}
            ></div>
        </>
    );
};

export default ChatSidebar;
