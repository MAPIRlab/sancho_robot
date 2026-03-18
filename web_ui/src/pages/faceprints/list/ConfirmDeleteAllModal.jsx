import ActionModal from "../../../components/ActionModal";

const ConfirmDeleteAllModal = ({ isOpen, handleClose, action }) => {
    return (
        <ActionModal
            name={"confirm-delete-all-faceprints"}
            title={"Eliminar base de datos"}
            isOpen={isOpen}
            handleClose={handleClose}
            action={action}
            buttonText={"Borrar"}
            buttonColor={"danger"}
        >
            <span>
                ¿Estás seguro de que quieres eliminar toda la base de datos?
            </span>
        </ActionModal>
    );
};

export default ConfirmDeleteAllModal;
