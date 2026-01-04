import React, { useEffect, useRef, useState } from "react";
import { useWindowSize, BREAKPOINTS } from "../hooks/useWindowSize";

const DraggableItem = ({ children, childrenWidth, childrenHeight }) => {
    const { width, height } = useWindowSize();

    const [isClosed, setIsClosed] = useState(false);
    const [position, setPosition] = useState({ x: 32, y: 32 });

    const draggingRef = useRef(false);
    const offsetRef = useRef({ x: 0, y: 0 });
    const childrenSizeRef = useRef({ width: 0, height: 0 });

    const handleMouseDown = (e) => {
        e.preventDefault();
        draggingRef.current = true;

        offsetRef.current = {
            x: e.clientX - position.x,
            y: e.clientY - position.y,
        };

        childrenSizeRef.current = {
            width: e.target.width + 8,
            height: e.target.height + 8,
        };
    };

    const handleMouseMove = (e) => {
        if (draggingRef.current) {
            const newX = e.clientX - offsetRef.current.x;
            const newY = e.clientY - offsetRef.current.y;

            const sizeX = childrenSizeRef.current.width;
            const sizeY = childrenSizeRef.current.height;

            setPosition({
                x: Math.min(Math.max(newX, 0), window.innerWidth - sizeX),
                y: Math.min(Math.max(newY, 0), window.innerHeight - sizeY),
            });
        }
    };

    const handleMouseUp = () => {
        draggingRef.current = false;
    };

    useEffect(() => {
        setPosition((oldPosition) => {
            const sizeX = childrenSizeRef.current.width;
            const sizeY = childrenSizeRef.current.height;

            const newX = oldPosition.x > width - sizeX ? width - sizeX : oldPosition.x;
            const newY = oldPosition.y > height - sizeY ? height - sizeY : oldPosition.y;

            return { x: newX, y: newY };
        });
    }, [width, height]);

    useEffect(() => {
        window.addEventListener("mousemove", handleMouseMove);
        window.addEventListener("mouseup", handleMouseUp);

        return () => {
            window.removeEventListener("mousemove", handleMouseMove);
            window.removeEventListener("mouseup", handleMouseUp);
        };
    }, []);

    return (
        <>
            {!isClosed && (
                <div
                    onMouseDown={handleMouseDown}
                    style={{
                        zIndex: 90 /*40 * (width < BREAKPOINTS.MD ? 1 : 10),*/,
                        objectFit: "contain",
                        position: "fixed",
                        top: position.y,
                        left: position.x,
                        cursor: draggingRef.current ? "grabbing" : "move",
                        userSelect: "none",
                    }}
                >
                    <div
                        style={{
                            position: "fixed",
                            top: position.y + 5,
                            left: position.x + (childrenWidth ? childrenWidth : 0) - 30,
                        }}
                    >
                        <button
                            className="btn btn-danger p-0 m-0"
                            onClick={() => setIsClosed(true)}
                            style={{
                                width: 25,
                                height: 25,
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                            }}
                        >
                            <i className="bi bi-x" style={{ color: "white", fontSize: 20 }}></i>
                        </button>
                    </div>

                    {children}
                </div>
            )}
        </>
    );
};

export default DraggableItem;
