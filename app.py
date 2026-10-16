import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from ai_assistant import AssistantError, OllamaAssistant
from recommender import MovieRecommender
from ai_assistant import AssistantError, OllamaAssistant

def create_app(recommender, comments_path, assistant=None):
       assistant = assistant or OllamaAssistant()

BASE_DIR = Path(__file__).resolve().parent
RULE_PRESENTATION = {
    "R1": {
        "title": "Находим понравившиеся фильмы",
        "explanation": "Оценку 4 или 5 считаем признаком, что фильм понравился зрителю.",
        "result": "Факт: фильм понравился",
    },
    "R2": {
        "title": "Определяем любимые жанры",
        "explanation": "Жанры понравившихся фильмов становятся предпочтениями зрителя.",
        "result": "Факт: зритель предпочитает жанр",
    },
    "R3": {
        "title": "Подбираем ещё не оценённые фильмы",
        "explanation": "Достаточно совпадения хотя бы по одному любимому жанру. Учитываем только оценки выбранного зрителя: подойдут и фильмы, которые он не оценивал, и фильмы без оценок в каталоге.",
        "result": "Факт: фильм подходит зрителю по жанру, если он ещё не оценивал его, даже когда в каталоге у фильма нет оценок.",
    },
}
GENRE_PRESENTATION = {
    "Action": "боевик",
    "Adventure": "приключения",
    "Animation": "анимация",
    "Biography": "биография",
    "Comedy": "комедия",
    "Crime": "криминал",
    "Drama": "драма",
    "Family": "семейный",
    "Fantasy": "фэнтези",
    "Horror": "ужасы",
    "Music": "музыка",
    "Mystery": "детектив",
    "Romance": "романтика",
    "Science Fiction": "фантастика",
    "Thriller": "триллер",
}


