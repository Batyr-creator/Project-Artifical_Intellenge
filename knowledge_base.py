from dataclasses import dataclass
from typing import Callable


LIKE_THRESHOLD = 4.0


@dataclass(frozen=True)
class ProductionRule:
    name: str
    condition: str
    action: str
    fire: Callable[[set[tuple]], set[tuple]]


def _derive_likes(facts):
    return {
        ("likes", fact[1], fact[2])
        for fact in facts
        if fact[0] == "rating" and fact[3] >= LIKE_THRESHOLD
    }


def _derive_preferred_genres(facts):
    genres_by_movie = {}
    for fact in facts:
        if fact[0] == "genre":
            genres_by_movie.setdefault(fact[1], set()).add(fact[2])

    return {
        ("prefers_genre", fact[1], genre)
        for fact in facts
        if fact[0] == "likes"
        for genre in genres_by_movie.get(fact[2], set())
    }


def _derive_recommendations(facts):
    genres_by_movie = {}
    preferred_genres_by_user = {}
    rated = set()
    for fact in facts:
        if fact[0] == "genre":
            genres_by_movie.setdefault(fact[1], set()).add(fact[2])
        elif fact[0] == "prefers_genre":
            preferred_genres_by_user.setdefault(fact[1], set()).add(fact[2])
        elif fact[0] == "rated":
            rated.add((fact[1], fact[2]))

    return {
        ("recommends", user_id, movie_id)
        for user_id, preferred_genres in preferred_genres_by_user.items()
        for movie_id, movie_genres in genres_by_movie.items()
        if preferred_genres.intersection(movie_genres)
        and (user_id, movie_id) not in rated
    }


class MovieKnowledgeBase:
    RULES = (
        ProductionRule(
            "R1",
            "rating(U, M, R) AND R >= 4",
            "likes(U, M)",
            _derive_likes,
        ),
        ProductionRule(
            "R2",
            "likes(U, M) AND genre(M, G)",
            "prefers_genre(U, G)",
            _derive_preferred_genres,
        ),
        ProductionRule(
            "R3",
            "prefers_genre(U, G) AND genre(C, G) AND NOT rated(U, C)",
            "recommends(U, C)",
            _derive_recommendations,
        ),
    )
    LIKE_THRESHOLD = LIKE_THRESHOLD

    def __init__(self, movies, ratings):
        self.facts = set()
        for movie in movies:
            for genre in movie["genres"].split("|"):
                self.facts.add(("genre", movie["movie_id"], genre))

        for rating in ratings:
            user_id = rating["user_id"]
            movie_id = rating["movie_id"]
            self.facts.add(("rated", user_id, movie_id))
            self.facts.add(("rating", user_id, movie_id, float(rating["rating"])))

    def infer(self):
        working_memory = set(self.facts)
        while True:
            agenda = set()
            for rule in self.RULES:
                agenda.update(rule.fire(working_memory))

            new_facts = agenda.difference(working_memory)
            if not new_facts:
                return working_memory
            working_memory.update(new_facts)