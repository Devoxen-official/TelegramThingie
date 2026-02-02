import re
import concurrent.futures
import requests
from typing import Optional

from src.config import Settings
from src.utils.logger import logger

settings = Settings.from_env()
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

class LLMProvider:
    def __init__(self, provider_name: str):
        self.provider = provider_name.lower()
        self.api_key = settings.llm_api_key
        if self.provider == "deepseek":
            self.model = settings.llm_model or "deepseek/deepseek-r1-0528:free"
            self.url = "https://openrouter.ai/api/v1/chat/completions"
        elif self.provider == "openai":
            self.model = settings.llm_model or "gpt-3.5-turbo"
            self.url = "https://api.openai.com/v1/chat/completions"
        else:
            raise ValueError(f"Unknown LLM provider: {provider_name}")
        if not self.api_key:
            raise ValueError("LLM_API_KEY is not configured")

    def get_completion(self, prompt: str) -> Optional[str]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": self.model, "messages": [{"role": "user", "content": prompt}]}
        try:
            response = requests.post(self.url, headers=headers, json=payload, timeout=60.0)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"Error in LLM request to {self.url}: {e}")
            return None

        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        content = msg.get("content") or (msg.get("reasoning") if self.provider == "deepseek" else None)

        if not content:
            error = choice.get("error") or data.get("error")
            logger.error(f"{self.provider.capitalize()} API Error: {error}. Response: {data}")
            return None

        return content


def get_dialog_to_script_similarity(dialog: str, script: str) -> Optional[int]:
    prompt = (
        "Analyze the following client-manager dialog and compare it with the provided manager script(s). "
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

    def _request():
        try:
            provider = LLMProvider(settings.llm_provider)
            content = provider.get_completion(prompt)
            if not content:
                return None

            match = re.search(r'\d+', content)
            return int(match.group()) if match else None
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            return None

    return _executor.submit(_request).result()
