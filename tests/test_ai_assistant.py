import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from ai_assistant import AssistantError, OllamaAssistant
from app import create_app
from recommender import MovieRecommender


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class OllamaAssistantTests(unittest.TestCase):
    def test_status_reports_missing_model_with_pull_command(self):
        assistant = OllamaAssistant()
        response_data = {"models": [{"name": "another-model"}]}
        with patch("ai_assistant.urlopen") as urlopen:
            response = urlopen.return_value.__enter__.return_value
            response.read.return_value = json.dumps(response_data).encode("utf-8")

            status = assistant.status()

        self.assertFalse(status["configured"])
        self.assertIn("ollama pull qwen2.5:3b", status["message"])
        self.assertEqual(urlopen.call_args.args[0].full_url, "http://127.0.0.1:11434/api/tags")

    def test_status_reports_unavailable_local_ollama(self):
        assistant = OllamaAssistant()
        with patch("ai_assistant.urlopen", side_effect=URLError("not running")):
            status = assistant.status()

        self.assertFalse(status["configured"])
        self.assertIn("Ollama не запущен", status["message"])

    def test_answer_sends_question_and_catalog_to_local_ollama(self):
        assistant = OllamaAssistant()
        response_data = {"response": "Посмотрите «Интерстеллар»."}
        with patch(
            "ai_assistant.urlopen",
        ) as urlopen:
            response = urlopen.return_value.__enter__.return_value
            response.read.return_value = json.dumps(response_data).encode("utf-8")

            answer = assistant.answer(
                "Что посмотреть?",
                "- Интерстеллар (2014): Science Fiction, Drama",
            )

        self.assertEqual(answer, "Посмотрите «Интерстеллар».")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/generate")
        self.assertIsNone(request.get_header("Authorization"))
        payload = json.loads(request.data)
        self.assertEqual(payload["model"], "qwen2.5:3b")
        self.assertIn("<|im_start|>system", payload["prompt"])
        self.assertIn("<|im_start|>user\nЧто посмотреть?", payload["prompt"])
        self.assertIn("Интерстеллар", payload["prompt"])
        self.assertTrue(payload["raw"])
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["keep_alive"], "10m")
        self.assertEqual(payload["options"]["num_predict"], 64)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 240)

    def test_api_reports_configuration_and_validates_assistant_queries(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            recommender = MovieRecommender(
                DATA_DIR,
                Path(temporary_directory) / "similarity.pkl",
            )

            class FakeAssistant:
                last_catalog_context = None

                @staticmethod
                def status():
                    return {"configured": True, "model": "test", "message": "готов"}

                @classmethod
                def answer(cls, question, catalog_context):
                    cls.last_catalog_context = catalog_context
                    return f"{question}: {catalog_context.splitlines()[0]}"

            client = create_app(
                recommender,
                Path(temporary_directory) / "comments.json",
                assistant=FakeAssistant(),
            ).test_client()

            status = client.get("/api/assistant/status")
            answer = client.post("/api/assistant", json={"question": "Подскажи фильм"})
            missing = client.post("/api/assistant", json={"question": "  "})
            too_long = client.post(
                "/api/assistant",
                json={"question": "x" * 2001},
            )

        self.assertEqual(status.status_code, 200)
        self.assertTrue(status.json["configured"])
        self.assertEqual(status.json["model"], "test")
        self.assertEqual(answer.status_code, 200)
        self.assertTrue(answer.json["answer"].startswith("Подскажи фильм: - "))
        self.assertLessEqual(len(FakeAssistant.last_catalog_context.splitlines()), 10)
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(too_long.status_code, 400)

    def test_api_does_not_send_catalog_for_non_movie_questions(self):
        class FakeAssistant:
            catalog_context = None

            @staticmethod
            def status():
                return {"configured": True, "model": "test", "message": "готов"}

            @classmethod
            def answer(cls, question, catalog_context):
                cls.catalog_context = catalog_context
                return "Готов помочь."

        with tempfile.TemporaryDirectory() as temporary_directory:
            recommender = MovieRecommender(
                DATA_DIR,
                Path(temporary_directory) / "similarity.pkl",
            )
            client = create_app(
                recommender,
                Path(temporary_directory) / "comments.json",
                assistant=FakeAssistant(),
            ).test_client()

            response = client.post(
                "/api/assistant",
                json={"question": "Как составить план на неделю?"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(FakeAssistant.catalog_context, "")

    def test_api_returns_assistant_errors_to_the_client(self):
        class UnavailableAssistant:
            @staticmethod
            def answer(question, catalog_context):
                raise AssistantError("Ollama is not running.")

        with tempfile.TemporaryDirectory() as temporary_directory:
            recommender = MovieRecommender(
                DATA_DIR,
                Path(temporary_directory) / "similarity.pkl",
            )
            client = create_app(
                recommender,
                Path(temporary_directory) / "comments.json",
                assistant=UnavailableAssistant(),
            ).test_client()
            response = client.post(
                "/api/assistant",
                json={"question": "Посоветуй фильм"},
            )

        self.assertEqual(response.status_code, 502)
        self.assertIn("Ollama", response.json["error"])


if __name__ == "__main__":
    unittest.main()
