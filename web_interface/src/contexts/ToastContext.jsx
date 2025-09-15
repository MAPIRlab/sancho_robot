import { useContext, createContext, useState } from "react";

const ToastContext = createContext();

export const ToastProvider = ({ children }) => {
    const [toasts, setToasts] = useState([]);

    const showToast = (title, subtitle, color) => {
        const id = Date.now(); // ID único para cada toast
        const newToast = { id, title, subtitle, color };

        setToasts((prevToasts) => [...prevToasts, newToast]);

        // Eliminar el toast después de 5 segundos
        setTimeout(() => {
            setToasts((prevToasts) => prevToasts.filter((toast) => toast.id !== id));
        }, 5000);
    };

    const removeToast = (id) => {
        setToasts((prevToasts) => prevToasts.filter((toast) => toast.id !== id));
    };

    return (
        <ToastContext.Provider
            value={{
                showToast,
            }}
        >
            <div
                className="toast-container position-fixed bottom-0 end-0 p-3"
                style={{
                    zIndex: 1055,
                    maxWidth: "90%", // Para pantallas móviles
                }}
            >
                {toasts.map((toast) => (
                    <div
                        key={toast.id}
                        className="toast show align-items-center text-bg-light border-0 mb-2"
                        role="alert"
                    >
                        <div className="d-flex">
                            <div className="toast-body">
                                <div className="d-flex align-items-start">
                                    {toast.color && (
                                        <div
                                            className="me-2"
                                            style={{
                                                width: "16px",
                                                height: "16px",
                                                minWidth: "16px",
                                                minHeight: "16px",
                                                backgroundColor: toast.color,
                                            }}
                                        ></div>
                                    )}
                                    <div>
                                        <strong className="mt-0">{toast.title}</strong>
                                        <div>{toast.subtitle}</div>
                                    </div>
                                </div>
                            </div>
                            <button
                                type="button"
                                className="btn-close me-2 m-auto"
                                aria-label="Close"
                                onClick={() => removeToast(toast.id)}
                            ></button>
                        </div>
                    </div>
                ))}
            </div>

            {children}
        </ToastContext.Provider>
    );
};

export const useToast = () => useContext(ToastContext);
