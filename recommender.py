import csv
import hashlib
import json
import pickle
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from frame_model import FrameModel
from knowledge_base import MovieKnowledgeBase


class MovieRecommender:
    def __init__(self, data_dir, cache_path=None):
        self.data_dir = Path(data_dir)
        self.cache_path = (
            Path(cache_path)
            if cache_path is not None
            else self.data_dir / "cache" / "content_similarity.pkl"
        )
        self.movies = self._read_csv("movies.csv")
        try:
            with (self.data_dir / "movie_localizations.json").open(encoding="utf-8") as file:
                localizations = json.load(file)
        except (OSError, json.JSONDecodeError):
            localizations = {}
        for movie in self.movies:
            localization = localizations.get(movie["movie_id"], {})
            movie["title_ru"] = localization.get("title_ru") or movie["title"]
            movie["original_language"] = localization.get("original_language", "en")
            if localization.get("poster_url"):
                movie["poster_url"] = localization["poster_url"]
        self.profiles = self._read_csv("profiles.csv")
        self.ratings = self._read_csv("ratings.csv")
        self.movie_by_id = {movie["movie_id"]: movie for movie in self.movies}
        self.profile_by_id = {profile["user_id"]: profile for profile in self.profiles}
        self.frame_model = FrameModel(self.movies, self.profiles, self.ratings)
        self.knowledge_base = MovieKnowledgeBase(self.movies, self.ratings)
        self.content_similarity = self._load_or_build_content_similarity()

    def _read_csv(self, filename):
        with (self.data_dir / filename).open(encoding="utf-8", newline="") as file:
            return list(csv.DictReader(file))

    def _content_fingerprint(self):
        return hashlib.sha256((self.data_dir / "movies.csv").read_bytes()).hexdigest()

    def _load_or_build_content_similarity(self):
        fingerprint = self._content_fingerprint()
        try:
            with self.cache_path.open("rb") as file:
                cached = pickle.load(file)
            matrix = cached.get("matrix")
            if (
                cached.get("fingerprint") == fingerprint
                and isinstance(matrix, np.ndarray)
                and matrix.shape == (len(self.movies), len(self.movies))
            ):
                return matrix
        except (OSError, EOFError, pickle.PickleError, AttributeError, TypeError, ValueError):
            pass

        documents = [
            " ".join(
                (
                    movie["genres"].replace("|", " "),
                    movie["overview"],
                    movie["cast"].replace("|", " "),
                    movie["director"],
                )
            )
            for movie in self.movies
        ]
        vectors = TfidfVectorizer(stop_words="english", ngram_range=(1, 2)).fit_transform(
            documents
        )
        matrix = cosine_similarity(vectors).astype(np.float32)

        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = self.cache_path.with_suffix(".tmp")
            with temporary_path.open("wb") as file:
                pickle.dump({"fingerprint": fingerprint, "matrix": matrix}, file)
            temporary_path.replace(self.cache_path)
        except OSError:
            pass
        return matrix

    def catalog(self):
        return self.movies

    def user_profiles(self):
        return self.profiles

    def genres(self):
        return sorted(
            {genre for movie in self.movies for genre in movie["genres"].split("|")}
        )

    def popular_movies(self, limit=6, ratings=None):
        ratings = self.ratings if ratings is None else ratings
        ratings_by_movie = {}
        for rating in ratings:
            ratings_by_movie.setdefault(rating["movie_id"], []).append(
                float(rating["rating"])
            )

        ranked = [
            (
                movie,
                ratings_by_movie[movie["movie_id"]],
            )
            for movie in self.movies
            if movie["movie_id"] in ratings_by_movie
        ]
        ranked.sort(
            key=lambda item: (
                -len(item[1]),
                -sum(item[1]) / len(item[1]),
                item[0]["title"],
            )
        )
        return [
            {
                **movie,
                "score": round(sum(ratings) / len(ratings), 2),
                "rating_count": len(ratings),
            }
            for movie, ratings in ranked[:limit]
        ]

    def recommend_by_genre(self, genre, limit=None):
        if genre not in self.genres():
            raise ValueError("Жанр не найден")

        ratings_by_movie = {}
        for rating in self.ratings:
            ratings_by_movie.setdefault(rating["movie_id"], []).append(float(rating["rating"]))

        ranked = []
        for movie in self.movies:
            if genre not in movie["genres"].split("|"):
                continue
            ratings = ratings_by_movie.get(movie["movie_id"], [])
            average_rating = sum(ratings) / len(ratings) if ratings else 0
            ranked.append((movie, average_rating))

        ranked.sort(key=lambda item: item[1], reverse=True)
        return [
            {
                **movie,
                "score": round(average_rating, 2),
                "score_label": "средняя оценка",
            }
            for movie, average_rating in ranked[:limit]
        ]

    def recommend_by_content(self, movie_id, limit=None):
        if movie_id not in self.movie_by_id:
            raise ValueError("Фильм не найден")

        movie_index = next(
            index for index, movie in enumerate(self.movies) if movie["movie_id"] == movie_id
        )
        scores = self.content_similarity[movie_index]
        selected_genres = set(self.movies[movie_index]["genres"].split("|"))
        ranked_indices = np.argsort(scores)[::-1]
        recommendations = []
        for index in ranked_indices:
            candidate_genres = set(self.movies[index]["genres"].split("|"))
            if index == movie_index or not selected_genres.intersection(candidate_genres):
                continue
            recommendations.append(
                {
                    **self.movies[index],
                    "score": round(float(scores[index]), 3),
                    "score_label": "сходство",
                }
            )
            if limit is not None and len(recommendations) == limit:
                break
        return recommendations

    def recommend_by_audience_taste(self, movie_id, limit=6, ratings=None):
        if movie_id not in self.movie_by_id:
            raise ValueError("Фильм не найден")
        ratings = self.ratings if ratings is None else ratings

        fans = {
            rating["user_id"]
            for rating in ratings
            if rating["movie_id"] == movie_id and float(rating["rating"]) >= 4
        }
        ratings_by_movie = {}
        for rating in ratings:
            candidate_id = rating["movie_id"]
            if candidate_id == movie_id or rating["user_id"] not in fans:
                continue
            candidate_rating = float(rating["rating"])
            if candidate_rating >= 4:
                ratings_by_movie.setdefault(candidate_id, []).append(candidate_rating)

        ranked = [
            (self.movie_by_id[candidate_id], candidate_ratings)
            for candidate_id, candidate_ratings in ratings_by_movie.items()
        ]
        ranked.sort(
            key=lambda item: (
                -sum(item[1]) / len(item[1]),
                -len(item[1]),
                item[0].get("title_ru", item[0]["title"]).casefold(),
            )
        )
        return [
            {
                **movie,
                "score": round(sum(candidate_ratings) / len(candidate_ratings), 2),
                "rating_count": len(candidate_ratings),
                "score_label": "оценка зрителей, которым понравился выбранный фильм",
            }
            for movie, candidate_ratings in ranked[:limit]
        ]

    def recommend_for_user(self, user_id, limit=6, profiles=None, ratings=None):
        profiles = self.profiles if profiles is None else profiles
        ratings = self.ratings if ratings is None else ratings
        profile_by_id = {profile["user_id"]: profile for profile in profiles}
        if user_id not in profile_by_id:
            raise ValueError("Профиль не найден")

        user_ids = [profile["user_id"] for profile in profiles]
        movie_ids = [movie["movie_id"] for movie in self.movies]
        user_index = user_ids.index(user_id)
        ratings_matrix = np.zeros((len(user_ids), len(movie_ids)), dtype=np.float32)
        movie_indices = {movie_id: index for index, movie_id in enumerate(movie_ids)}
        for rating in ratings:
            ratings_matrix[user_ids.index(rating["user_id"]), movie_indices[rating["movie_id"]]] = (
                float(rating["rating"])
            )

        similarities = cosine_similarity(ratings_matrix)[user_index]
        seen = set(np.flatnonzero(ratings_matrix[user_index]))
        weighted_scores = {}
        total_weights = {}
        for neighbor_index, similarity in enumerate(similarities):
            if neighbor_index == user_index or similarity <= 0:
                continue
            for movie_index, rating in enumerate(ratings_matrix[neighbor_index]):
                if rating <= 0 or movie_index in seen:
                    continue
                weighted_scores[movie_index] = (
                    weighted_scores.get(movie_index, 0.0) + float(similarity * rating)
                )
                total_weights[movie_index] = total_weights.get(movie_index, 0.0) + float(
                    similarity
                )

        ranked = sorted(
            weighted_scores,
            key=lambda index: weighted_scores[index] / total_weights[index],
            reverse=True,
        )[:limit]
        return [
            {
                **self.movies[index],
                "score": round(weighted_scores[index] / total_weights[index], 2),
                "score_label": "оценка похожих зрителей",
            }
            for index in ranked
        ]

    def recommend_by_logic(self, user_id, limit=6, profiles=None, ratings=None):
        profiles = self.profiles if profiles is None else profiles
        ratings = self.ratings if ratings is None else ratings
        profile_by_id = {profile["user_id"]: profile for profile in profiles}
        if user_id not in profile_by_id:
            raise ValueError("Профиль не найден")

        inferred_facts = MovieKnowledgeBase(self.movies, ratings).infer()
        preferred_genres = {
            fact[2]
            for fact in inferred_facts
            if fact[0] == "prefers_genre" and fact[1] == user_id
        }
        liked_titles_by_genre = {}
        liked_movies_by_genre = {}
        ratings_by_movie = {
            rating["movie_id"]: float(rating["rating"])
            for rating in ratings
            if rating["user_id"] == user_id
        }
        for fact in inferred_facts:
            if fact[0] != "likes" or fact[1] != user_id:
                continue
            liked_movie = self.movie_by_id[fact[2]]
            rating = ratings_by_movie[fact[2]]
            for genre in liked_movie["genres"].split("|"):
                liked_titles_by_genre.setdefault(genre, set()).add(liked_movie["title"])
                liked_movies_by_genre.setdefault(genre, {})[fact[2]] = {
                    "title": liked_movie["title"],
                    "rating": int(rating) if rating.is_integer() else rating,
                }

        recommendations = []
        for fact in inferred_facts:
            if fact[0] != "recommends" or fact[1] != user_id:
                continue
            movie = self.movie_by_id[fact[2]]
            candidate_genres = sorted(movie["genres"].split("|"))
            matched_genres = sorted(preferred_genres.intersection(candidate_genres))
            supporting_movies = {
                movie_id: liked_movie
                for genre in matched_genres
                for movie_id, liked_movie in liked_movies_by_genre[genre].items()
            }
            supporting_titles = sorted(
                {
                    title
                    for genre in matched_genres
                    for title in liked_titles_by_genre.get(genre, set())
                }
            )
            explanation = (
                f"Высокие оценки И жанры фильмов «{', '.join(supporting_titles)}» "
                f"вывели предпочтения: {', '.join(matched_genres)}. "
                "Совпало хотя бы одно предпочтение (ИЛИ); выбранный зритель ещё не оценивал фильм (НЕ rated). "
                "Фильм может быть без оценок в каталоге."
            )
            recommendations.append(
                {
                    **movie,
                    "score": len(matched_genres),
                    "score_label": "совпавшие предпочтения",
                    "matched_genres": matched_genres,
                    "explanation": explanation,
                    "reasoning": {
                        "viewer": profile_by_id[user_id]["name"],
                        "liked_movies": sorted(
                            supporting_movies.values(),
                            key=lambda liked_movie: liked_movie["title"],
                        ),
                        "candidate_genres": candidate_genres,
                        "matched_genres": matched_genres,
                        "genre_sources": [
                            {"genre": genre, **liked_movie}
                            for genre in matched_genres
                            for liked_movie in liked_movies_by_genre[genre].values()
                        ],
                        "candidate_is_unrated": (
                            "rated", user_id, movie["movie_id"]
                        ) not in inferred_facts,
                    },
                }
            )

        recommendations.sort(key=lambda movie: (-movie["score"], movie["title"]))
        return recommendations[:limit]