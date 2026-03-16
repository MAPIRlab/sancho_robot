import json

from ...prompts.commands.commands import COMMANDS, COMMAND_RESUITS

from ...engines import HRIEngine


class IntentExecutor:

    def __init__(self, hri_engine: HRIEngine):
        self.hri_engine = hri_engine
    
    def execute(self, intent: str, arguments: dict) -> dict:
        if intent == COMMANDS.DELETE_USER:
            return self.delete_user(arguments)

        elif intent == COMMANDS.RENAME_USER:
            return self.rename_user(arguments)

        elif intent == COMMANDS.TAKE_PICTURE:
            return self.take_picture(arguments)

        raise ValueError(f"Invalid intent: {intent}")

    def delete_user(self, arguments):
        user = arguments["user"]
        if not user:
            details = f"No he eliminado a nadie, no sé a quién te refieres"
            status = COMMAND_RESUITS.MISSING_ARGUMENT
            
        else:
            users_obj_json = self.hri_engine.get_faceprint_request(json.dumps({"name": user}))
            users_obj = json.loads(users_obj_json)
            if len(users_obj) > 0:
                user_obj = users_obj[0]
                result_action = self.hri_engine.delete_request(user_obj["id"])
                if result_action >= 0:
                    details = f"He eliminado a {user} correctamente"
                    status = COMMAND_RESUITS.SUCCESS

                else:
                    details = f"No he podido borrar a {user}"
                    status = COMMAND_RESUITS.FAILURE

            else:
                details = f"No he encontrado a nadie con el nombre {user}"
                status = COMMAND_RESUITS.FAILURE

        return details, status, {}

    def rename_user(self, arguments):
        old_name = arguments["old_name"]
        new_name = arguments["new_name"]

        if not old_name:
            details = f"No he renombrado a nadie, no sé a quién te refieres"
            status = COMMAND_RESUITS.MISSING_ARGUMENT
        elif not new_name:
            details = f"No he renombrado a {old_name}, no sé que otro nombre le quieres poner"
            status = COMMAND_RESUITS.MISSING_ARGUMENT
        else:
            users_obj_json = self.hri_engine.get_faceprint_request(json.dumps({"name": old_name}))
            users_obj = json.loads(users_obj_json)
            if len(users_obj) > 0:
                user_obj = users_obj[0]
                result_action = self.hri_engine.rename_request(user_obj["id"], new_name)
                if result_action >= 0:
                    details = f"He cambiado el nombre de {old_name} por {new_name} correctamente"
                    status = COMMAND_RESUITS.SUCCESS
                else:
                    details = f"No he podido cambiar el nombre de {old_name} por {new_name}"
                    status = COMMAND_RESUITS.FAILURE
            else:
                details = f"No he encontrado a nadie con el nombre {old_name}"
                status = COMMAND_RESUITS.FAILURE

        return details, status, {}

    def take_picture(self, _):
        image = self.hri_engine.get_last_frame_request()
        if not image:
            details = "No he podido tomar una foto"
            status = COMMAND_RESUITS.FAILURE
            data = {}
        else:
            details = "Foto tomada correctamente"
            status = COMMAND_RESUITS.SUCCESS
            data = { "image": image }
        
        return details, status, data