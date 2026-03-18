import React from "react";
import SimpleModal from "../../../components/SimpleModal";

const NotConnectedModal = ({ isOpen, handleClose }) => {
    return (
        <SimpleModal
            name="websocket-disconnected"
            title="No hay conexión"
            handleClose={handleClose}
            isOpen={isOpen}
            zIndex={105}
        >
            <p className="mb-2">No se puede realizar esta acción sin estar conectado al servidor.</p>
            <p className="mb-0 text-muted">Asegúrate de que la conexión esté activa e inténtalo de nuevo.</p>
        </SimpleModal>
    );
};

export default NotConnectedModal;
