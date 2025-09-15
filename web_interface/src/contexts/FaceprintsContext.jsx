import { useContext, createContext, useState, useEffect } from "react";

import { useAPI } from "./APIContext";
import { useEventBus } from "./EventBusContext";
import { useToast } from "./ToastContext";
import { useLoadingScreen } from "../components/LoadingScreen";

import { FACEPRINT_EVENT } from "./WebSocketContext";

const FaceprintsContext = createContext();

export const FaceprintsProvider = ({ children }) => {
    const { showToast } = useToast();
    const { subscribe } = useEventBus();
    const { faceprints, isResponseOk } = useAPI();
    const { withLoading } = useLoadingScreen();

    const [faceprintsData, setFaceprints] = useState([]);
    const [loadingFaceprints, setLoadingFaceprints] = useState(true);

    const getFaceprint = (id) => faceprintsData.find((item) => item.id == id);
    const addFaceprint = (fc) => setFaceprints((prev) => [...prev, fc]);
    const updateFaceprint = (id, fc) => setFaceprints((prev) => prev.map((item) => (item.id === id ? fc : item)));
    const deleteFaceprint = (id) => setFaceprints((prev) => prev.filter((item) => item.id !== id));

    const fetchFaceprintsData = async () => {
        setLoadingFaceprints(true);

        const response = await faceprints.getAll();
        if (isResponseOk(response)) {
            setFaceprints(response.data);
        } else {
            showToast("Error al cargar faceprints", "No se han podido cargar los datos", "red");
        }

        setLoadingFaceprints(false);
    };

    useEffect(() => {
        fetchFaceprintsData();
    }, []);

    useEffect(() => {
        const processEvent = async (e) => {
            if (e.event === FACEPRINT_EVENT.CREATE || e.event === FACEPRINT_EVENT.UPDATE) {
                const response = await faceprints.getById(e.id);
                if (isResponseOk(response)) {
                    if (e.event === FACEPRINT_EVENT.CREATE) {
                        addFaceprint(response.data);

                        const name = response.data.name;
                        showToast("Nueva persona aprendida", "Se ha aprendido a la persona " + name, "green");
                    } else {
                        updateFaceprint(e.id, response.data);
                    }
                } else {
                    showToast("Error", response.data.detail, "red");
                }
            } else if (e.event === FACEPRINT_EVENT.DELETE) {
                const faceprint = faceprintsData.find((item) => item.id == e.id);
                const name = faceprint ? `${faceprint.name} (ID ${faceprint.id})` : `con id ${e.id}`;

                deleteFaceprint(e.id);
                showToast("Persona eliminada", "Se ha eliminado a la persona " + name, "green");
            }
        };

        const unsubscribe = subscribe("ROS_MESSAGE_FACEPRINT_EVENT", processEvent);
        return () => unsubscribe();
    }, []);

    const doAddFaceprint = async (name, base64Image) => {
        const response = await withLoading(() =>
            faceprints.create({
                name: name,
                image: base64Image,
            })
        );

        if (isResponseOk(response)) {
            addFaceprint(response.data);
            showToast(
                "Éxito",
                `La cara ha sido procesada y se ha aprendido a ${response.data.name} correctamente.`,
                "green"
            );
        } else {
            showToast("Error", response.data.detail, "red");
        }

        return response;
    };

    const doUpdateFaceprint = async (id, newName) => {
        const response = await withLoading(() => faceprints.update(id, { name: newName }));
        if (isResponseOk(response)) {
            updateFaceprint(id, response.data);
            showToast("Persona editada", "Has editado a la persona " + newName + " satisfactoriamente", "green");
        } else {
            showToast("Error", response.data.detail, "red");
        }

        return response;
    };

    const doDeleteFaceprint = async (id) => {
        const response = await withLoading(() => faceprints.delete(id));
        if (isResponseOk(response)) {
            const faceprint = faceprintsData.find((item) => item.id == id);
            const name = faceprint ? `${faceprint.name} (ID ${faceprint.id})` : `con id ${id}`;

            deleteFaceprint(id);
            showToast("Persona eliminada", "Has eliminado a la persona " + name + " satisfactoriamente", "green");
        } else {
            showToast("Error", response.data.detail, "red");
        }

        return response;
    };

    return (
        <FaceprintsContext.Provider
            value={{
                getFaceprint,

                doAddFaceprint,
                doUpdateFaceprint,
                doDeleteFaceprint,

                fetchFaceprintsData,

                loadingFaceprints,
                faceprintsData,
            }}
        >
            {children}
        </FaceprintsContext.Provider>
    );
};

export const useFaceprints = () => useContext(FaceprintsContext);
