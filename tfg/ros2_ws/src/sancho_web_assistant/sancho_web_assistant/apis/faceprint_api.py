import json

from std_msgs.msg import String

from ..engines import FaceprintEngine
from .api_responses import APIResponse, HTTPException, JSONResponse
from sancho_web_assistant.database.system_database import CONSTANTS


class FaceprintAPI:

    def __init__(self, node):
        self.engine = FaceprintEngine(node)

    def get_all_faceprints(self) -> APIResponse:
        faceprints_json = self.engine.get_faceprint_request()
        faceprints = json.loads(faceprints_json)

        return JSONResponse(content=faceprints)

    def get_faceprint(self, id: str) -> APIResponse:
        faceprint_json = self.engine.get_faceprint_request(json.dumps({ "id": id }))

        faceprint = json.loads(faceprint_json)
        if not faceprint:
            return HTTPException(status_code=404, detail=f"Faceprint con id {id} no encontrado")
        
        return JSONResponse(content=faceprint)

    def create_faceprint(self, name: str, image_base64: str) -> APIResponse:
        image_cv2 = self.engine.br.base64_to_cv2(image_base64)
        image_msg = self.engine.br.cv2_to_imgmsg(image_cv2, encoding="bgr8")
        
        positions_msg, scores_msg = self.engine.detection_request(image_msg)
        positions, scores = self.engine.br.msg_to_detector(positions_msg, scores_msg)

        if len(positions) == 0:
            return HTTPException(detail=f"No se ha detectado ningún rostro en la imagen.")
        elif len(positions) > 1:
            return HTTPException(detail=f"Se ha detectado más de un rostro en la imagen. Solo debe haber uno.")
        else:
            position = positions_msg[0]
            score = scores[0]

            if score < 1:
                return HTTPException(detail=f"La puntuación de la detección ha sido demasiado baja ({score:.2f} < 1). Por favor, envía una imagen mejor.")
            else:
                face_aligned_msg, features_msg, classified_id, classified_name_msg, distance_msg, pos_msg, face_updated = \
                    self.engine.recognition_request(image_msg, position, score)
                face_aligned, features, classified_name, distance, pos = \
                    self.engine.br.msg_to_recognizer(face_aligned_msg, features_msg, classified_name_msg, distance_msg, pos_msg)
                
                if face_updated:
                    log_message = f"Se ha actualizado la imagen de la cara con id {classified_id} desde la web"
                    metadata_json = json.dumps({ "faceprint_id": classified_id })
                    self.engine.create_log(CONSTANTS.ACTION.UPDATE_FACE, classified_id, log_message, metadata_json)

                LOWER_BOUND = 0.75
                MIDDLE_BOUND = 0.80
                if distance < LOWER_BOUND:
                    face_aligned_base64 = self.engine.br.cv2_to_base64(face_aligned)
                    result, message = self.engine.training_request(String(data="add_class"), String(data=json.dumps({
                        "class_name": name,
                        "features": features,
                        "face": face_aligned_base64,
                        "score": score
                    }))) # Añadimos clase (en teoria es alguien nuevo)
                    if result < 0: # Solo si es error
                        return HTTPException(detail=message)
                    else: # Añade vector de característica
                        classified_id = message

                        updated_item_json = self.engine.get_faceprint_request(json.dumps({ "id": classified_id }))
                        updated_item = json.loads(updated_item_json)

                        log_message = f"Se ha creado una nueva clase con id {classified_id} desde la web"
                        metadata_json = json.dumps({ "faceprint_id": classified_id, "name": name, "face_score": score })
                        self.engine.create_log(CONSTANTS.ACTION.ADD_CLASS, classified_id)

                        return JSONResponse(content=updated_item)
                    
                elif distance < MIDDLE_BOUND:
                    return HTTPException(detail=f"Nunca pensé que pasase esto MIDDLE BOUND.")
                else:
                    return HTTPException(detail=f"Ya te conozco {classified_name}, esta función es para personas nuevas.")

    def update_faceprint(self, id: str, faceprint: dict) -> APIResponse:
        new_name = faceprint["name"]
        if new_name is None:
            return HTTPException(detail="No has incluido el campo name.")

        item_json = self.engine.get_faceprint_request(json.dumps({ "id": id }))
        item = json.loads(item_json)
        if not item:
            return HTTPException(detail=f"No existe ningun rostro con el id {id}")

        result, message = self.engine.training_request(String(data="rename_class"), String(data=json.dumps({
            "class_id": id,
            "new_name": new_name,
        })))
        if result <= 0:
            return HTTPException(detail=message)

        log_message = f"Se ha creado renombrado la clase con id {id} desde la web. Nuevo nombre: {new_name}"
        metadata_json = json.dumps({ "faceprint_id": id, "new_name": new_name })
        self.engine.create_log(CONSTANTS.ACTION.RENAME_CLASS, id, log_message, metadata_json)

        updated_item_json = self.engine.get_faceprint_request(json.dumps({ "id": id }))
        updated_item = json.loads(updated_item_json)

        return JSONResponse(content=updated_item)

    def delete_faceprint(self, id: str) -> APIResponse:
        item_json = self.engine.get_faceprint_request(json.dumps({ "id": id }))
        item = json.loads(item_json)
        if not item:
            return HTTPException(detail=f"No existe ningun rostro con el id {id}")
    
        result, message = self.engine.training_request(String(data="delete_class"), String(data=json.dumps({
            "class_id": id
        })))
        if result <= 0:
            return HTTPException(detail=message)

        log_message = f"Se ha eliminado la clase con id {id} desde la web"
        metadata_json = json.dumps({ "faceprint_id": id })
        self.engine.create_log(CONSTANTS.ACTION.DELETE_CLASS, id)

        return JSONResponse(content=f"Faceprint con id {id} eliminado correctamente.")