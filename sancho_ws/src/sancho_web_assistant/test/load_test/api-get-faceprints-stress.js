import http from "k6/http";

const average = Math.round(28993 * 0.8);

export const options = {
    stages: [
        { duration: "3m", target: average },
        { duration: "3m", target: average },
        { duration: "2m", target: 0 },
    ],
    thresholds: {
        http_req_failed: [
            { threshold: "rate <= 0.01", abortOnFail: true }, // menos del 1% de errores
        ],
        http_req_duration: [
            { threshold: "avg <= 5000", abortOnFail: true }, // respuesta media < 5s
        ],
    },
};

export default function () {
    http.get("http://localhost:7654/api/v1/faceprints", {
        headers: { Accept: "application/json" },
    });
}
