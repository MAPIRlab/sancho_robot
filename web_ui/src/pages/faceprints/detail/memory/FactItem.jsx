import React from "react";

const FactItem = ({ text, isEditing, canEdit, onStartEdit, onCancelEdit, onConfirmEdit, onDelete, tempValue, setTempValue }) => {
    return (
        <li className="list-group-item d-flex align-items-center py-3">
            <div className="flex-grow-1 me-3">
                {isEditing ? (
                    <input
                        type="text"
                        className="form-control form-control-sm"
                        value={tempValue}
                        placeholder="Edita el fact…"
                        onChange={(e) => setTempValue(e.target.value)}
                    />
                ) : (
                    <div className="fw-semibold text-wrap" title={text}>
                        {text}
                    </div>
                )}
            </div>

            {/* Acciones siempre a la derecha y con ancho fijo */}
            <div className="d-flex justify-content-end ms-auto">
                <div className="btn-group btn-group-sm">
                    {canEdit ? (
                        isEditing ? (
                            <>
                                <button className="btn btn-success" onClick={onConfirmEdit} title="Confirmar">
                                    <i className="bi bi-check-lg" />
                                </button>
                                <button className="btn btn-outline-secondary" onClick={onCancelEdit} title="Cancelar">
                                    <i className="bi bi-x-lg" />
                                </button>
                                <button className="btn btn-outline-danger" onClick={onDelete} title="Eliminar">
                                    <i className="bi bi-trash" />
                                </button>
                            </>
                        ) : (
                            <>
                                <button className="btn btn-outline-primary" onClick={onStartEdit} title="Editar">
                                    <i className="bi bi-pencil-square" />
                                </button>
                                <button className="btn btn-outline-danger" onClick={onDelete} title="Eliminar">
                                    <i className="bi bi-trash" />
                                </button>
                            </>
                        )
                    ) : (
                        <>
                            <button className="btn btn-outline-primary invisible">
                                <i className="bi bi-pencil-square" />
                            </button>
                            <button className="btn btn-outline-danger invisible">
                                <i className="bi bi-trash" />
                            </button>
                            <button className="btn btn-success invisible">
                                <i className="bi bi-check-lg" />
                            </button>
                        </>
                    )}
                </div>
            </div>
        </li>
    );
}

export default FactItem;