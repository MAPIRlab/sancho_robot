import React from "react";
import { Line } from "react-chartjs-2";
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Filler,
} from "chart.js";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Filler);

const formatDuration = (start, end) => {
    const seconds = (end - start).toFixed(0);
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;

    if (hours > 0) return `${hours}h ${remainingMinutes}m ${remainingSeconds}s`;
    if (minutes > 0) return `${minutes}m ${remainingSeconds}s`;
    return `${seconds}s`;
};

const downsample = (arr, maxPoints) => {
    if (arr.length <= maxPoints) return arr;
    const ratio = Math.ceil(arr.length / maxPoints);
    return arr.filter((_, i) => i % ratio === 0);
};

const ScoresChart = ({ times, scores, label }) => {
    const maxPoints = 500;

    const sampledTimes = downsample(times, maxPoints).map((t) => parseFloat(t.toFixed(1)));
    const sampledScores = downsample(scores, maxPoints);

    const chartData = {
        labels: sampledTimes.map((s) => formatDuration(0, s)),
        datasets: [
            {
                label,
                data: sampledScores,
                fill: "origin",
                backgroundColor: "rgba(2, 117, 216, 0.15)",
                borderColor: "rgba(2, 117, 216, 1)",
                borderWidth: 3,
                pointRadius: 2,
                pointBackgroundColor: "#ffffff",
            },
        ],
    };

    const minY = label === "Clasificación"
        ? Math.max(0, Math.min(...sampledScores) - 0.01)
        : 0;

    const options = {
        responsive: true,
        maintainAspectRatio: false,
        tension: 0.3,
        plugins: {
            legend: {
                display: true,
                position: "top",
            },
            tooltip: {
                mode: "index",
                intersect: false,
                callbacks: {
                    label: function (context) {
                        const value = context.raw != null ? context.raw.toFixed(3) : "";
                        return `${label}: ${value}`;
                    },
                },
            },
        },
        scales: {
            x: {
                title: {
                    display: true,
                    text: "Tiempo transcurrido",
                    color: "#444",
                    font: { weight: "bold", size: 14 },
                },
                ticks: {
                    color: "#444",
                    font: { weight: "bold", size: 12 },
                },
                grid: {
                    color: "rgba(255,255,255,0.2)",
                },
            },
            y: {
                min: minY,
                beginAtZero: false,
                title: {
                    display: true,
                    text: "Puntuación",
                    color: "#444",
                    font: { weight: "bold", size: 14 },
                },
                ticks: {
                    color: "#444",
                    font: { weight: "bold", size: 12 },
                },
                grid: {
                    color: "rgba(255,255,255,0.2)",
                },
            },
        },
        interaction: {
            mode: "index",
            intersect: false,
        },
    };


    return <Line data={chartData} options={options} />;
};

export default ScoresChart;