def create_app(recommender=None, comments_path=None, assistant=None):
    app = Flask(__name__)
    movie_recommender = recommender or MovieRecommender(BASE_DIR / "data")
    ai_assistant = assistant or OllamaAssistant()
    comments_file = Path(comments_path) if comments_path else BASE_DIR / "data" / "comments.json"

    def read_comments():
        try:
            with comments_file.open(encoding="utf-8") as file:
                comments = json.load(file)
            return comments if isinstance(comments, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def write_comments(comments):
        comments_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = comments_file.with_suffix(".tmp")
        with temporary_file.open("w", encoding="utf-8") as file:
            json.dump(comments, file, ensure_ascii=False, indent=2)
        temporary_file.replace(comments_file)

    def viewer_data():
        profiles = list(movie_recommender.user_profiles())
        profiles_by_name = {
            profile["name"].strip().casefold(): profile
            for profile in profiles
        }
        ratings_by_user_and_movie = {
            (rating["user_id"], rating["movie_id"]): dict(rating)
            for rating in movie_recommender.ratings
        }
        review_counts = {}
        review_ratings = {}

        for comment in read_comments():
            author = str(comment.get("author", "")).strip()
            movie_id = str(comment.get("movie_id", ""))
            if not author or movie_id not in movie_recommender.movie_by_id:
                continue

            normalized_name = author.casefold()
            profile = profiles_by_name.get(normalized_name)
            if profile is None:
                user_id = f"reviewer_{hashlib.sha256(normalized_name.encode('utf-8')).hexdigest()[:16]}"
                profile = {
                    "user_id": user_id,
                    "name": author,
                    "taste": "Зритель оставил отзыв",
                }
                profiles.append(profile)
                profiles_by_name[normalized_name] = profile

            try:
                rating_value = float(comment.get("rating"))
            except (TypeError, ValueError):
                continue
            if not 1 <= rating_value <= 5:
                continue

            review_counts[profile["user_id"]] = review_counts.get(profile["user_id"], 0) + 1
            review_ratings[(profile["user_id"], movie_id)] = {
                "user_id": profile["user_id"],
                "movie_id": movie_id,
                "rating": str(rating_value),
            }

        for profile in profiles:
            if profile["user_id"] in review_counts and profile["user_id"].startswith("reviewer_"):
                count = review_counts[profile["user_id"]]
                profile["taste"] = f"Оценки из отзывов · {count}"

        ratings_by_user_and_movie.update(review_ratings)
        return profiles, list(ratings_by_user_and_movie.values())

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/catalog")
    def catalog():
        return jsonify(movie_recommender.catalog())

    @app.get("/api/assistant/status")
    def assistant_status():
        return jsonify(ai_assistant.status())

    @app.post("/api/assistant")
    def ask_assistant():
        payload = request.get_json(silent=True)
        question = payload.get("question", "").strip() if isinstance(payload, dict) else ""
        if not question:
            return jsonify({"error": "Напишите вопрос для ИИ-помощника."}), 400
        if len(question) > 2000:
            return jsonify({"error": "Вопрос не должен превышать 2000 символов."}), 400

        normalized_question = question.casefold()
        movie_request = any(
            term in normalized_question
            for term in (
                "фильм",
                "кино",
                "сериал",
                "посовет",
                "рекоменд",
                "посмотр",
                "movie",
                "film",
                "series",
                "watch",
                "recommend",
                ""
            )
        )
        catalog_movies = []
        if movie_request:
            matching_genres = {
                genre
                for genre in movie_recommender.genres()
                if genre.casefold() in normalized_question
                or GENRE_PRESENTATION.get(genre, "").casefold() in normalized_question
            }
            if matching_genres:
                catalog_movies = [
                    movie
                    for movie in movie_recommender.movies
                    if matching_genres.intersection(movie["genres"].split("|"))
                ][:10]
            else:
                catalog_movies = movie_recommender.popular_movies(limit=10)

        catalog_context = "\n".join(
            f"- {movie.get('title_ru') or movie['title']} ({movie['year']}): "
            f"{movie['genres'].replace('|', ', ')}"
            for movie in catalog_movies
        )
        try:
            answer = ai_assistant.answer(question, catalog_context)
        except AssistantError as error:
            return jsonify({"error": str(error)}), error.status_code
        return jsonify({"answer": answer})

    @app.get("/api/profiles")
    def profiles():
        profiles, _ = viewer_data()
        return jsonify(profiles)

    @app.get("/api/genres")
    def genres():
        return jsonify(movie_recommender.genres())

    @app.get("/api/popular")
    def popular():
        _, ratings = viewer_data()
        return jsonify(movie_recommender.popular_movies(ratings=ratings))

    @app.get("/api/rules")
    def rules():
        inferred_facts = movie_recommender.knowledge_base.infer()
        ratings_by_viewer_and_movie = {
            (rating["user_id"], rating["movie_id"]): float(rating["rating"])
            for rating in movie_recommender.ratings
        }
        liked_examples = []
        liked_facts = sorted(
            (fact for fact in inferred_facts if fact[0] == "likes"),
            key=lambda fact: (
                -ratings_by_viewer_and_movie[(fact[1], fact[2])],
                movie_recommender.profile_by_id[fact[1]]["name"],
                movie_recommender.movie_by_id[fact[2]]["title"],
            ),
        )
        for _, user_id, movie_id in liked_facts:
            rating = ratings_by_viewer_and_movie[(user_id, movie_id)]
            liked_examples.append(
                {
                    "viewer": movie_recommender.profile_by_id[user_id]["name"],
                    "movie": movie_recommender.movie_by_id[movie_id]["title"],
                    "movie_ru": movie_recommender.movie_by_id[movie_id]["title_ru"],
                    "rating": int(rating) if rating.is_integer() else rating,
                }
            )

        genres_by_viewer = {}
        for fact in inferred_facts:
            if fact[0] != "prefers_genre":
                continue
            _, user_id, genre = fact
            genres_by_viewer.setdefault(user_id, set()).add(genre)
        genre_examples = [
            {
                "viewer": movie_recommender.profile_by_id[user_id]["name"],
                "genres": sorted(genres),
            }
            for user_id, genres in sorted(
                genres_by_viewer.items(),
                key=lambda item: movie_recommender.profile_by_id[item[0]]["name"],
            )
        ]

        return jsonify(
            [
                {
                    "name": rule.name,
                    "condition": rule.condition,
                    "action": rule.action,
                    **RULE_PRESENTATION.get(rule.name, {}),
                    **(
                        {
                            "result": (
                                "Факт: фильм подходит зрителю, если совпал хотя бы один "
                                "из его любимых жанров. Жанры каталога: "
                                + ", ".join(
                                    GENRE_PRESENTATION.get(genre, genre)
                                    for genre in movie_recommender.genres()
                                )
                                + "."
                            )
                        }
                        if rule.name == "R3"
                        else {}
                    ),
                    **(
                        {
                            "examples": liked_examples,
                            "example_count": len(liked_examples),
                        }
                        if rule.name == "R1"
                        else {}
                    ),
                    **(
                        {
                            "examples": genre_examples,
                            "example_count": len(genre_examples),
                        }
                        if rule.name == "R2"
                        else {}
                    ),
                }
                for rule in movie_recommender.knowledge_base.RULES
            ]
        )

    @app.get("/api/frames")
    def frames():
        return jsonify(movie_recommender.frame_model.describe())

    @app.get("/api/classification/results")
    def classification_results():
        report_path = BASE_DIR / "data" / "rating_classification_metrics.json"
        dataset_path = BASE_DIR / "data" / "rating_classification.csv"
        try:
            with report_path.open(encoding="utf-8") as file:
                report = json.load(file)
            with dataset_path.open(encoding="utf-8", newline="") as file:
                dataset_rows = list(csv.DictReader(file))

            report["dataset_preview"] = []
            seen_viewers = set()
            for sample in dataset_rows:
                user_id = sample["user_id"]
                if user_id in seen_viewers:
                    continue
                seen_viewers.add(user_id)
                movie = movie_recommender.movie_by_id.get(sample["movie_id"], {})
                profile = movie_recommender.profile_by_id.get(user_id, {})
                genres = [
                    GENRE_PRESENTATION.get(genre, genre)
                    for genre in movie.get("genres", "").split("|")
                    if genre
                ]
                report["dataset_preview"].append(
                    {
                        "viewer_name": profile.get("name", "Зритель"),
                        "movie_title": movie.get("title_ru") or movie.get("title") or sample["movie_id"],
                        "rating": float(sample["rating"]),
                        "liked": sample["liked"] == "1",
                        "genres": genres,
                        "director": movie.get("director", ""),
                        "cast": movie.get("cast", "").replace("|", ", "),
                        "overview": movie.get("overview_ru") or movie.get("overview", ""),
                    }
                )
                if len(report["dataset_preview"]) == 6:
                    break

            for example in report.get("neural_recognition_examples", []):
                movie = movie_recommender.movie_by_id.get(example["movie_id"], {})
                profile = movie_recommender.profile_by_id.get(example["user_id"], {})
                example["movie_title"] = movie.get("title_ru") or movie.get("title") or example["movie_id"]
                example["viewer_name"] = profile.get("name", "Зритель")
        except (OSError, json.JSONDecodeError) as error:
            return jsonify({"error": f"Результаты классификации недоступны: {error}"}), 503
        return jsonify(report)

    @app.get("/api/frames/network")
    def frame_network():
        return jsonify(movie_recommender.frame_model.semantic_network())

    @app.get("/api/frames/<path:instance_id>/related")
    def related_frame_objects(instance_id):
        try:
            related = movie_recommender.frame_model.related_objects(
                instance_id,
                query=request.args.get("q", ""),
                relation=request.args.get("relation", ""),
            )
        except ValueError as error:
            return jsonify({"error": str(error)}), 404
        return jsonify(related)

    @app.get("/api/frames/search")
    def search_frames():
        try:
            instances = movie_recommender.frame_model.search(
                query=request.args.get("q", ""),
                frame_class=request.args.get("class", ""),
            )
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        return jsonify(instances)

    @app.patch("/api/frames/<instance_id>/properties")
    def update_frame_properties(instance_id):
        payload = request.get_json(silent=True)
        properties = payload.get("properties") if isinstance(payload, dict) else None
        try:
            instance = movie_recommender.frame_model.update_properties(
                instance_id,
                properties,
            )
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        return jsonify({"instance": instance})

    @app.get("/api/comments")
    def comments():
        movie_id = request.args.get("movie_id", "")
        if movie_id not in movie_recommender.movie_by_id:
            return jsonify({"error": "Фильм не найден"}), 404
        return jsonify([comment for comment in read_comments() if comment["movie_id"] == movie_id])

    @app.post("/api/comments")
    def add_comment():
        payload = request.get_json(silent=True) or {}
        movie_id = str(payload.get("movie_id", "")).strip()
        author = str(payload.get("author", "")).strip()
        text = str(payload.get("text", "")).strip()
        rating_value = payload.get("rating")
        rating = None
        if rating_value not in (None, ""):
            try:
                rating = int(rating_value)
            except (TypeError, ValueError):
                return jsonify({"error": "Оценка должна быть от 1 до 5"}), 400
        if movie_id not in movie_recommender.movie_by_id:
            return jsonify({"error": "Фильм не найден"}), 404
        if rating is not None and not 1 <= rating <= 5:
            return jsonify({"error": "Оценка должна быть от 1 до 5"}), 400
        if not author:
            return jsonify({"error": "Укажите ваше имя"}), 400
        if not text:
            return jsonify({"error": "Комментарий не может быть пустым"}), 400
        if len(author) > 80 or len(text) > 1000:
            return jsonify({"error": "Комментарий или имя слишком длинные"}), 400

        comment = {
            "movie_id": movie_id,
            "author": author,
            "text": text,
            "rating": rating,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        comments = read_comments()
        comments.append(comment)
        write_comments(comments)
        profiles, _ = viewer_data()
        profile_id = next(
            profile["user_id"]
            for profile in profiles
            if profile["name"].strip().casefold() == author.casefold()
        )
        return jsonify({**comment, "user_id": profile_id}), 201

    @app.get("/api/recommendations")
    def recommendations():
        mode = request.args.get("mode", "content")
        viewer_opinion = None
        try:
            if mode == "content":
                movie_id = request.args.get("movie_id", "")
                results = movie_recommender.recommend_by_content(movie_id)
                movie = movie_recommender.movie_by_id[movie_id]
                source = movie.get("title_ru", movie["title"])
            elif mode == "collaborative":
                movie_id = request.args.get("movie_id", "")
                _, ratings = viewer_data()
                results = movie_recommender.recommend_by_audience_taste(
                    movie_id,
                    ratings=ratings,
                )
                movie = movie_recommender.movie_by_id[movie_id]
                source = movie.get("title_ru", movie["title"])
            elif mode == "logic":
                user_id = request.args.get("user_id", "")
                profiles, ratings = viewer_data()
                profile_by_id = {profile["user_id"]: profile for profile in profiles}
                if user_id not in profile_by_id:
                    raise ValueError("Профиль не найден")
                results = movie_recommender.recommend_by_logic(
                    user_id,
                    profiles=profiles,
                    ratings=ratings,
                )
                source = profile_by_id[user_id]["name"]
                rated_movies = []
                for rating in ratings:
                    if rating["user_id"] != user_id:
                        continue
                    movie = movie_recommender.movie_by_id[rating["movie_id"]]
                    numeric_rating = float(rating["rating"])
                    rated_movies.append(
                        {
                            "movie_id": movie["movie_id"],
                            "title": movie["title"],
                            "title_ru": movie.get("title_ru", movie["title"]),
                            "rating": (
                                int(numeric_rating)
                                if numeric_rating.is_integer()
                                else numeric_rating
                            ),
                        }
                    )
                viewer_opinion = {
                    "viewer": source,
                    "rated_movies": sorted(
                        rated_movies,
                        key=lambda item: (-item["rating"], item["title_ru"].casefold()),
                    ),
                }
            elif mode == "genre":
                source = request.args.get("genre", "")
                results = movie_recommender.recommend_by_genre(source)
            else:
                return jsonify({"error": "Неизвестный способ подбора"}), 400
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

        response = {"mode": mode, "source": source, "recommendations": results}
        if viewer_opinion is not None:
            response["viewer_opinion"] = viewer_opinion
        return jsonify(response)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5050)))