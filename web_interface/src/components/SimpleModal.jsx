import React, { useEffect } from "react";

const SimpleModal = ({ name, title, handleClose, isOpen, size = "lg", zIndex = 100, children }) => {
    useEffect(() => {
        document.body.style.overflow = isOpen ? "hidden" : "";
        return () => (document.body.style.overflow = "");
    }, [isOpen]);

    return (
        <div
            id={name + "-"}
            onClick={handleClose}
            className={`modal ${isOpen ? "show" : ""}`}
            style={{
                display: isOpen ? "block" : "none",
                backgroundColor: "rgba(0, 0, 0, 0.5)",
                zIndex: zIndex,
                position: "fixed",
                top: 0,
                left: 0,
                width: "100%",
                height: "100%",
            }}
            tabIndex="-1"
        >
            <div
                className={`my-5 modal-dialog modal-${size}`}
                role="document"
                onClick={(e) => e.stopPropagation()}
                style={{
                    margin: "auto",
                    display: "flex",
                    alignItems: "center",
                }}
            >
                <div className="modal-content">
                    <div className="modal-header">
                        <h5 className="modal-title" id={name + "-modal-label"}>
                            {title}
                        </h5>
                        <button type="button" className="btn-close" onClick={handleClose}></button>
                    </div>
                    <div className="modal-body">{children}</div>
                    <div className="modal-footer">
                        <button type="button" className="btn btn-secondary" onClick={handleClose}>
                            Cerrar
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default SimpleModal;
