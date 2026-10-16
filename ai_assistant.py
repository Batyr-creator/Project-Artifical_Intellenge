import json
from urllib.request import Request, urlopen
from urllib.error import URLError

OLLAMA_URL = "http://127.0.0.1:11434"
MODEL = "qwen2.5:3b"


class AssistantError(Exception):
    pass


class OllamaAssistant:
    def __init__(self, base_url=OLLAMA_URL, model=MODEL):
        self.base_url = base_url
        self.model = model

    def status(self):
        try:
            request = Request(f"{self.base_url}/api/tags")
            with urlopen(request, timeout=3) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (URLError, OSError, ValueError):
            return {"configured": False, "model": self.model,
                    "message": "Ollama не запущен. Запустите: ollama serve"}

        names = [m.get("name", "") for m in data.get("models", [])]
        if self.model not in names:
            return {"configured": False, "model": self.model,
                    "message": f"Модель не найдена. Выполните: ollama pull {self.model}"}
        return {"configured": True, "model": self.model, "message": "ИИ-помощник готов"}

    def answer(self, question, catalog_context):
        system = "Ты помощник по фильмам. Отвечай кратко по-русски."
        if catalog_context:
            system += f"\nКаталог:\n{catalog_context}"
        prompt = (
            f"<|im_start|>system\n{system}<|im_end|>\n"
            f"<|im_start|>user\n{question}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        payload = {
            "model": self.model,
            "prompt": prompt,
            "raw": True,
            "stream": False,
            "keep_alive": "10m",
            "options": {"num_predict": 64},
        }
        request = Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=240) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (URLError, OSError, ValueError) as exc:
            raise AssistantError(f"Ollama недоступен: {exc}") from exc
        return data.get("response", "").strip()