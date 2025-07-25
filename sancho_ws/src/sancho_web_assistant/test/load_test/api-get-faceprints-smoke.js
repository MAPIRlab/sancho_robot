import http from "k6/http";
import { check } from "k6";

export const options = {
    vus: 5,
    duration: "1m",
    thresholds: {
        http_req_failed: ["rate==0"],
        http_req_duration: ["avg<200"],
    },
};

export default function () {
    const res = http.get("http://localhost:7654/api/v1/faceprints", {
        headers: { Accept: "application/json" },
    });
    
    check(res, {
        "status is 200": (r) => r.status === 200,
    });
}
