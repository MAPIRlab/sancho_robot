import React, { useRef, useState, useEffect } from "react";

import SimpleModal from "../../../components/SimpleModal";

import { useToast } from "../../../contexts/ToastContext";
import { useCamera } from "../../../hooks/useCamera";
import { useNavigate } from "react-router-dom";
import { useAPI } from "../../../contexts/APIContext";

const NewFaceprintModal = ({ handleClose, isOpen, doAddFaceprint }) => {
    const { videoRef, isActive: usingCamera, startCamera, stopCamera, takePhoto } = useCamera();
    const { showToast } = useToast();
    const { isResponseOk } = useAPI();

    const navigate = useNavigate();

    const [name, setName] = useState("");
    const [selectedImage, setSelectedImage] = useState(undefined);

    const fileInputRef = useRef(null);

    const handleFileChange = (e) => {
        const file = e.target.files[0];
        if (file && file.type.startsWith("image/")) {
            setSelectedImage(file);
            stopCamera();
        } else {
            showToast("Archivo no válido", "Solo se permiten imágenes", "red");
        }
    };

    const handleTakePhoto = async () => {
        const photo = await takePhoto();
        if (photo) {
            setSelectedImage(photo);
            stopCamera();
        }
    };

    const convertToBase64 = (file) => {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    };

    const uploadFace = async () => {
        const trimmedName = name.trim();

        if (!selectedImage) {
            showToast("Imagen requerida", "Por favor, selecciona una imagen.", "red");
            return;
        }

        if (!trimmedName) {
            showToast("Nombre requerido", "Por favor, introduce un nombre válido.", "red");
            return;
        }

        try {
            const base64Image = await convertToBase64(selectedImage);
            const response = await doAddFaceprint(trimmedName, base64Image);

            cleanAndClose();
            if (isResponseOk(response)) navigate(`/faceprints/${response.data.id}`)
        } catch (error) {
            const errorMsg = error?.response?.data?.detail || error?.message || "Error inesperado al subir la cara.";
            showToast("Error", errorMsg, "red");
        }
    };

    const cleanAndClose = () => {
        handleClose();
        setName("");
        setSelectedImage(undefined);
        if (fileInputRef.current) fileInputRef.current.value = null;
        stopCamera();
    };

    useEffect(() => {
        if (!isOpen) {
            cleanAndClose();
        }
    }, [isOpen]);

    return (
        <SimpleModal
            name="upload-face"
            title="Subir nueva cara"
            handleClose={cleanAndClose}
            isOpen={isOpen}
            zIndex={100}
        >
            <div className="mb-3">
                <label htmlFor="nameInput" className="form-label">Nombre</label>
                <input
                    type="text"
                    id="nameInput"
                    className="form-control"
                    placeholder="Introduce un nombre"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                />
            </div>

            {!usingCamera && (
                <div className="mb-3 d-flex gap-2">
                    <label htmlFor="fileInput" className="btn btn-secondary w-50">
                        Seleccionar imagen
                    </label>
                    <button className="btn btn-secondary w-50" onClick={startCamera}>
                        Usar cámara
                    </button>
                    <input
                        ref={fileInputRef}
                        id="fileInput"
                        type="file"
                        className="form-control visually-hidden"
                        accept="image/*"
                        onChange={handleFileChange}
                    />
                </div>
            )}

                <div className="mb-3 text-center" style={{display: usingCamera ? "block" : "none"}}>
                    <div style={{ position: "relative", width: "100%", paddingTop: "56.25%" }}>
                        <video
                            ref={videoRef}
                            muted
                            playsInline
                            autoPlay
                            style={{
                                position: "absolute",
                                top: 0,
                                left: 0,
                                width: "100%",
                                height: "100%",
                                objectFit: "contain",
                                borderRadius: "8px",
                                backgroundColor: "#000"
                            }}
                        />
                    </div>
                    <button className="btn btn-secondary mt-2 me-2" onClick={stopCamera}>
                        Volver
                    </button>
                    <button className="btn btn-primary mt-2" onClick={handleTakePhoto}>
                        Tomar foto
                    </button>
                </div>

            {selectedImage ? (
                <div className="d-flex flex-column align-items-center">
                    <img
                        src={URL.createObjectURL(selectedImage)}
                        alt="Vista previa"
                        style={{
                            minWidth: "256px",
                            maxWidth: "256px",
                            objectFit: "cover",
                            border: "1px solid #ddd",
                            borderRadius: "4px",
                            marginBottom: "8px",
                        }}
                    />
                    <span>{selectedImage.name}</span>
                </div>
            ) : (
                !usingCamera && <span style={{ color: "#aaa" }}>Ninguna imagen seleccionada</span>
            )}

            <button className="btn btn-primary mt-3 w-100" onClick={uploadFace}>
                Subir cara
            </button>
        </SimpleModal>
    );
};

export default NewFaceprintModal;
