import React, { useState } from "react";

import FaceprintItem from "./FaceprintItem";
import Pagination from "../../../components/Pagination";

const FaceprintList = ({ faceprints }) => {
    const [currentPage, setCurrentPage] = useState(1);
    const perPage = 12;

    const sortedData = [...faceprints].sort((a, b) => a.learning_date - b.learning_date);
    const totalPages = Math.ceil(sortedData.length / perPage);
    const pageData = sortedData.slice((currentPage - 1) * perPage, currentPage * perPage);

    return (
        <>
            <div className="row">
                {pageData && pageData.length > 0 ? (
                    pageData.map((faceprint) => <FaceprintItem key={faceprint.id} faceprint={faceprint} />)
                ) : (
                    <p className="alert alert-warning text-center">No se encontraron rostros.</p>
                )}
            </div>

            {totalPages > 1 && (
                <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} />
            )}
        </>
    );
};

export default FaceprintList;
