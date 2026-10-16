import tempfile
import unittest
from pathlib import Path

from app import create_app
from knowledge_base import MovieKnowledgeBase
from recommender import MovieRecommender


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class MovieRecommenderTests(unittest.TestCase):
    def setUp(self):
        self.cache_dir = tempfile.TemporaryDirectory()
        self.cache_path = Path(self.cache_dir.name) / "similarity.pkl"
        self.comments_path = Path(self.cache_dir.name) / "comments.json"
        self.recommender = MovieRecommender(DATA_DIR, self.cache_path)

    def tearDown(self):
        self.cache_dir.cleanup()

    def test_content_recommendations_exclude_selected_movie(self):
        recommendations = self.recommender.recommend_by_content("1")

        self.assertTrue(recommendations)
        self.assertNotIn("1", [movie["movie_id"] for movie in recommendations])
        self.assertEqual(recommendations[0]["score_label"], "сходство")

    def test_content_recommendations_always_share_a_genre(self):
        for movie in self.recommender.catalog():
            recommendations = self.recommender.recommend_by_content(movie["movie_id"])
            selected_genres = set(movie["genres"].split("|"))

            self.assertTrue(recommendations, movie["title"])
            self.assertTrue(
                all(
                    selected_genres.intersection(recommendation["genres"].split("|"))
                    for recommendation in recommendations
                ),
                movie["title"],
            )

    def test_collaborative_recommendations_exclude_rated_movies(self):
        recommendations = self.recommender.recommend_for_user("viewer_01")
        rated = {
            rating["movie_id"]
            for rating in self.recommender.ratings
            if rating["user_id"] == "viewer_01"
        }

        self.assertTrue(recommendations)
        self.assertTrue(rated.isdisjoint(movie["movie_id"] for movie in recommendations))

    def test_audience_taste_recommendations_use_high_ratings_from_fans(self):
        ratings = [
            {"user_id": "fan", "movie_id": "1", "rating": "5"},
            {"user_id": "fan", "movie_id": "2", "rating": "5"},
            {"user_id": "fan", "movie_id": "3", "rating": "3"},
            {"user_id": "not_a_fan", "movie_id": "1", "rating": "3"},
            {"user_id": "not_a_fan", "movie_id": "4", "rating": "5"},
        ]

        recommendations = self.recommender.recommend_by_audience_taste("1", ratings=ratings)

        self.assertEqual([movie["movie_id"] for movie in recommendations], ["2"])
        self.assertEqual(recommendations[0]["score"], 5)
        self.assertEqual(recommendations[0]["rating_count"], 1)

    def test_logical_recommendations_follow_inferred_preferences(self):
        inferred_facts = self.recommender.knowledge_base.infer()
        recommendations = self.recommender.recommend_by_logic("viewer_01")
        rated = {
            rating["movie_id"]
            for rating in self.recommender.ratings
            if rating["user_id"] == "viewer_01"
        }
        globally_rated = {rating["movie_id"] for rating in self.recommender.ratings}

        self.assertIn(("likes", "viewer_01", "1"), inferred_facts)
        self.assertIn(("prefers_genre", "viewer_01", "Science Fiction"), inferred_facts)
        self.assertTrue(recommendations)
        self.assertTrue(rated.isdisjoint(movie["movie_id"] for movie in recommendations))
        self.assertTrue(
            any(movie["movie_id"] not in globally_rated for movie in recommendations)
        )
        self.assertTrue(all(movie["matched_genres"] for movie in recommendations))
        self.assertTrue(all("ИЛИ" in movie["explanation"] for movie in recommendations))
        self.assertTrue(all("НЕ rated" in movie["explanation"] for movie in recommendations))
        reasoning = recommendations[0]["reasoning"]
        self.assertEqual(reasoning["viewer"], "Амина")
        self.assertTrue(reasoning["liked_movies"])
        self.assertTrue(reasoning["candidate_genres"])
        self.assertTrue(reasoning["matched_genres"])
        self.assertTrue(reasoning["genre_sources"])
        self.assertTrue(reasoning["candidate_is_unrated"])

    def test_logic_rules_apply_and_or_not(self):
        knowledge_base = MovieKnowledgeBase(
            [
                {"movie_id": "liked", "genres": "Drama|Mystery"},
                {"movie_id": "candidate", "genres": "Mystery"},
                {"movie_id": "rated_candidate", "genres": "Drama"},
                {"movie_id": "unrelated", "genres": "Action"},
            ],
            [
                {"user_id": "viewer", "movie_id": "liked", "rating": "5"},
                {"user_id": "viewer", "movie_id": "rated_candidate", "rating": "2"},
            ],
        )
        original_facts = set(knowledge_base.facts)

        inferred_facts = knowledge_base.infer()

        self.assertEqual([rule.name for rule in knowledge_base.RULES], ["R1", "R2", "R3"])
        self.assertEqual(inferred_facts, knowledge_base.infer())
        self.assertEqual(knowledge_base.facts, original_facts)
        self.assertIn(("prefers_genre", "viewer", "Drama"), inferred_facts)
        self.assertIn(("prefers_genre", "viewer", "Mystery"), inferred_facts)
        self.assertNotIn(("rated", "viewer", "candidate"), inferred_facts)
        self.assertIn(("recommends", "viewer", "candidate"), inferred_facts)
        self.assertNotIn(("likes", "viewer", "rated_candidate"), inferred_facts)
        self.assertNotIn(("recommends", "viewer", "rated_candidate"), inferred_facts)
        self.assertNotIn(("recommends", "viewer", "unrelated"), inferred_facts)

    def test_similarity_matrix_is_saved_and_reused(self):
        self.assertTrue(self.cache_path.exists())
        cached_recommender = MovieRecommender(DATA_DIR, self.cache_path)

        self.assertEqual(
            self.recommender.recommend_by_content("2"),
            cached_recommender.recommend_by_content("2"),
        )

    def test_unknown_movie_is_rejected(self):
        with self.assertRaises(ValueError):
            self.recommender.recommend_by_content("unknown")

    def test_genre_recommendations_only_return_selected_genre(self):
        recommendations = self.recommender.recommend_by_genre("Horror")

        self.assertTrue(recommendations)
        self.assertTrue(
            all("Horror" in movie["genres"].split("|") for movie in recommendations)
        )
        self.assertTrue(all(movie["score"] > 0 for movie in recommendations))

    def test_popular_movies_are_ranked_by_rating_count_and_expose_rating_summary(self):
        recommendations = self.recommender.popular_movies(limit=6)

        self.assertEqual(len(recommendations), 6)
        self.assertTrue(all(movie["rating_count"] > 0 for movie in recommendations))
        self.assertTrue(all(1 <= movie["score"] <= 5 for movie in recommendations))
        self.assertEqual(
            [movie["rating_count"] for movie in recommendations],
            sorted(
                (movie["rating_count"] for movie in recommendations),
                reverse=True,
            ),
        )

    def test_api_serves_all_recommendation_modes(self):
        client = create_app(self.recommender, self.comments_path).test_client()

        content_response = client.get("/api/recommendations?mode=content&movie_id=1")
        collaborative_response = client.get(
            "/api/recommendations?mode=collaborative&movie_id=1"
        )
        logic_response = client.get("/api/recommendations?mode=logic&user_id=viewer_01")
        genre_response = client.get("/api/recommendations?mode=genre&genre=Horror")
        rules_response = client.get("/api/rules")
        popular_response = client.get("/api/popular")
        homepage_response = client.get("/")

        self.assertEqual(content_response.status_code, 200)
        self.assertTrue(content_response.json["recommendations"])
        self.assertEqual(collaborative_response.status_code, 200)
        self.assertTrue(collaborative_response.json["recommendations"])
        self.assertEqual(
            collaborative_response.json["source"],
            self.recommender.movie_by_id["1"]["title_ru"],
        )
        self.assertNotIn(
            "1",
            [movie["movie_id"] for movie in collaborative_response.json["recommendations"]],
        )
        self.assertEqual(logic_response.status_code, 200)
        self.assertTrue(logic_response.json["recommendations"])
        self.assertTrue(logic_response.json["recommendations"][0]["explanation"])
        self.assertEqual(genre_response.status_code, 200)
        self.assertTrue(genre_response.json["recommendations"])
        self.assertEqual(popular_response.status_code, 200)
        self.assertTrue(popular_response.json)
        self.assertNotIn(b"browse-movie-select", homepage_response.data)
        self.assertNotIn("Показать фильм".encode(), homepage_response.data)
        self.assertIn("Выбрать способ подбора".encode(), homepage_response.data)
        self.assertIn("Выберите фильм, профиль зрителя или жанр".encode(), homepage_response.data)
        self.assertEqual(rules_response.status_code, 200)
        self.assertEqual(
            [rule["name"] for rule in rules_response.json],
            ["R1", "R2", "R3"],
        )
        rule_one = rules_response.json[0]
        rule_one_examples = rule_one["examples"]
        self.assertEqual(rule_one["example_count"], len(rule_one_examples))
        self.assertGreater(len(rule_one_examples), 3)
        self.assertTrue(
            any(
                example["viewer"] == "Амина"
                and example["movie"] == "Interstellar"
                and example["movie_ru"] == "Интерстеллар"
                and example["rating"] == 5
                for example in rule_one_examples
            )
        )
        rule_two = rules_response.json[1]
        self.assertEqual(rule_two["example_count"], len(rule_two["examples"]))
        amina_genres = next(
            example["genres"]
            for example in rule_two["examples"]
            if example["viewer"] == "Амина"
        )
        self.assertIn("Science Fiction", amina_genres)
        self.assertIn("Adventure", amina_genres)
        self.assertIn("любимому жанру", rules_response.json[2]["explanation"])
        self.assertIn("без оценок в каталоге", rules_response.json[2]["explanation"])
        self.assertIn("фантастика", rules_response.json[2]["result"])
        self.assertIn("приключения", rules_response.json[2]["result"])
        self.assertIn("ужасы", rules_response.json[2]["result"])

    def test_smart_recommendations_include_the_selected_viewers_real_ratings(self):
        client = create_app(self.recommender, self.comments_path).test_client()

        response = client.get(
            "/api/recommendations?mode=logic&user_id=viewer_01"
        )

        self.assertEqual(response.status_code, 200)
        opinion = response.json["viewer_opinion"]
        self.assertEqual(opinion["viewer"], "Амина")
        self.assertEqual(
            len(opinion["rated_movies"]),
            sum(rating["user_id"] == "viewer_01" for rating in self.recommender.ratings),
        )
        interstellar = next(
            movie for movie in opinion["rated_movies"] if movie["movie_id"] == "1"
        )
        self.assertEqual(interstellar["title_ru"], "Интерстеллар")
        self.assertEqual(interstellar["rating"], 5)

    def test_frame_model_exposes_hierarchy_inherited_slots_and_instances(self):
        client = create_app(self.recommender, self.comments_path).test_client()

        response = client.get("/api/frames")

        self.assertEqual(response.status_code, 200)
        model = response.json
        frames_by_name = {frame["name"]: frame for frame in model["hierarchy"]}
        film = frames_by_name["Фильм"]
        viewer = frames_by_name["Зритель"]
        movie_instance = next(
            item for item in model["instances"] if item["properties"]["id"] == "1"
        )
        viewer_instance = next(
            item
            for item in model["instances"]
            if item["properties"]["id"] == "viewer_01"
        )

        self.assertEqual(film["parent"], "Медиапроизведение")
        self.assertIn("title", film["properties"])
        self.assertIn("has_genre", film["relations"])
        self.assertEqual(viewer["parent"], "Участник")
        self.assertIn("rated", viewer["relations"])
        self.assertEqual(movie_instance["class"], "Фильм")
        self.assertEqual(movie_instance["properties"]["title_ru"], "Интерстеллар")
        self.assertIn("Science Fiction", movie_instance["relations"]["has_genre"])
        self.assertEqual(viewer_instance["class"], "Зритель")
        self.assertIn("taste", viewer["properties"])
        self.assertTrue(viewer_instance["properties"]["taste"])
        self.assertTrue(viewer_instance["relations"]["rated"])

    def test_frame_objects_can_be_searched_and_properties_updated(self):
        client = create_app(self.recommender, self.comments_path).test_client()

        search_response = client.get(
            "/api/frames/search?q=ИНТЕРСТЕЛЛАР&class=Фильм"
        )
        update_response = client.patch(
            "/api/frames/1/properties",
            json={"properties": {"title_ru": "Новое название"}},
        )
        updated_search = client.get("/api/frames/search?q=новое+название")
        immutable_id_response = client.patch(
            "/api/frames/1/properties",
            json={"properties": {"id": "999"}},
        )
        invalid_payload_response = client.patch(
            "/api/frames/1/properties",
            json=["invalid"],
        )

        self.assertEqual(search_response.status_code, 200)
        self.assertEqual(len(search_response.json), 1)
        self.assertEqual(search_response.json[0]["properties"]["id"], "1")
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(
            update_response.json["instance"]["properties"]["title_ru"],
            "Новое название",
        )
        self.assertEqual(updated_search.status_code, 200)
        self.assertEqual(updated_search.json[0]["properties"]["id"], "1")
        self.assertEqual(immutable_id_response.status_code, 400)
        self.assertEqual(invalid_payload_response.status_code, 400)

    def test_semantic_network_exposes_nodes_edges_and_related_object_search(self):
        client = create_app(self.recommender, self.comments_path).test_client()

        network_response = client.get("/api/frames/network")
        related_response = client.get("/api/frames/1/related?q=Science+Fiction")
        rated_response = client.get("/api/frames/viewer_01/related?relation=rated")
        missing_response = client.get("/api/frames/unknown/related")

        self.assertEqual(network_response.status_code, 200)
        network = network_response.json
        nodes_by_id = {node["id"]: node for node in network["nodes"]}
        self.assertEqual(nodes_by_id["1"]["class"], "Фильм")
        self.assertEqual(nodes_by_id["Жанр:Science Fiction"]["class"], "Жанр")
        self.assertTrue(
            any(
                edge["source"] == "1"
                and edge["target"] == "Жанр:Science Fiction"
                and edge["relation"] == "has_genre"
                for edge in network["edges"]
            )
        )
        self.assertEqual(related_response.status_code, 200)
        self.assertEqual(len(related_response.json["related"]), 1)
        self.assertEqual(
            related_response.json["related"][0]["node"]["properties"]["name"],
            "Science Fiction",
        )
        self.assertEqual(rated_response.status_code, 200)
        self.assertTrue(rated_response.json["related"])
        self.assertEqual(rated_response.json["related"][0]["node"]["class"], "Фильм")
        self.assertEqual(missing_response.status_code, 404)

    def test_comments_can_be_created_and_read_for_a_movie(self):
        client = create_app(self.recommender, self.comments_path).test_client()

        response = client.post(
            "/api/comments",
            json={
                "movie_id": "1",
                "author": "Анна",
                "text": "Очень сильный фильм.",
                "rating": 5,
            },
        )

        self.assertEqual(response.status_code, 201)
        comments_response = client.get("/api/comments?movie_id=1")
        self.assertEqual(comments_response.status_code, 200)
        self.assertEqual(comments_response.json[0]["text"], "Очень сильный фильм.")
        self.assertEqual(comments_response.json[0]["rating"], 5)

    def test_comment_authors_become_recommendation_profiles(self):
        client = create_app(self.recommender, self.comments_path).test_client()
        comment_response = client.post(
            "/api/comments",
            json={
                "movie_id": "1",
                "author": "Игорь",
                "text": "Отличный фильм.",
                "rating": 5,
            },
        )

        self.assertEqual(comment_response.status_code, 201)
        viewer_id = comment_response.json["user_id"]
        profiles_response = client.get("/api/profiles")
        profile = next(
            profile for profile in profiles_response.json if profile["user_id"] == viewer_id
        )
        self.assertEqual(profile["name"], "Игорь")
        self.assertIn("Оценки из отзывов", profile["taste"])

        collaborative_response = client.get(
            "/api/recommendations?mode=collaborative&movie_id=1"
        )
        logic_response = client.get(
            f"/api/recommendations?mode=logic&user_id={viewer_id}"
        )

        self.assertEqual(collaborative_response.status_code, 200)
        self.assertEqual(
            collaborative_response.json["source"],
            self.recommender.movie_by_id["1"]["title_ru"],
        )
        self.assertNotIn(
            "1",
            [
                movie["movie_id"]
                for movie in collaborative_response.json["recommendations"]
            ],
        )
        self.assertEqual(logic_response.status_code, 200)
        self.assertEqual(logic_response.json["source"], "Игорь")
        self.assertNotIn(
            "1",
            [movie["movie_id"] for movie in logic_response.json["recommendations"]],
        )

    def test_comments_can_be_created_without_rating_and_add_the_author_profile(self):
        client = create_app(self.recommender, self.comments_path).test_client()

        response = client.post(
            "/api/comments",
            json={
                "movie_id": "1",
                "author": "Новый зритель",
                "text": "Хороший фильм.",
            },
        )
        profiles_response = client.get("/api/profiles")
        profile = next(
            (
                profile
                for profile in profiles_response.json
                if profile["name"] == "Новый зритель"
            ),
            None,
        )

        out_of_range = client.post(
            "/api/comments",
            json={"movie_id": "1", "text": "Хороший фильм.", "rating": 6},
        )

        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json["rating"])
        self.assertIsNotNone(profile)
        self.assertEqual(profile["user_id"], response.json["user_id"])
        self.assertEqual(out_of_range.status_code, 400)

    def test_content_and_genre_recommendations_are_not_limited_to_six(self):
        content = self.recommender.recommend_by_content("1")
        genre = self.recommender.recommend_by_genre("Drama")

        self.assertGreater(len(content), 6)
        self.assertGreater(len(genre), 6)

    def test_catalog_contains_localized_films(self):
        catalog = self.recommender.catalog()
        language_counts = {
            language: sum(movie["original_language"] == language for movie in catalog)
            for language in ("en", "ru", "kk")
        }

        self.assertEqual(len(catalog), 58)
        self.assertEqual(language_counts, {"en": 50, "ru": 4, "kk": 4})
        self.assertTrue(all(movie["overview_ru"] for movie in catalog))
        self.assertTrue(all(movie["title_ru"] for movie in catalog))
        self.assertEqual(
            next(movie["title_ru"] for movie in catalog if movie["movie_id"] == "55"),
            "Меня зовут Кожа",
        )
        kyz_zhibek = next(movie for movie in catalog if movie["movie_id"] == "56")
        self.assertEqual(kyz_zhibek["poster_url"], "/static/kyz-zhibek.svg")
        tomiris = next(movie for movie in catalog if movie["movie_id"] == "57")
        self.assertEqual(tomiris["poster_url"], "/static/tomiris.svg")


if __name__ == "__main__":
    unittest.main()