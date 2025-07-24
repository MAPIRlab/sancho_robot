import React from "react";

const style = {
    position: "fixed",
    top: "0",
    left: "0",
    width: "100%",
    height: "100%",
    backgroundColor: "rgba(0, 0, 0, 0.5)",
    zIndex: "9999",
    display: "none",
    color: "white",
};

export default function LoadingScreen() {
    return (
        <div id="loading-screen" style={{ display: "none" }}>
            <div className="d-flex flex-column justify-content-center align-items-center" style={style}>
                <div className="spinner-border" style={{ width: "100px", height: "100px" }} role="status">
                    <span className="visually-hidden">Cargando...</span>
                </div>
            </div>
        </div>
    );
}

export const useLoadingScreen = () => {
    const showLoadingScreen = () => (document.getElementById("loading-screen").style.display = "block");
    const hideLoadingScreen = () => (document.getElementById("loading-screen").style.display = "none");
    const withLoading = async (action) => {
        showLoadingScreen();
        try {
            return await action();
        } finally {
            hideLoadingScreen();
        }
    };

    return { showLoadingScreen, hideLoadingScreen, withLoading };
};
