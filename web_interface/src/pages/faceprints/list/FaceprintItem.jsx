import React from "react";

import { useNavigate } from "react-router-dom";

const FaceprintItem = ({ faceprint }) => {
    const navigate = useNavigate();

    const learning_date = new Date(faceprint.learning_date * 1000);
    const formattedDateStr = new Intl.DateTimeFormat("es-ES", {
        hour: "2-digit",
        minute: "2-digit",
        day: "numeric",
        month: "numeric",
        year: "numeric",
    }).format(learning_date);

    return (
        <div className="p-0 col-6 col-md-4 col-lg-3 mb-5 " onClick={() => navigate(`/faceprints/${faceprint.id}`)}>
            <div className="d-flex clickable clickable-1 flex-column justify-content-center align-items-center">
                <img
                    src={`data:image/jpg;base64,${faceprint.face}`}
                    alt={faceprint.name}
                    className="rounded mb-2"
                    width={196}
                    height={196}
                />

                <b>
                    {faceprint.name} (ID {faceprint.id})
                </b>
                <span className="small">{formattedDateStr}</span>
            </div>
        </div>
    );
};

export default FaceprintItem;
