import http from "k6/http";

export const options = {
  scenarios: {
    breakpoint: {
      executor: "ramping-arrival-rate", // Executor que incrementa la carga
      preAllocatedVUs: 0, // Queremos encontrar el breakpoint y como no sabemos cual es, empezamos en 0
      maxVUs: 1e7, // Maximos VUs
      stages: [{ duration: "10m", target: 100000 }],
    },
  },
  thresholds: {
    http_req_failed: [
      {
        threshold: "rate<=0.01",
        abortOnFail: true,
      },
    ],
  },
};

export default function () {
    http.get("http://localhost:7654/api/v1/faceprints", {
        headers: { Accept: "application/json" },
    });
}
