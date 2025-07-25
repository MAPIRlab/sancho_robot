from typing import Optional, Dict
from fastapi import Request, HTTPException


class APIUtils:
    _admin_key = ""

    @classmethod
    def get_admin_key(cls) -> str:
        "Obtiene la clave de admin"
        return cls._admin_key

    @classmethod
    def is_admin(cls, request) -> bool:
        token = request.headers.get("Authorization")
        if token is None or len(token.split(" ")) < 2:
            return False
        
        return token.split(" ")[1] == cls.get_admin_key()

    @classmethod
    def has_permission(cls, needed_id: str, actual_id: str) -> bool:
        """Devuelve true si se tienen permisos para la acción"""
        return actual_id == needed_id or actual_id == cls.get_admin_key()

    @classmethod
    def get_service_url(cls, version: str, service: str) -> str:
        """Construir la URL para el servicio y versión especificados."""
        return f"{cls.get_service_base_url(service)}/api/{version}/{service}"

    @classmethod
    def construct_url(cls, version: str, service: str, path: str) -> str:
        """Construir la URL completa con una ruta específica."""
        return f"{cls.get_service_url(version, service)}/{path}".rstrip("/")

    @classmethod
    def check_accept_json(cls, request: Request):
        """Verificar si la cabecera Accept contiene 'application/json'."""
        accepted = request.headers.get("Accept", "")
        if "application/json" not in accepted and "*/*" not in accepted:
            raise HTTPException(status_code=406, detail="La cabecera Accept debe incluir 'application/json'")

    @classmethod
    def check_content_type_json(cls, request: Request):
        """Verificar si la cabecera Content-Type contiene 'application/json'."""
        if "application/json" not in request.headers.get("Content-Type", ""):
            raise HTTPException(status_code=415, detail="La cabecera Content-Type debe incluir 'application/json'")

    @classmethod
    def add_regex(cls, query: Dict[str, Dict], field: str, value: Optional[str]):
        """Agregar un filtro regex a la consulta si el valor no es None."""
        if value:
            query[field] = {"$regex": value, "$options": 'i'}

    @classmethod
    def build_projection(cls, fields: Optional[str]) -> Optional[dict]:
        """Construir el diccionario de proyección para los campos especificados."""
        if fields:
            return {field: 1 for field in fields.split(',')}
        return None

    @classmethod
    def build_sort_criteria(cls, sort: Optional[str]) -> Optional[list]:
        """Construir los criterios de ordenación a partir de la cadena de campos."""
        if sort:
            criteria = []
            for field in sort.split(','):
                field = field.strip()
                if field.startswith('-'):
                    criteria.append([field[1:], -1])  # Orden descendente
                else:
                    criteria.append([field, 1])       # Orden ascendente
            return criteria
        return None

    @classmethod
    async def get(cls, client, url):
        response = await client.get(url, headers={"Accept" : "application/json"})
        return response.json()
    
    @classmethod
    async def post(cls, client, url, content):
        response = await client.post(url, json=content, headers={"Accept" : "application/json", "Authorization": f"Bearer {cls.get_admin_key()}"})
        return response.json()
    
    @classmethod
    async def delete(cls, client, url):
        response = await client.delete(url, headers={"Accept" : "application/json", "Authorization": f"Bearer {cls.get_admin_key()}"})
        return response.json()
