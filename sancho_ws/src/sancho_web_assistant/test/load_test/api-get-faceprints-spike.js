import http from "k6/http";

const target = Math.round(28993 * 0.4);

export const options = {
    stages: [
        { duration: "1m", target: target },
        { duration: "1m", target: 0 },
    ],
    thresholds: {
        http_req_failed: ["rate<=0.05"],
    },
};

export default function () {
    http.get("http://localhost:7654/api/v1/faceprints", {
        headers: { Accept: "application/json" },
    });
}
