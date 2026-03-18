import { useEffect, useState } from "react";

export const BREAKPOINTS = {
    SM: 576,
    MD: 768,
    LG: 992,
    XL: 1200,
    XXL: 1400,
};

export const useWindowSize = () => {
    const [width, setWidth] = useState(window.innerWidth);
    const [height, setHeight] = useState(window.innerHeight);

    useEffect(() => {
        const handleResize = () => {
            setWidth(window.innerWidth);
            setHeight(window.innerHeight);
        };

        window.addEventListener("resize", handleResize);
        return () => window.removeEventListener("resize", handleResize);
    }, []);

    return { width, height };
};
