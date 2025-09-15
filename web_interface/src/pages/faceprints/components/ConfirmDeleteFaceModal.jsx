import React from "react";

import ActionModal from "../../../components/ActionModal";

const ConfirmDeleteFaceModal = ({ faceprint, isOpen, handleClose, action }) => {
    return (
        <ActionModal
            name={"confirm-delete-faceprint"}
            title={"Eliminar rostro"}
            isOpen={isOpen}
            handleClose={handleClose}
            action={action}
            buttonText={"Borrar"}
            buttonColor={"danger"}
        >
            <span>
                ¿Estás seguro de que quieres eliminar el rostro de{" "}
                <b>
                    {faceprint.name} (ID {faceprint.id})
                </b>
                ?
            </span>
        </ActionModal>
    );
};

export default ConfirmDeleteFaceModal;
