import unittest
from pathlib import Path

from app import create_app
from train_rating_classifier import build_classification_dataset, evaluate_dataset


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class RatingClassifierTests(unittest.TestCase):
    def test_dataset_joins_ratings_with_movie_and_viewer_features(self):
        dataset = build_classification_dataset(DATA_DIR)

        self.assertEqual(len(dataset), 54)
        first_rating = next(
            row
            for row in dataset
            if row["user_id"] == "viewer_01" and row["movie_id"] == "1"
        )
        self.assertEqual(first_rating["rating"], 5.0)
        self.assertEqual(first_rating["liked"], 1)
        self.assertIn("Science Fiction", first_rating["text"])
        self.assertIn("Фантастика и космос", first_rating["text"])

    def test_evaluation_uses_viewer_groups_and_reports_baseline(self):
        report = evaluate_dataset(build_classification_dataset(DATA_DIR))

        self.assertEqual(report["samples"], 54)
        self.assertEqual(report["viewers"], 6)
        self.assertEqual(report["class_distribution"], {"disliked": 11, "liked": 43})
        self.assertIn("без оценок одного зрителя", report["validation"])
        self.assertEqual(sum(map(sum, report["model"]["confusion_matrix"])), 54)
        self.assertEqual(sum(map(sum, report["neural_network"]["confusion_matrix"])), 54)
        self.assertTrue(report["neural_recognition_examples"])
        self.assertTrue(
            all("probability_liked" in example for example in report["neural_recognition_examples"])
        )
        self.assertIn("balanced_accuracy", report["baseline"])

    def test_classification_results_are_available_from_the_web_api(self):
        client = create_app().test_client()
        response = client.get("/api/classification/results")
        homepage = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["samples"], 54)
        self.assertTrue(response.json["dataset_preview"])
        preview = response.json["dataset_preview"]
        self.assertEqual(len({row["viewer_name"] for row in preview}), 6)
        self.assertIn("movie_title", preview[0])
        self.assertIn("genres", preview[0])
        self.assertNotIn("user_id", preview[0])
        self.assertTrue(response.json["neural_recognition_examples"])
        self.assertIn("movie_title", response.json["neural_recognition_examples"][0])
        self.assertIn("viewer_name", response.json["neural_recognition_examples"][0])
        self.assertIn("Результаты обучения".encode(), homepage.data)
        self.assertIn(b'<details class="classifier-report"', homepage.data)
        self.assertIn("Показать результаты".encode(), homepage.data)
        self.assertIn(b'id="classifier-scoreboard"', homepage.data)
        self.assertIn("Примеры данных датасета".encode(), homepage.data)


if __name__ == "__main__":
    unittest.main()