import React, { useEffect } from "react";

const ActionModal = ({
    name,
    title,
    handleClose,
    isOpen,
    action,
    buttonText = "Confirmar",
    buttonColor = "primary",
    size = "lg",
    zIndex = 100,
    children,
}) => {
    const handleAction = () => {
        action();
        handleClose();
    };

    useEffect(() => {
        document.body.style.overflow = isOpen ? "hidden" : "";
        return () => (document.body.style.overflow = "");
    }, [isOpen]);

    return (
        <div
            id={name + "-"}
            onClick={handleClose}
            className={`modal ${isOpen ? "show" : ""}`}
            style={{ display: isOpen ? "block" : "none", backgroundColor: "rgb(0.5,0.5,0.5,0.5)", zIndex: zIndex }}
            tabIndex="-1"
        >
            <div className={"my-5 modal-dialog modal-" + size} role="document" onClick={(e) => e.stopPropagation()}>
                <div className="modal-content">
                    <div className="modal-header">
                        <h5 className="modal-title" id={name + "-modal-label"}>
                            {title}
                        </h5>
                    </div>
                    <div className="modal-body">{children}</div>
                    <div className="modal-footer">
                        <button type="button" className={"btn btn-" + buttonColor} onClick={handleAction}>
                            {buttonText}
                        </button>
                        <button type="button" className="btn btn-secondary" onClick={handleClose}>
                            Cerrar
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ActionModal;
