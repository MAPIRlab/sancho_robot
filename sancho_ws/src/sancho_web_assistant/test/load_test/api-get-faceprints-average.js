import http from "k6/http";

const target = Math.round(28993 * 0.5);

export const options = {
    stages: [
        { duration: "3m", target: target },
        { duration: "3m", target: target },
        { duration: "2m", target: 0 },
    ],
    thresholds: {
        http_req_failed: [
            { threshold: "rate <= 0.025", abortOnFail: true },
        ],
        http_req_duration: [
            { threshold: "avg <= 500" },
        ],
    },
};

export default function () {
    http.get("http://localhost:7654/api/v1/faceprints", {
        headers: { Accept: "application/json" },
    });
}
