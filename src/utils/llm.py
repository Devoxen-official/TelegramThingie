import sys
from pathlib import Path
import requests
import json
import concurrent.futures
from typing import Optional
from dotenv import load_dotenv, find_dotenv
import re
from src.utils.logger import logger

root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.config import Settings

load_dotenv(find_dotenv())
settings = Settings.from_env()

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)


def get_dialog_to_script_similarity(dialog, script) -> Optional[int]:
    message = ("Analyze the following client-manager dialog and compare it with the provided manager script(s). "
               "The script(s) define how the manager should communicate, what questions to ask, and what information to provide. "
               "Evaluate how closely the manager followed the script(s). "
               "Similarity is a percentage (0-100) where 100 means perfect adherence to the script's logic and tone, "
               "and 0 means the manager completely ignored the script. "
               "\n\nCRITICAL REQUIREMENT: Your output must be ONLY the integer number. "
               "Do NOT include the '%' sign, do NOT include words like 'Rated:', 'Similarity:', or any explanation. "
               "Just the number itself. For example, if the similarity is 85%, output '85'."
               f"\n\n==DIALOG==\n{dialog}\n==END OF DIALOG=="
               f"\n\n==MANAGER SCRIPTS==\n{script}\n==END OF MANAGER SCRIPTS=="
               )

    def _do_request():
        try:
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
                }),
                timeout=60.0
            )
            response.raise_for_status()
            
            response_json = response.json()
            choice = response_json.get("choices", [{}])[0]
            message_data = choice.get("message", {})
            content = message_data.get("content")
            reasoning = message_data.get("reasoning")
            error = choice.get("error") or response_json.get("error")

            if not content and reasoning:
                content = reasoning

            if not content:
                if logger.level is None:
                    logger.set_level(settings.env)
                msg = f"LLM response content is empty. Full response: {response.text}"
                if error:
                    msg = f"LLM API Error: {error}. Full response: {response.text}"
                logger.error(msg)
                return None

            try:
                cleaned_content = content.strip()
                return int(cleaned_content)
            except ValueError:
                match = re.search(r'\d+', content)
                if match:
                    return int(match.group())

                if logger.level is None:
                    logger.set_level(settings.env)
                logger.error(f"Failed to parse LLM response as int. Content: '{content}'")
                return None
        except Exception as e:
            if logger.level is None:
                logger.set_level(settings.env)
            logger.error(f"Error in LLM request: {e}")
            return None

    future = _executor.submit(_do_request)
    return future.result()
