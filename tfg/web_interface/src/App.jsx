import { BrowserRouter as Router, Route, Routes, Navigate } from "react-router-dom";

import Header from "./components/Header";
import Footer from "./components/Footer";
import HomePage from "./pages/home/HomePage";
import ChatPage from "./pages/chat/ChatPage";
import FaceprintListPage from "./pages/faceprints/FaceprintListPage";
import FaceprintDetailPage from "./pages/faceprints/FaceprintDetailPage";

import WebSocketVideoViewer from "./components/WebSocketVideoViewer";
import LoadingScreen from "./components/LoadingScreen";
import ModelsPage from "./pages/models/ModelsPage";
import LogsPage from "./pages/logs_page/LogsPage";

const App = () => {
    const wrap = (page) => (
        <div className="d-flex flex-column min-vh-100">
            <Header />
            <main className="flex-grow-1">{page}</main>
            {false && <Footer />}
        </div>
    );

    return (
        <Router>
            <WebSocketVideoViewer />
            <LoadingScreen />

            <Routes>
                <Route path="/" element={wrap(<HomePage />)} />
                <Route path="/chat" element={wrap(<ChatPage />)} />
                <Route path="/faceprints" element={wrap(<FaceprintListPage />)} />
                <Route path="/faceprints/:id" element={wrap(<FaceprintDetailPage />)} />
                <Route path="/models" element={wrap(<ModelsPage />)} />
                <Route path="/logs" element={wrap(<LogsPage />)} />
                <Route path="*" element={<Navigate to="/" />} />
            </Routes>
        </Router>
    );
};

export default App;
