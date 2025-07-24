import React, { useState } from "react";

import SessionItem from "./SessionItem";
import Pagination from "../../../components/Pagination";
import SessionModal from "./SessionModal";

const SessionList = ({ faceprint, sessions }) => {
    const [selectedSessionId, setSelectedSessionId] = useState(undefined);

    const [currentPage, setCurrentPage] = useState(1);
    const perPage = 5;

    const sortedData = [...sessions].sort((a, b) => a.start_time - b.start_time);
    const totalPages = Math.ceil(sortedData.length / perPage);
    const pageData = sortedData.slice((currentPage - 1) * perPage, currentPage * perPage);

    return (
        <>
            <SessionModal
                handleClose={() => setSelectedSessionId(undefined)}
                isOpen={selectedSessionId !== undefined}
                session={sessions.find((session) => session.id == selectedSessionId)}
            />

            <div className="row">
                {pageData && pageData.length > 0 ? (
                    pageData.map((session) => (
                        <SessionItem
                            key={session.id}
                            session={session}
                            onClick={() => setSelectedSessionId(session.id)}
                        />
                    ))
                ) : (
                    <div className="alert alert-warning" role="alert">
                        No hay ninguna sesion registrada para {faceprint.name} (ID {faceprint.id}).
                    </div>
                )}
            </div>

            {totalPages > 1 && (
                <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} />
            )}
        </>
    );
};

export default SessionList;
