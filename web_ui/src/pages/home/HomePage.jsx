import { useNavigate } from "react-router-dom";
import sanchoSrc from "/sancho.jpg";

const HomePage = () => {
    const navigate = useNavigate();

    return (
        <div>
            {/* Hero principal */}
            <section className="bg-light text-center py-5 px-3 border-bottom shadow-sm" style={{ marginTop: "76px" }}>
                <div className="container">
                    <h1 className="display-4 fw-bold mb-3">
                        Bienvenido a <span className="text-primary">SanchoUI</span>
                    </h1>
                    <p className="lead text-muted mb-4">
                        Plataforma inteligente de interacción humano-robot con reconocimiento facial, conversación
                        natural y gestión remota.
                    </p>
                    <div className="d-flex flex-column flex-md-row justify-content-center">
                        <button
                            className="btn btn-primary btn-lg me-md-3 mb-3 mb-md-0"
                            onClick={() => navigate("/chat")}
                        >
                            <i className="bi bi-cpu-fill me-2"></i>Habla con Sancho
                        </button>
                        <button className="btn btn-outline-secondary btn-lg" onClick={() => navigate("/models")}>
                            <i className="bi bi-gear me-2"></i>Gestionar Modelos
                        </button>
                    </div>
                </div>
            </section>

            {/* Características clave */}
            <section className="container py-5">
                <div className="row text-center">
                    <div className="col-md-4 mb-4">
                        <i className="bi bi-person-bounding-box fs-1 text-primary mb-3"></i>
                        <h4>Reconocimiento Facial</h4>
                        <p className="text-muted">
                            Sancho detecta y reconoce rostros en tiempo real, con identificación persistente y base de
                            datos editable desde la web.
                        </p>
                    </div>
                    <div className="col-md-4 mb-4">
                        <i className="bi bi-chat-dots fs-1 text-primary mb-3"></i>
                        <h4>Conversación Natural</h4>
                        <p className="text-muted">
                            Sistema de diálogo basado en LLMs e integración con Whisper para transcripción y respuesta
                            hablada con TTS.
                        </p>
                    </div>
                    <div className="col-md-4 mb-4">
                        <i className="bi bi-cpu fs-1 text-primary mb-3"></i>
                        <h4>Gestión Modular</h4>
                        <p className="text-muted">
                            Control total desde la interfaz: carga y descarga de modelos de voz, STT y LLM. Todo
                            sincronizado con ROS 2.
                        </p>
                    </div>
                </div>
            </section>

            {/* Capturas y evidencia */}
            <section className="bg-white border-top border-bottom py-5">
                <div className="container">
                    <h3 className="text-center fw-bold mb-5 fs-1">Conoce a Sancho</h3>
                    <div className="row align-items-center justify-content-center g-5">
                        {/* Imagen del robot */}
                        <div className="col-lg-6 col-xl-4 text-center">
                            <img src={sanchoSrc} className="img-fluid rounded shadow-sm" alt="Robot Sancho" />
                        </div>

                        {/* Descripción del robot */}
                        <div className="col-lg-6">
                            <h4 className="fw-bold mb-3 text-dark">El robot social del grupo MAPIR</h4>
                            <p className="text-muted">
                                <strong>Sancho</strong> es el robot social del grupo de investigación MAPIR (Universidad
                                de Málaga), concebido como una plataforma avanzada para experimentar con interacción
                                humano-robot en contextos reales. Su diseño modular, abierto y extensible lo convierte
                                en un banco de pruebas ideal para el desarrollo de sistemas inteligentes.
                            </p>
                            <p className="text-muted">
                                Este robot es capaz de{" "}
                                <strong>ver, escuchar, hablar, reconocer personas y expresar emociones</strong>. Gracias
                                a su arquitectura basada en ROS 2, Sancho combina visión por computador, procesamiento
                                de lenguaje natural (LLM), síntesis y transcripción de voz, y control físico de LEDs que
                                simulan la boca y los ojos. Todo esto permite que interactúe con los usuarios de forma
                                fluida, natural y personalizada.
                            </p>
                            <p className="text-muted">
                                A través de una interfaz web intuitiva, cualquier persona puede observar su
                                comportamiento en tiempo real, gestionar modelos de IA, registrar nuevos usuarios o
                                consultar estadísticas de interacción. Su versatilidad lo convierte en una herramienta
                                útil para entornos educativos, demostraciones científicas y robótica asistencial.
                            </p>
                        </div>
                    </div>
                </div>
            </section>

            {/* Sobre el TFG */}
            <section className="container py-5">
                <h3 className="fw-bold text-center mb-4">Sobre este proyecto</h3>
                <p className="text-muted text-center col-md-10 offset-md-1">
                    Este Trabajo de Fin de Grado presenta un sistema de interacción humano-robot (HRI) completamente
                    funcional construido sobre ROS 2 y controlado mediante una interfaz web moderna. Sancho reconoce
                    rostros, transcribe audio, genera respuestas en lenguaje natural y permite al usuario gestionar los
                    modelos de IA que lo hacen posible. Todo ello desde cualquier navegador.
                </p>
            </section>
        </div>
    );
};

export default HomePage;
