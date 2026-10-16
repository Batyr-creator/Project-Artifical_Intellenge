import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import joblib
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LIKE_THRESHOLD = 4.0


def _read_csv(path):
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def build_classification_dataset(data_dir=DATA_DIR):
    data_dir = Path(data_dir)
    movies = {movie["movie_id"]: movie for movie in _read_csv(data_dir / "movies.csv")}
    profiles = {
        profile["user_id"]: profile for profile in _read_csv(data_dir / "profiles.csv")
    }
    ratings = _read_csv(data_dir / "ratings.csv")
    dataset = []

    for rating in ratings:
        movie = movies.get(rating["movie_id"])
        profile = profiles.get(rating["user_id"])
        if movie is None or profile is None:
            raise ValueError(
                f"Не найдены фильм или профиль для оценки {rating!r}"
            )

        text = " ".join(
            value
            for value in (
                movie["genres"].replace("|", " "),
                movie["director"],
                movie["cast"].replace("|", " "),
                movie["overview"],
                movie.get("overview_ru", ""),
                profile["taste"],
            )
            if value
        )
        numeric_rating = float(rating["rating"])
        dataset.append(
            {
                "user_id": rating["user_id"],
                "movie_id": rating["movie_id"],
                "rating": numeric_rating,
                "text": text,
                "liked": int(numeric_rating >= LIKE_THRESHOLD),
            }
        )

    return dataset


def build_model():
    return make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), max_features=3000, sublinear_tf=True),
        LogisticRegression(
            class_weight="balanced",
            max_iter=2000,
            random_state=42,
        ),
    )


def build_neural_network():
    return make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), max_features=3000, sublinear_tf=True),
        MLPClassifier(
            hidden_layer_sizes=(32, 16),
            alpha=0.1,
            max_iter=1200,
            tol=1e-3,
            random_state=42,
        ),
    )


def _metrics(labels, predictions):
    matrix = confusion_matrix(labels, predictions, labels=[0, 1])
    return {
        "accuracy": accuracy_score(labels, predictions),
        "balanced_accuracy": balanced_accuracy_score(labels, predictions),
        "precision_liked": precision_score(labels, predictions, zero_division=0),
        "recall_liked": recall_score(labels, predictions, zero_division=0),
        "f1_liked": f1_score(labels, predictions, zero_division=0),
        "confusion_matrix": matrix.tolist(),
    }


def evaluate_dataset(dataset):
    labels = [row["liked"] for row in dataset]
    texts = [row["text"] for row in dataset]
    groups = [row["user_id"] for row in dataset]
    group_count = len(set(groups))
    if group_count < 2 or len(set(labels)) < 2:
        raise ValueError("Для оценки нужны минимум два зрителя и два класса")

    cross_validation = GroupKFold(n_splits=group_count)
    model_predictions = cross_val_predict(
        build_model(), texts, labels, groups=groups, cv=cross_validation
    )
    neural_probabilities = cross_val_predict(
        build_neural_network(),
        texts,
        labels,
        groups=groups,
        cv=cross_validation,
        method="predict_proba",
    )
    neural_predictions = (neural_probabilities[:, 1] >= 0.5).astype(int)
    baseline_predictions = cross_val_predict(
        DummyClassifier(strategy="most_frequent"),
        texts,
        labels,
        groups=groups,
        cv=cross_validation,
    )
    class_counts = Counter(labels)
    recognition_by_outcome = defaultdict(list)
    for index, row in enumerate(dataset):
        recognition_by_outcome[(labels[index], neural_predictions[index])].append(
            {
                "user_id": row["user_id"],
                "movie_id": row["movie_id"],
                "rating": row["rating"],
                "actual_liked": labels[index],
                "predicted_liked": int(neural_predictions[index]),
                "probability_liked": float(neural_probabilities[index, 1]),
            }
        )
    recognition_examples = [
        example
        for outcome in ((0, 0), (0, 1), (1, 0), (1, 1))
        for example in recognition_by_outcome[outcome][:2]
    ]

    return {
        "samples": len(dataset),
        "viewers": group_count,
        "class_distribution": {
            "disliked": class_counts[0],
            "liked": class_counts[1],
        },
        "validation": "Для проверки сеть каждый раз обучалась без оценок одного зрителя, а затем предсказывала оценки этого зрителя.",
        "model": _metrics(labels, model_predictions),
        "neural_network": _metrics(labels, neural_predictions),
        "baseline": _metrics(labels, baseline_predictions),
        "neural_recognition_examples": recognition_examples,
    }


def run_training(data_dir=DATA_DIR):
    data_dir = Path(data_dir)
    dataset = build_classification_dataset(data_dir)
    dataset_path = data_dir / "rating_classification.csv"
    with dataset_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["user_id", "movie_id", "rating", "text", "liked"],
        )
        writer.writeheader()
        writer.writerows(dataset)

    report = evaluate_dataset(dataset)
    pipeline = build_model()
    pipeline.fit(
        [row["text"] for row in dataset],
        [row["liked"] for row in dataset],
    )
    neural_network = build_neural_network()
    neural_network.fit(
        [row["text"] for row in dataset],
        [row["liked"] for row in dataset],
    )

    output_dir = data_dir / "cache"
    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "rating_preference_classifier.joblib"
    neural_network_path = output_dir / "rating_preference_neural_network.joblib"
    report_path = data_dir / "rating_classification_metrics.json"
    joblib.dump(pipeline, model_path)
    joblib.dump(neural_network, neural_network_path)
    report["artifacts"] = {
        "dataset": str(dataset_path.relative_to(BASE_DIR)),
        "model": str(model_path.relative_to(BASE_DIR)),
        "neural_network": str(neural_network_path.relative_to(BASE_DIR)),
    }
    with report_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)

    return report


if __name__ == "__main__":
    print(json.dumps(run_training(), ensure_ascii=False, indent=2))