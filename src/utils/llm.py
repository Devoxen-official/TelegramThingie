import sys
from pathlib import Path
import requests
import json
from dotenv import load_dotenv, find_dotenv

root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.config import Settings

load_dotenv(find_dotenv())
settings = Settings.from_env()


def get_dialog_to_script_similarity(dialog, script) -> int:
    message = ("do not even fucking think of answering something i did not ask you about. "
               "I will send you a client-manager dialog. "
               "Your task is to get how manager is following his script"
               "(similarity percentage between what manager says in dialog,"
               "and script that manager needs to use in dialog). "
               "you must output ONLY int percentage of script and dialog similarity for it to work with int(). "
               f"==DIALOG==:{dialog}==END OF DIALOG==\n==MANAGERS SCRIPT=={script}==END OF MANAGERS SCRIPT=="
               )

    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.llm_deepseek_api_key}",
            "Content-Type": "application/json",
        },
        data=json.dumps({
            "model": "deepseek/deepseek-r1-0528:free",
            "messages": [
                {
                    "role": "user",
                    "content": message
                }
            ]
        })
    )

    result = (
        response.json()
        .get("choices", [{}])[0]
        .get("message", {})
        .get("content")
    )
    return int(result)
