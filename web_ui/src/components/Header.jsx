import { Link, useNavigate } from "react-router-dom";
import bannerSrc from "/logo.png";

const Header = () => {
    const navigate = useNavigate();

    let items = [
        { link: "", name: "Inicio" },
        { link: "chat", name: "Chat" },
        { link: "faceprints", name: "Rostros" },
        { link: "models", name: "Modelos" },
        { link: "logs", name: "Logs" },
    ];

    //const user = getActualUser();
    //if (user !== null && user.profile.firstName === "admin")
    //    items = [...items, { link: "admin", name: "Admin" }];

    return (
        <header style={{ zIndex: 10 }}>
            <nav className="ps-4 d-flex justify-content-start align-items-center position-absolute w-100 navbar navbar-expand-lg bg-body-tertiary border-bottom top-0">
                <div className="container-fluid">
                    <a
                        className="navbar-brand"
                        style={{ cursor: "pointer" }}
                        onClick={() => {
                            navigate("/");
                        }}
                    >
                        <img src={bannerSrc} alt="SanchoUI" height="50" />
                    </a>
                    <button
                        className="navbar-toggler"
                        type="button"
                        data-bs-toggle="collapse"
                        data-bs-target="#navbarScroll"
                        aria-controls="navbarScroll"
                        aria-expanded="false"
                        aria-label="Toggle navigation"
                    >
                        <span className="navbar-toggler-icon"></span>
                    </button>
                    <div className="collapse navbar-collapse" id="navbarScroll">
                        <ul className="navbar-nav me-auto my-2 my-lg-0 navbar-nav-scroll">
                            {items.map((v) => item(v.link, v.name))}
                        </ul>
                    </div>
                </div>
            </nav>
        </header>
    );
};

const item = (link, name) => {
    return (
        <li key={link} className="nav-item">
            <Link
                className={
                    "nav-link text-dark" +
                    (document.URL.split("/")[3].toLowerCase() === link.toLowerCase() ? " active fw-bold" : "")
                }
                to={"/" + link}
                style={{ color: "#0d6efd" }} // Usamos el color primario de Bootstrap para el enlace
            >
                {name}
            </Link>
        </li>
    );
};

export default Header;
