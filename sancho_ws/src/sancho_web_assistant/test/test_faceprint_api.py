import requests
import base64
import uuid
from pathlib import Path
import pytest

BASE_URL = "http://localhost:7654/api/v1/faceprints"
HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}
IMAGES_DIR = Path("./images")


def load_image_base64(filename: str) -> str:
    with open(IMAGES_DIR / filename, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/jpeg;base64,{encoded}"


def assert_has_id(response):
    assert response.status_code == 200, f"Status code: {response.status_code}, body: {response.text}"
    json_data = response.json()
    assert "id" in json_data, f"Response JSON does not contain 'id': {json_data}"
    return json_data


@pytest.fixture(autouse=True)
def clear_faceprints_before_each_test():
    """Elimina todos los registros antes de cada test."""
    response = requests.get(BASE_URL, headers=HEADERS)
    if response.status_code == 200:
        for item in response.json():
            requests.delete(f"{BASE_URL}/{item['id']}", headers=HEADERS)


def test_create_and_get_faceprint():
    name = "TestUser1"
    payload = {"name": name, "image": load_image_base64("valid_face.jpg")}

    create_resp = requests.post(BASE_URL, json=payload, headers=HEADERS)
    created = assert_has_id(create_resp)

    get_resp = requests.get(f"{BASE_URL}/{created['id']}", headers=HEADERS)
    assert get_resp.status_code == 200
    fetched = get_resp.json()

    assert fetched["name"] == name
    assert fetched["id"] == created["id"]


def test_update_faceprint():
    create_resp = requests.post(BASE_URL, json={"name": "UserToUpdate", "image": load_image_base64("valid_face.jpg")}, headers=HEADERS)
    created = assert_has_id(create_resp)

    update_resp = requests.put(f"{BASE_URL}/{created['id']}", json={"name": "UpdatedUser"}, headers=HEADERS)
    assert update_resp.status_code == 200
    updated = update_resp.json()

    get_resp = requests.get(f"{BASE_URL}/{created['id']}", headers=HEADERS)
    fetched = get_resp.json()

    assert updated["name"] == "UpdatedUser"
    assert fetched["name"] == "UpdatedUser"


def test_delete_faceprint():
    create_resp = requests.post(BASE_URL, json={"name": "UserToDelete", "image": load_image_base64("valid_face.jpg")}, headers=HEADERS)
    created = assert_has_id(create_resp)

    delete_resp = requests.delete(f"{BASE_URL}/{created['id']}", headers=HEADERS)
    assert delete_resp.status_code == 200

    try:
        details = delete_resp.json()
        if isinstance(details, dict):
            assert "eliminado correctamente" in details.get("details", "").lower()
        elif isinstance(details, str):
            assert "eliminado correctamente" in details.lower()
        else:
            assert False, f"Respuesta inesperada: {details}"
    except Exception as e:
        assert False, f"delete_resp.json() falló: {str(e)}"


def test_get_all_faceprints():
    names = ["User1", "User2", "User3"]
    ids = []
    for i, name in enumerate(names):
        filename = f"valid_face_{i+1}.jpg" if (IMAGES_DIR / f"valid_face_{i+1}.jpg").exists() else "valid_face.jpg"
        resp = requests.post(BASE_URL, json={"name": name, "image": load_image_base64(filename)}, headers=HEADERS)
        created = assert_has_id(resp)
        ids.append(created["id"])

    get_all_resp = requests.get(BASE_URL, headers=HEADERS)
    assert get_all_resp.status_code == 200
    all_faceprints = get_all_resp.json()
    all_ids = {fp["id"] for fp in all_faceprints}

    for fid in ids:
        assert fid in all_ids


def test_get_single_faceprint():
    create_resp = requests.post(BASE_URL, json={"name": "SingleUser", "image": load_image_base64("valid_face.jpg")}, headers=HEADERS)
    created = assert_has_id(create_resp)

    get_resp = requests.get(f"{BASE_URL}/{created['id']}", headers=HEADERS)
    assert get_resp.status_code == 200
    fetched = get_resp.json()

    assert fetched["name"] == "SingleUser"
    assert fetched["id"] == created["id"]


def test_crud_faceprint():
    payload = {"name": "E2EUser", "image": load_image_base64("valid_face.jpg")}

    create_resp = requests.post(BASE_URL, json=payload, headers=HEADERS)
    created = assert_has_id(create_resp)

    get_resp = requests.get(f"{BASE_URL}/{created['id']}", headers=HEADERS)
    fetched = get_resp.json()
    assert fetched["name"] == "E2EUser"

    update_resp = requests.put(f"{BASE_URL}/{created['id']}", json={"name": "FinalName"}, headers=HEADERS)
    updated = update_resp.json()
    assert updated["name"] == "FinalName"

    delete_resp = requests.delete(f"{BASE_URL}/{created['id']}", headers=HEADERS)
    result = delete_resp.json()
    if isinstance(result, dict):
        assert "eliminado correctamente" in result.get("details", "").lower()


def test_get_nonexistent_faceprint():
    non_existing_id = str(uuid.uuid4())
    response = requests.get(f"{BASE_URL}/{non_existing_id}", headers=HEADERS)
    assert response.status_code == 404, f"Expected 404 but got {response.status_code}: {response.text}"
    assert "no encontrado" in response.text.lower()


def test_update_nonexistent_faceprint():
    non_existing_id = str(uuid.uuid4())
    response = requests.put(
        f"{BASE_URL}/{non_existing_id}",
        json={"name": "NuevoNombre"},
        headers=HEADERS,
    )
    assert response.status_code == 400
    assert "no existe ningun rostro" in response.text.lower()


def test_update_faceprint_without_name():
    create_resp = requests.post(BASE_URL, json={"name": "Temp", "image": load_image_base64("valid_face.jpg")}, headers=HEADERS)
    created = assert_has_id(create_resp)

    update_resp = requests.put(f"{BASE_URL}/{created['id']}", json={}, headers=HEADERS)
    assert update_resp.status_code == 422
    assert '"name"' in update_resp.text.lower()


def test_delete_nonexistent_faceprint():
    non_existing_id = str(uuid.uuid4())
    response = requests.delete(f"{BASE_URL}/{non_existing_id}", headers=HEADERS)
    assert response.status_code == 400
    assert "no existe ningun rostro" in response.text.lower()


def test_create_faceprint_with_multiple_faces():
    image_data = load_image_base64("multiple_faces.jpg")
    response = requests.post(BASE_URL, json={"name": "TwoFaces", "image": image_data}, headers=HEADERS)
    assert response.status_code == 400
    assert "más de un rostro" in response.text.lower()


def test_create_faceprint_with_no_face():
    image_data = load_image_base64("no_face.jpg")
    response = requests.post(BASE_URL, json={"name": "NoFace", "image": image_data}, headers=HEADERS)
    assert response.status_code == 400
    assert "no se ha detectado ningún rostro" in response.text.lower()


def test_create_faceprint_already_known():
    image_data = load_image_base64("known_face.jpg")
    response = requests.post(BASE_URL, json={"name": "KnownUser", "image": image_data}, headers=HEADERS)
    assert response.status_code == 200  # Se registra por primera vez

    response_repeat = requests.post(BASE_URL, json={"name": "KnownUser", "image": image_data}, headers=HEADERS)
    assert response_repeat.status_code == 400
    assert "ya te conozco" in response_repeat.text.lower()
