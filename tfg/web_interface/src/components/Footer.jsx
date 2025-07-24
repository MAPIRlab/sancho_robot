import React from "react";

const Footer = () => {
    return (
        <footer className="bg-body-tertiary text-center py-3 border-top mt-auto">
            <div className="container">
                <span className="text-muted small">
                    © {new Date().getFullYear()} SanchoUI · Proyecto de Fin de Grado · Desarrollado por Eulogio Quemada
                    Tores
                </span>
            </div>
        </footer>
    );
};

export default Footer;
