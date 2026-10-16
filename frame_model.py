import json


class FrameModel:
    FRAME_DEFINITIONS = {
        "Сущность": {
            "parent": None,
            "properties": {"id": {"description": "Идентификатор объекта"}},
            "relations": {},
        },
        "Медиапроизведение": {
            "parent": "Сущность",
            "properties": {
                "title": {"description": "Название произведения"},
                "title_ru": {"description": "Название на русском"},
                "year": {"description": "Год выхода"},
                "overview": {"description": "Краткое описание"},
                "overview_ru": {"description": "Краткое описание на русском"},
                "original_language": {"description": "Язык оригинала"},
            },
            "relations": {
                "has_genre": {"target": "Жанр", "description": "Принадлежит жанрам"},
                "directed_by": {"target": "Режиссёр", "description": "Снято режиссёром"},
                "features": {"target": "Актёр", "description": "В ролях"},
            },
        },
        "Фильм": {
            "parent": "Медиапроизведение",
            "properties": {
                "media_type": {
                    "description": "Тип медиапроизведения",
                    "default": "Фильм",
                },
                "poster_path": {"description": "Путь к постеру"},
            },
            "relations": {},
        },
        "Участник": {
            "parent": "Сущность",
            "properties": {"name": {"description": "Имя участника системы"}},
            "relations": {},
        },
        "Зритель": {
            "parent": "Участник",
            "properties": {
                "taste": {"description": "Краткое описание вкусов зрителя"},
            },
            "relations": {
                "rated": {"target": "Фильм", "description": "Оценил фильм"},
            },
        },
    }

    def __init__(self, movies, profiles, ratings):
        self.instances = [self._build_movie_instance(movie) for movie in movies]

        ratings_by_user = {}
        for rating in ratings:
            ratings_by_user.setdefault(rating["user_id"], []).append(
                {"movie_id": rating["movie_id"], "rating": float(rating["rating"])}
            )

        self.instances.extend(
            self._build_viewer_instance(profile, ratings_by_user)
            for profile in profiles
        )

    @staticmethod
    def _build_movie_instance(movie):
        return {
            "class": "Фильм",
            "properties": {
                "id": movie["movie_id"],
                "title": movie["title"],
                "title_ru": movie.get("title_ru", movie["title"]),
                "year": movie["year"],
                "overview": movie["overview"],
                "overview_ru": movie.get("overview_ru", movie["overview"]),
                "original_language": movie.get("original_language", "en"),
                "media_type": "Фильм",
                "poster_path": movie["poster_path"],
            },
            "relations": {
                "has_genre": movie["genres"].split("|"),
                "directed_by": movie["director"],
                "features": movie["cast"].split("|"),
            },
        }

    @staticmethod
    def _build_viewer_instance(profile, ratings_by_user):
        return {
            "class": "Зритель",
            "properties": {
                "id": profile["user_id"],
                "name": profile["name"],
                "taste": profile["taste"],
            },
            "relations": {"rated": ratings_by_user.get(profile["user_id"], [])},
        }

    @classmethod
    def _inherited_members(cls, frame_name, member_name):
        members = {}
        parent = cls.FRAME_DEFINITIONS[frame_name]["parent"]
        if parent is not None:
            members.update(cls._inherited_members(parent, member_name))
        members.update(cls.FRAME_DEFINITIONS[frame_name][member_name])
        return members

    @classmethod
    def _describe_frame(cls, frame_name):
        definition = cls.FRAME_DEFINITIONS[frame_name]
        return {
            "name": frame_name,
            "parent": definition["parent"],
            "properties": cls._inherited_members(frame_name, "properties"),
            "relations": cls._inherited_members(frame_name, "relations"),
            "children": [
                name
                for name, child in cls.FRAME_DEFINITIONS.items()
                if child["parent"] == frame_name
            ],
        }

    def describe(self):
        return {
            "hierarchy": [
                self._describe_frame(name) for name in self.FRAME_DEFINITIONS
            ],
            "instances": self.instances,
        }

    def semantic_network(self):
        nodes = [
            {
                "id": str(instance["properties"]["id"]),
                "class": instance["class"],
                "properties": dict(instance["properties"]),
            }
            for instance in self.instances
        ]
        nodes_by_id = {node["id"]: node for node in nodes}
        edges = []

        def entity_node(entity_class, name):
            node_id = f"{entity_class}:{name}"
            if node_id not in nodes_by_id:
                node = {
                    "id": node_id,
                    "class": entity_class,
                    "properties": {"name": name},
                }
                nodes.append(node)
                nodes_by_id[node_id] = node
            return node_id

        for instance in self.instances:
            source = str(instance["properties"]["id"])
            relations = instance["relations"]
            if instance["class"] == "Фильм":
                for genre in relations["has_genre"]:
                    edges.append({
                        "source": source,
                        "target": entity_node("Жанр", genre),
                        "relation": "has_genre",
                    })
                director = relations["directed_by"]
                edges.append({
                    "source": source,
                    "target": entity_node("Режиссёр", director),
                    "relation": "directed_by",
                })
                for actor in relations["features"]:
                    edges.append({
                        "source": source,
                        "target": entity_node("Актёр", actor),
                        "relation": "features",
                    })
            elif instance["class"] == "Зритель":
                for rating in relations["rated"]:
                    target = str(rating["movie_id"])
                    if target in nodes_by_id:
                        edges.append({
                            "source": source,
                            "target": target,
                            "relation": "rated",
                            "properties": {"rating": rating["rating"]},
                        })

        return {"nodes": nodes, "edges": edges}

    def related_objects(self, instance_id, query="", relation=""):
        network = self.semantic_network()
        nodes_by_id = {node["id"]: node for node in network["nodes"]}
        instance_id = str(instance_id)
        instance = nodes_by_id.get(instance_id)
        if instance is None:
            raise ValueError("Объект не найден")

        normalized_query = query.strip().casefold()
        related = []
        for edge in network["edges"]:
            if relation and edge["relation"] != relation:
                continue
            if edge["source"] == instance_id:
                node_id = edge["target"]
                direction = "outgoing"
            elif edge["target"] == instance_id:
                node_id = edge["source"]
                direction = "incoming"
            else:
                continue
            node = nodes_by_id[node_id]
            if normalized_query and normalized_query not in json.dumps(
                node,
                ensure_ascii=False,
            ).casefold():
                continue
            related.append({
                "node": node,
                "relation": edge["relation"],
                "direction": direction,
                "properties": edge.get("properties", {}),
            })
        return {"instance": instance, "related": related}

    def search(self, query="", frame_class=""):
        normalized_query = query.strip().casefold()
        if frame_class and frame_class not in self.FRAME_DEFINITIONS:
            raise ValueError("Неизвестный класс фрейма")

        matches = []
        for instance in self.instances:
            if frame_class and instance["class"] != frame_class:
                continue
            if normalized_query and normalized_query not in json.dumps(
                instance,
                ensure_ascii=False,
            ).casefold():
                continue
            matches.append(instance)
        return matches

    def update_properties(self, instance_id, properties):
        instance = self._find_instance(instance_id)
        if instance is None:
            raise ValueError("Объект не найден")
        if not isinstance(properties, dict) or not properties:
            raise ValueError("Укажите свойства для изменения")

        allowed_properties = self._inherited_members(instance["class"], "properties")
        updates = {}
        for name, value in properties.items():
            if name == "id":
                raise ValueError("Идентификатор объекта нельзя изменить")
            if name not in allowed_properties or name not in instance["properties"]:
                raise ValueError(f"Свойство «{name}» не найдено")
            updates[name] = self._convert_property_value(
                name,
                value,
                instance["properties"][name],
            )

        instance["properties"].update(updates)
        return instance

    def _find_instance(self, instance_id):
        return next(
            (
                instance
                for instance in self.instances
                if str(instance["properties"].get("id")) == str(instance_id)
            ),
            None,
        )

    @staticmethod
    def _convert_property_value(name, value, current_value):
        if not isinstance(value, (str, int, float, bool)):
            raise ValueError(f"Недопустимое значение свойства «{name}»")
        if len(str(value)) > 5000:
            raise ValueError(f"Значение свойства «{name}» слишком длинное")

        if isinstance(current_value, bool):
            return bool(value)
        if isinstance(current_value, int):
            try:
                return int(value)
            except (TypeError, ValueError):
                raise ValueError(f"Свойство «{name}» должно быть целым числом")
        if isinstance(current_value, float):
            try:
                return float(value)
            except (TypeError, ValueError):
                raise ValueError(f"Свойство «{name}» должно быть числом")
        return str(value)