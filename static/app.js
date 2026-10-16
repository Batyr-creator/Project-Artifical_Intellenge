const form = document.querySelector("#recommendation-form");
const movieSelect = document.querySelector("#movie-select");
const profileSelect = document.querySelector("#profile-select");
const genreSelect = document.querySelector("#genre-select");
const movieField = document.querySelector("#movie-field");
const profileField = document.querySelector("#profile-field");
const genreField = document.querySelector("#genre-field");
const resultsGrid = document.querySelector("#results-grid");
const resultsContext = document.querySelector("#results-context");
const ruleList = document.querySelector("#rule-list");
const classifierDatasetSummary = document.querySelector("#classifier-dataset-summary");
const classifierValidation = document.querySelector("#classifier-validation");
const classifierStatus = document.querySelector("#classifier-status");
const classifierScoreboard = document.querySelector("#classifier-scoreboard");
const classifierConfusion = document.querySelector("#classifier-confusion");
const classifierRecognitionRows = document.querySelector("#classifier-recognition-rows");
const classifierPreviewRows = document.querySelector("#classifier-preview-rows");
const frameTree = document.querySelector("#frame-tree");
const frameExamples = document.querySelector("#frame-examples");
const framePropertyEditorContainer = document.querySelector("#frame-property-editor");
const frameInstanceSelect = document.querySelector("#frame-instance-select");
const frameShowButton = document.querySelector("#frame-show-button");
const frameSearchInput = document.querySelector("#frame-search");
const frameClassFilter = document.querySelector("#frame-class-filter");
const frameSearchStatus = document.querySelector("#frame-search-status");
const frameRelatedSearchInput = document.querySelector("#frame-related-search");
const frameRelatedSearchStatus = document.querySelector("#frame-related-search-status");
const frameRelatedResults = document.querySelector("#frame-related-results");
const frameHierarchyTab = document.querySelector("#frame-hierarchy-tab");
const frameInstancesTab = document.querySelector("#frame-instances-tab");
const frameTreePanel = document.querySelector("#frame-tree-panel");
const frameExamplesPanel = document.querySelector("#frame-examples-panel");
const resultsTitle = document.querySelector("#results-title");
const submitButton = form.querySelector(".submit-button");
const modeDescription = document.querySelector("#mode-description");
const assistantForm = document.querySelector("#assistant-form");
const assistantQuestion = document.querySelector("#assistant-question");
const assistantSubmit = document.querySelector("#assistant-submit");
const assistantStatus = document.querySelector("#assistant-status");
const assistantAnswer = document.querySelector("#assistant-answer");
let mode = "content";
let catalogById = new Map();
let frameInstances = [];
let frameSearchResults = [];
let frameMovieNamesById = new Map();
let frameDescriptionsByClass = new Map();
let frameSearchSequence = 0;
let frameRelatedSequence = 0;

const frameRelationNames = {
  has_genre: "Жанр",
  directed_by: "Режиссёр",
  features: "Актёр",
  rated: "Оценка",
};

const genreNames = {
  Action: "Боевик",
  Adventure: "Приключения",
  Animation: "Анимация",
  Biography: "Биография",
  Comedy: "Комедия",
  Crime: "Криминал",
  Drama: "Драма",
  Fantasy: "Фэнтези",
  Family: "Семейный",
  Horror: "Ужасы",
  Music: "Музыка",
  Mystery: "Детектив",
  Romance: "Романтика",
  "Science Fiction": "Фантастика",
  Thriller: "Триллер",
};
const genreExplanations = {
  Action: (title, synopsis) => `В «${title}» боевик раскрывается через столкновение героев с опасностью: ${synopsis}`,
  Adventure: (title, synopsis) => `Путь героев «${title}» начинается так: ${synopsis} Это история о движении к цели, характерная для приключений.`,
  Animation: (title, synopsis) => `Анимация помогает «${title}» оживить эту историю: ${synopsis}`,
  Biography: (title, synopsis) => `В основе «${title}» — человеческая судьба и испытания героя: ${synopsis}`,
  Comedy: (title, synopsis) => `Комедия «${title}» предлагает увидеть героев в неожиданных обстоятельствах: ${synopsis}`,
  Crime: (title, synopsis) => `Криминальная сторона «${title}» связана с такими событиями: ${synopsis}`,
  Drama: (title, synopsis) => `В центре драмы «${title}» — непростой опыт и переживания героев: ${synopsis}`,
  Fantasy: (title, synopsis) => `«${title}» приглашает в необычный мир, где возможно больше, чем в повседневной жизни: ${synopsis}`,
  Family: (title, synopsis) => `История «${title}» подойдёт для совместного просмотра: ${synopsis}`,
  Horror: (title, synopsis) => `В «${title}» тревога начинается с событий, которые нарушают привычный порядок: ${synopsis}`,
  Music: (title, synopsis) => `Музыка становится частью истории «${title}»: ${synopsis}`,
  Mystery: (title, synopsis) => `В «${title}» за событиями скрывается загадка, которую предстоит распутать: ${synopsis}`,
  Romance: (title, synopsis) => `В «${title}» чувства и отношения героев оказываются в центре внимания: ${synopsis}`,
  "Science Fiction": (title, synopsis) => `Фантастическая идея задаёт мир «${title}» и его возможности: ${synopsis}`,
  Thriller: (title, synopsis) => `«${title}» держит напряжение вокруг опасности и неизвестности: ${synopsis}`,
};
const languageNames = { en: "Английский", ru: "Русский", kk: "Казахский" };

async function loadOptions(endpoint, select, label) {
  const response = await fetch(endpoint);
  if (!response.ok) throw new Error("Не удалось загрузить каталог.");
  const options = await response.json();
  select.replaceChildren(new Option(label, ""));
  for (const item of options) {
    const optionLabel = item.taste || "Профиль по оценкам";
    select.add(new Option(optionLabel, item.user_id));
  }
  select.disabled = false;
  return options.length;
}

async function loadCatalogOptions() {
  const response = await fetch("/api/catalog");
  if (!response.ok) throw new Error("Не удалось загрузить каталог.");
  const movies = await response.json();
  catalogById = new Map(movies.map((movie) => [movie.movie_id, movie]));
  movieSelect.replaceChildren(new Option("Выберите фильм", ""));
  for (const movie of movies) {
    movieSelect.add(new Option(
      `${movie.title_ru || movie.title} (${movie.year})`,
      movie.movie_id,
    ));
  }
  movieSelect.disabled = false;
  return movies.length;
}

async function loadPopularMovies() {
  try {
    const response = await fetch("/api/popular");
    const movies = await response.json();
    if (!response.ok) throw new Error(movies.error || "Не удалось загрузить популярные фильмы.");
    resultsTitle.textContent = "Популярные фильмы";
    resultsContext.textContent = "По оценкам зрителей";
    if (!movies.length) {
      showMessage("Пока недостаточно оценок, чтобы показать популярные фильмы.");
      return;
    }
    resultsGrid.replaceChildren(
      ...movies.map((movie, index) => movieCard(movie, index, "popular")),
    );
  } catch (error) {
    resultsTitle.textContent = "Популярные фильмы";
    resultsContext.textContent = "Не удалось загрузить";
    showMessage(error.message, true);
  }
}

async function loadRules() {
  const response = await fetch("/api/rules");
  if (!response.ok) throw new Error("Не удалось загрузить базу правил.");
  const rules = await response.json();
  ruleList.replaceChildren(...rules.map((rule) => {
    const item = document.createElement("li");
    item.className = "rule-item";
    const header = document.createElement("div");
    header.className = "rule-card-header";
    const name = document.createElement("span");
    name.className = "rule-name";
    name.textContent = `ПРАВИЛО ${rule.name}`;
    const title = document.createElement("h3");
    title.className = "rule-title";
    title.textContent = rule.title;
    const explanation = document.createElement("p");
    explanation.className = "rule-explanation";
    explanation.textContent = rule.explanation;
    const result = document.createElement("p");
    result.className = "rule-result";
    result.textContent = rule.result;
    const cardContent = [header, explanation, result];
    if (rule.examples?.length) {
      const examples = document.createElement("section");
      examples.className = "rule-examples";
      const examplesLabel = document.createElement("p");
      examplesLabel.className = "rule-examples-label";
      const isGenreRule = rule.name === "R2";
      examplesLabel.textContent = isGenreRule
        ? `Жанры, которые нравятся зрителям (${rule.example_count})`
        : `Понравившиеся фильмы (${rule.example_count})`;
      const createExampleList = (items, label) => {
        const list = document.createElement("ul");
        list.className = "rule-example-list";
        list.setAttribute("aria-label", label);
        list.append(...items.map((example) => {
          const entry = document.createElement("li");
          entry.textContent = isGenreRule
            ? `${example.viewer}: ${example.genres.map((genre) => genreNames[genre] || genre).join(" · ")}`
            : `${example.viewer}: «${example.movie_ru || example.movie}» (${example.rating}/5)`;
          return entry;
        }));
        return list;
      };
      const visibleExamples = rule.examples.slice(0, 3);
      const remainingExamples = rule.examples.slice(visibleExamples.length);
      examples.append(examplesLabel, createExampleList(visibleExamples, "Примеры вывода"));
      if (remainingExamples.length) {
        const moreExamples = document.createElement("details");
        moreExamples.className = "rule-more-examples";
        const moreSummary = document.createElement("summary");
        moreSummary.textContent = isGenreRule
          ? `Показать ещё ${remainingExamples.length} зрителей`
          : `Показать ещё ${remainingExamples.length}`;
        moreExamples.append(
          moreSummary,
          createExampleList(remainingExamples, "Остальные примеры вывода"),
        );
        examples.append(moreExamples);
      }
      cardContent.push(examples);
    }
    if (rule.name === "R3") {
      const demo = document.createElement("section");
      demo.className = "rule-demo";
      const profileLabel = document.createElement("label");
      profileLabel.className = "rule-demo-field";
      profileLabel.htmlFor = "rule-demo-profile";
      const profileLabelText = document.createElement("span");
      profileLabelText.textContent = "Подобрать для зрителя";
      const demoProfileSelect = document.createElement("select");
      demoProfileSelect.id = "rule-demo-profile";
      demoProfileSelect.setAttribute("aria-label", "Выберите зрителя для демонстрации правила R3");
      demoProfileSelect.disabled = true;
      demoProfileSelect.add(new Option("Загружаем зрителей...", ""));
      profileLabel.append(profileLabelText, demoProfileSelect);
      const demoButton = document.createElement("button");
      demoButton.className = "rule-demo-button";
      demoButton.type = "button";
      demoButton.textContent = "Показать подходящий фильм";
      demoButton.disabled = true;
      const output = document.createElement("div");
      output.className = "rule-demo-output";
      output.setAttribute("aria-live", "polite");
      demoButton.addEventListener("click", () => showRuleRecommendation(
        demoProfileSelect.value,
        demoButton,
        output,
      ));
      demo.append(profileLabel, demoButton, output);
      cardContent.push(demo);
    }
    header.append(name, title);
    item.append(...cardContent);
    return item;
  }));
  return rules.length;
}

function syncRuleDemoProfiles() {
  const demoSelect = document.querySelector("#rule-demo-profile");
  if (!demoSelect) return;
  const options = Array.from(profileSelect.options)
    .filter((option) => option.value)
    .map((option) => new Option(option.textContent, option.value));
  demoSelect.replaceChildren(
    new Option(options.length ? "Выберите зрителя" : "Зрители не найдены", ""),
    ...options,
  );
  demoSelect.disabled = options.length === 0;
  const button = demoSelect.closest(".rule-demo")?.querySelector(".rule-demo-button");
  if (button) button.disabled = options.length === 0;
}

async function showRuleRecommendation(userId, button, output) {
  if (!userId) {
    output.textContent = "Сначала выберите зрителя.";
    return;
  }

  button.disabled = true;
  button.textContent = "Ищем фильм...";
  output.classList.remove("is-error");
  output.replaceChildren();
  try {
    const params = new URLSearchParams({ mode: "logic", user_id: userId });
    const response = await fetch(`/api/recommendations?${params}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Не удалось подобрать фильм.");
    const movie = data.recommendations[0];
    if (!movie) {
      output.textContent = "Для этого зрителя пока нет подходящих неоценённых фильмов.";
      return;
    }

    const result = document.createElement("article");
    result.className = "rule-demo-result";
    const poster = document.createElement("div");
    poster.className = "rule-demo-poster";
    if (movie.poster_url || movie.poster_path) {
      const image = document.createElement("img");
      image.src = movie.poster_url || `https://image.tmdb.org/t/p/w342${movie.poster_path}`;
      image.alt = `Постер фильма «${movie.title_ru || movie.title}»`;
      image.loading = "lazy";
      image.addEventListener("error", () => poster.classList.add("is-fallback"), { once: true });
      poster.append(image);
    } else {
      poster.classList.add("is-fallback");
    }
    const details = document.createElement("div");
    const label = document.createElement("p");
    label.className = "rule-demo-result-label";
    label.textContent = "Результат применения R3";
    const title = document.createElement("h4");
    title.textContent = `${movie.title_ru || movie.title} (${movie.year})`;
    const genreLabel = document.createElement("p");
    genreLabel.className = "rule-demo-genres";
    const matchedGenres = movie.matched_genres.length
      ? movie.matched_genres
      : movie.genres.split("|");
    genreLabel.textContent = `Совпавший жанр: ${matchedGenres
      .map((genre) => genreNames[genre] || genre)
      .join(" · ")}`;
    details.append(label, title, genreLabel);
    result.append(poster, details);
    output.replaceChildren(result);
  } catch (error) {
    output.textContent = error.message;
    output.classList.add("is-error");
  } finally {
    button.disabled = false;
    button.textContent = "Показать подходящий фильм";
  }
}

function frameBranch(frame, framesByName) {
  const item = document.createElement("li");
  item.className = "frame-branch";
  const node = document.createElement("details");
  node.className = "frame-node";
  const heading = document.createElement("summary");
  heading.className = "frame-node-heading";
  const name = document.createElement("h3");
  name.textContent = frame.name;
  const inheritance = document.createElement("span");
  inheritance.className = "frame-inheritance";
  inheritance.textContent = frame.parent ? `наследует: ${frame.parent}` : "корневой класс";
  heading.append(name, inheritance);
  const content = document.createElement("div");
  content.className = "frame-node-content";

  for (const [label, members] of [["Свойства", frame.properties], ["Связи", frame.relations]]) {
    const section = document.createElement("div");
    section.className = "frame-members";
    const sectionLabel = document.createElement("span");
    sectionLabel.className = "frame-members-label";
    sectionLabel.textContent = label;
    const list = document.createElement("div");
    list.className = "frame-chips";
    for (const [memberName, definition] of Object.entries(members)) {
      const chip = document.createElement("span");
      chip.className = "frame-chip";
      chip.textContent = label === "Связи"
        ? `${memberName} → ${definition.target}`
        : memberName;
      chip.title = definition.description;
      list.append(chip);
    }
    section.append(sectionLabel, list);
    content.append(section);
  }

  const formal = document.createElement("details");
  formal.className = "frame-formal";
  const formalSummary = document.createElement("summary");
  formalSummary.textContent = "Формальная запись фрейма";
  const notation = document.createElement("pre");
  notation.textContent = [
    `ФРЕЙМ ${frame.name}${frame.parent ? ` IS-A ${frame.parent}` : ""}`,
    `  СЛОТЫ: ${Object.keys(frame.properties).join(", ") || "нет"}`,
    `  СВЯЗИ: ${Object.entries(frame.relations)
      .map(([name, relation]) => `${name} → ${relation.target}`)
      .join("; ") || "нет"}`,
  ].join("\n");
  formal.append(formalSummary, notation);
  content.append(formal);
  node.append(heading, content);

  item.append(node);
  const children = frame.children.map((name) => framesByName.get(name)).filter(Boolean);
  if (children.length) {
    const list = document.createElement("ul");
    list.className = "frame-children";
    list.append(...children.map((child) => frameBranch(child, framesByName)));
    item.append(list);
  }
  return item;
}

function frameExample(title, instance, movieNamesById) {
  const article = document.createElement("article");
  article.className = "frame-example";
  const heading = document.createElement("h3");
  heading.textContent = title;
  const name = document.createElement("p");
  name.className = "frame-example-name";
  name.textContent = instance.properties.title_ru
    || instance.properties.title
    || instance.properties.name;
  const meta = document.createElement("div");
  meta.className = "frame-example-meta";
  const addMeta = (label, value) => {
    if (!value) return;
    const item = document.createElement("span");
    item.className = "frame-meta-item";
    const itemLabel = document.createElement("span");
    itemLabel.className = "frame-meta-label";
    itemLabel.textContent = label;
    const itemValue = document.createElement("span");
    itemValue.className = "frame-meta-value";
    itemValue.textContent = value;
    item.append(itemLabel, itemValue);
    meta.append(item);
  };
  const addChipGroup = (label, values) => {
    if (!values.length) return null;
    const group = document.createElement("section");
    group.className = "frame-example-group";
    const groupLabel = document.createElement("h4");
    groupLabel.textContent = label;
    const chips = document.createElement("div");
    chips.className = "frame-example-chips";
    for (const value of values) {
      const chip = document.createElement("span");
      chip.className = "frame-example-chip";
      chip.textContent = value;
      chips.append(chip);
    }
    group.append(groupLabel, chips);
    return group;
  };

  if (instance.class === "Фильм") {
    const language = languageNames[instance.properties.original_language]
      || instance.properties.original_language;
    addMeta("Год", instance.properties.year);
    addMeta("Язык оригинала", language);
    addMeta("ID", instance.properties.id);
    const directedBy = document.createElement("p");
    directedBy.className = "frame-example-director";
    directedBy.textContent = `Режиссёр · ${instance.relations.directed_by}`;
    const cast = addChipGroup("В ролях", instance.relations.features);
    const genres = addChipGroup(
      "Жанры",
      instance.relations.has_genre.map((genre) => genreNames[genre] || genre),
    );
    article.append(heading, name, meta, directedBy);
    if (genres) article.append(genres);
    if (cast) article.append(cast);
  } else {
    addMeta("ID зрителя", instance.properties.id);
    addMeta("Предпочтения", instance.properties.taste);
    const rated = document.createElement("section");
    rated.className = "frame-example-group frame-rated-group";
    const ratedHeading = document.createElement("h4");
    ratedHeading.textContent = `Оценённые фильмы · ${instance.relations.rated.length}`;
    const ratedList = document.createElement("ul");
    ratedList.className = "frame-rated-list";
    for (const rating of instance.relations.rated) {
      const item = document.createElement("li");
      const movieName = document.createElement("span");
      movieName.textContent = movieNamesById.get(rating.movie_id)
        || `Фильм ${rating.movie_id}`;
      const ratingValue = document.createElement("span");
      ratingValue.className = "frame-rated-score";
      ratingValue.textContent = `${rating.rating}/5`;
      item.append(movieName, ratingValue);
      ratedList.append(item);
    }
    rated.append(ratedHeading, ratedList);
    article.append(heading, name, meta, rated);
  }
  return article;
}

async function loadFrameModel() {
  const response = await fetch("/api/frames");
  if (!response.ok) throw new Error("Не удалось загрузить фреймовую модель.");
  const model = await response.json();
  frameInstances = model.instances;
  frameDescriptionsByClass = new Map(
    model.hierarchy.map((frame) => [frame.name, frame]),
  );
  const framesByName = new Map(model.hierarchy.map((frame) => [frame.name, frame]));
  const roots = model.hierarchy.filter((frame) => frame.parent === null);
  const tree = document.createElement("ul");
  tree.className = "frame-roots";
  tree.append(...roots.map((root) => frameBranch(root, framesByName)));
  frameTree.replaceChildren(tree);

  frameMovieNamesById = new Map(
    model.instances
      .filter((instance) => instance.class === "Фильм")
      .map((instance) => [
        instance.properties.id,
        instance.properties.title_ru || instance.properties.title,
      ]),
  );
  frameSearchInput.addEventListener("input", searchFrameInstances);
  frameClassFilter.addEventListener("change", searchFrameInstances);
  frameInstanceSelect.addEventListener("change", () => renderSelectedInstance());
  frameRelatedSearchInput.addEventListener("input", searchRelatedObjects);
  frameShowButton.addEventListener("click", () => {
    setFrameTab("instances");
    renderSelectedInstance();
  });
  await searchFrameInstances();
}

async function searchFrameInstances() {
  const sequence = ++frameSearchSequence;
  frameSearchStatus.textContent = "Ищем объекты...";
  const params = new URLSearchParams({
    q: frameSearchInput.value.trim(),
    class: frameClassFilter.value,
  });

  try {
    const response = await fetch(`/api/frames/search?${params}`);
    const instances = await response.json();
    if (!response.ok) throw new Error(instances.error || "Не удалось найти объекты.");
    if (sequence !== frameSearchSequence) return;

    const selectedId = frameInstanceSelect.value;
    frameSearchResults = instances;
    const groups = ["Фильм", "Зритель"]
      .map((frameClass) => {
        const matches = instances.filter((instance) => instance.class === frameClass);
        if (!matches.length) return null;
        const group = document.createElement("optgroup");
        group.label = `${frameClass === "Фильм" ? "Фильмы" : "Зрители"} · ${matches.length}`;
        group.append(...matches.map((instance) => {
          const label = instance.class === "Фильм"
            ? `${instance.properties.title_ru || instance.properties.title} (${instance.properties.year})`
            : instance.properties.name;
          return new Option(label, instance.properties.id);
        }));
        return group;
      })
      .filter(Boolean);
    frameInstanceSelect.replaceChildren(...groups);
    frameInstanceSelect.disabled = instances.length === 0;
    frameShowButton.disabled = instances.length === 0;
    frameSearchStatus.textContent = instances.length
      ? `Найдено объектов: ${instances.length}`
      : "Ничего не найдено. Измените запрос или класс.";

    const retainsSelection = instances.some(
      (instance) => instance.properties.id === selectedId,
    );
    if (retainsSelection) frameInstanceSelect.value = selectedId;
    renderSelectedInstance();
  } catch (error) {
    if (sequence !== frameSearchSequence) return;
    frameSearchResults = [];
    frameInstanceSelect.replaceChildren();
    frameInstanceSelect.disabled = true;
    frameShowButton.disabled = true;
    frameSearchStatus.textContent = error.message;
    frameExamples.replaceChildren();
    framePropertyEditorContainer.replaceChildren();
    frameRelatedSearchInput.disabled = true;
    frameRelatedResults.replaceChildren();
    frameRelatedSearchStatus.textContent = "Сначала выберите объект.";
  }
}

function renderSelectedInstance(statusMessage = "") {
  const instance = frameSearchResults.find(
    (item) => item.properties.id === frameInstanceSelect.value,
  );
  if (!instance) {
    frameExamples.replaceChildren();
    framePropertyEditorContainer.replaceChildren();
    frameRelatedSearchInput.disabled = true;
    frameRelatedResults.replaceChildren();
    frameRelatedSearchStatus.textContent = "Сначала выберите объект.";
    return;
  }

  frameRelatedSearchInput.disabled = false;
  frameExamples.replaceChildren(
    frameExample(instance.class, instance, frameMovieNamesById),
  );
  framePropertyEditorContainer.replaceChildren(createFramePropertyEditor(instance));
  searchRelatedObjects();
  if (statusMessage) {
    framePropertyEditorContainer.querySelector(".frame-edit-status").textContent = statusMessage;
  }
}

async function searchRelatedObjects() {
  const instanceId = frameInstanceSelect.value;
  if (!instanceId) return;

  const sequence = ++frameRelatedSequence;
  frameRelatedSearchStatus.textContent = "Ищем связанные объекты...";
  const params = new URLSearchParams({ q: frameRelatedSearchInput.value.trim() });
  try {
    const response = await fetch(
      `/api/frames/${encodeURIComponent(instanceId)}/related?${params}`,
    );
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Не удалось найти связи.");
    if (sequence !== frameRelatedSequence) return;

    const items = data.related.map((related) => {
      const node = related.node;
      const properties = node.properties;
      const label = properties.title_ru || properties.title || properties.name || node.id;
      const item = document.createElement("li");
      const detail = document.createElement("span");
      detail.className = "frame-related-detail";
      detail.textContent = `${frameRelationNames[related.relation] || related.relation} · ${node.class}`;
      const openable = node.class === "Фильм" || node.class === "Зритель";
      const object = openable ? document.createElement("button") : document.createElement("span");
      object.className = openable ? "frame-related-object is-link" : "frame-related-object";
      object.textContent = label;
      if (openable) {
        object.type = "button";
        object.addEventListener("click", async () => {
          frameClassFilter.value = node.class;
          frameSearchInput.value = label;
          await searchFrameInstances();
          if (frameSearchResults.some((match) => match.properties.id === properties.id)) {
            frameInstanceSelect.value = properties.id;
            renderSelectedInstance();
          }
        });
      }
      item.append(detail, object);
      if (related.properties.rating !== undefined) {
        const rating = document.createElement("span");
        rating.className = "frame-related-rating";
        rating.textContent = `${related.properties.rating}/5`;
        item.append(rating);
      }
      return item;
    });
    frameRelatedResults.replaceChildren(...items);
    frameRelatedSearchStatus.textContent = data.related.length
      ? `Связанных объектов: ${data.related.length}`
      : "Связанные объекты не найдены.";
  } catch (error) {
    if (sequence !== frameRelatedSequence) return;
    frameRelatedResults.replaceChildren();
    frameRelatedSearchStatus.textContent = error.message;
  }
}

function createFramePropertyEditor(instance) {
  const form = document.createElement("form");
  form.className = "frame-property-editor";
  const heading = document.createElement("div");
  heading.className = "frame-editor-heading";
  const title = document.createElement("h3");
  title.textContent = "Свойства объекта";
  const persistenceNote = document.createElement("p");
  persistenceNote.textContent = "Изменения сохраняются до перезапуска приложения.";
  heading.append(title, persistenceNote);

  const fields = document.createElement("div");
  fields.className = "frame-property-fields";
  const definitions = frameDescriptionsByClass.get(instance.class)?.properties || {};
  for (const [name, value] of Object.entries(instance.properties)) {
    if (name === "id") continue;
    const label = document.createElement("label");
    label.className = "frame-property-field";
    const labelText = document.createElement("span");
    labelText.textContent = `${name} · ${definitions[name]?.description || "Свойство объекта"}`;
    const control = name.startsWith("overview") || name === "taste"
      ? document.createElement("textarea")
      : document.createElement("input");
    control.name = name;
    control.value = value ?? "";
    control.maxLength = 5000;
    if (control instanceof HTMLTextAreaElement) control.rows = 3;
    label.append(labelText, control);
    fields.append(label);
  }

  const footer = document.createElement("div");
  footer.className = "frame-editor-footer";
  const status = document.createElement("p");
  status.className = "frame-edit-status";
  status.setAttribute("role", "status");
  const saveButton = document.createElement("button");
  saveButton.className = "frame-save-button";
  saveButton.type = "submit";
  saveButton.textContent = "Сохранить свойства";
  footer.append(status, saveButton);
  form.append(heading, fields, footer);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    saveButton.disabled = true;
    status.textContent = "Сохраняем...";
    try {
      const properties = Object.fromEntries(new FormData(form).entries());
      const response = await fetch(
        `/api/frames/${encodeURIComponent(instance.properties.id)}/properties`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ properties }),
        },
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Не удалось сохранить свойства.");

      const updated = data.instance;
      frameInstances = frameInstances.map((item) => (
        item.properties.id === updated.properties.id ? updated : item
      ));
      frameSearchResults = frameSearchResults.map((item) => (
        item.properties.id === updated.properties.id ? updated : item
      ));
      if (updated.class === "Фильм") {
        frameMovieNamesById.set(
          updated.properties.id,
          updated.properties.title_ru || updated.properties.title,
        );
      }
      renderSelectedInstance("Свойства сохранены.");
    } catch (error) {
      status.textContent = error.message;
      status.classList.add("is-error");
      saveButton.disabled = false;
    }
  });
  return form;
}

function setFrameTab(tab) {
  const showHierarchy = tab === "hierarchy";
  frameHierarchyTab.classList.toggle("is-active", showHierarchy);
  frameHierarchyTab.setAttribute("aria-selected", String(showHierarchy));
  frameInstancesTab.classList.toggle("is-active", !showHierarchy);
  frameInstancesTab.setAttribute("aria-selected", String(!showHierarchy));
  frameTreePanel.hidden = !showHierarchy;
  frameExamplesPanel.hidden = showHierarchy;
}

function setMode(nextMode) {
  mode = nextMode;
  const isContent = mode === "content";
  const isMovieMode = isContent || mode === "collaborative";
  const isProfile = mode === "logic";
  movieField.classList.toggle("is-hidden", !isMovieMode);
  profileField.classList.toggle("is-hidden", !isProfile);
  genreField.classList.toggle("is-hidden", mode !== "genre");
  movieSelect.disabled = !isMovieMode;
  profileSelect.disabled = mode !== "logic";
  genreSelect.disabled = mode !== "genre";
  if (mode === "collaborative") {
    movieField.querySelector(".field-label").textContent =
      "Фильм, который понравился зрителям";
    movieSelect.options[0].textContent = "Выберите фильм";
    modeDescription.textContent =
      "Выберите фильм — покажем другие фильмы, которые высоко оценили зрители, которым он понравился.";
  } else if (isContent) {
    movieField.querySelector(".field-label").textContent = "Мне понравился фильм";
    movieSelect.options[0].textContent = "Выберите фильм";
    modeDescription.textContent =
      "Найдём фильмы с похожими жанрами, сюжетом, актёрами и режиссёром.";
  } else if (mode === "logic") {
    modeDescription.textContent =
      "Выберите профиль — логические правила подберут фильмы по предпочтениям из высоких оценок.";
  } else {
    modeDescription.textContent =
      "Выберите жанр и посмотрите фильмы, которые к нему относятся.";
  }
  for (const tab of document.querySelectorAll(".mode-tab")) {
    const selected = tab.dataset.mode === mode;
    tab.classList.toggle("is-active", selected);
    tab.setAttribute("aria-selected", String(selected));
  }
}

function recommendationExplanation(movie, mode, source, selectedMovie) {
  if (mode === "content") {
    const selectedGenres = new Set(selectedMovie.genres.split("|"));
    const sharedGenres = movie.genres
      .split("|")
      .filter((genre) => selectedGenres.has(genre))
      .map((genre) => genreNames[genre] || genre);
    const genreText = sharedGenres.length
      ? `Общий жанр: ${sharedGenres.join(", ")}.`
      : "По жанрам есть тематическое пересечение.";
    return `Вы выбрали «${source}». ${genreText} Дополнительно сравниваются описание, актёры и режиссёр; итоговое сходство — ${Math.round(movie.score * 100)}%.`;
  }
  if (mode === "collaborative") {
    return `Фильм понравился зрителям, которым понравился и «${source}». Средняя оценка от них — ${movie.score} из 5 (${movie.rating_count} ${ratingCountLabel(movie.rating_count)}).`;
  }
  if (mode === "logic") {
    const reasoning = movie.reasoning;
    const likedTitles = reasoning.liked_movies
      .map((item) => `«${item.title}» (${item.rating}/5)`)
      .join(", ");
    const matchedGenres = reasoning.matched_genres
      .map((genre) => genreNames[genre] || genre)
      .join(", ");
    const candidateTitle = movie.title_ru || movie.title;
    return `В профиле «${reasoning.viewer}» высокие оценки ${likedTitles} указали на интерес к жанрам ${matchedGenres}. У фильма «${candidateTitle}» есть совпадение по этим жанрам; пользователь его ещё не оценивал, поэтому правила добавили его в подборку.`;
  }
  if (mode === "genre") {
    const title = movie.title_ru || movie.title;
    const synopsis = movie.overview_ru || movie.overview;
    const explainGenre = genreExplanations[source];
    if (synopsis && explainGenre) return explainGenre(title, synopsis);
    if (synopsis) return `Жанр «${genreNames[source] || source}» раскрывается в истории фильма «${title}»: ${synopsis}`;
    return `Фильм «${title}» относится к жанру «${genreNames[source] || source}».`;
  }
  return "";
}

function viewerOpinionPanel(opinion) {
  const panel = document.createElement("section");
  panel.className = "viewer-opinion";
  const heading = document.createElement("h3");
  heading.textContent = `Оценки зрителя: ${opinion.viewer}`;
  panel.append(heading);

  if (!opinion.rated_movies.length) {
    const emptyMessage = document.createElement("p");
    emptyMessage.textContent = "У этого профиля пока нет оценок — определить предпочтения по ним не получится.";
    panel.append(emptyMessage);
    return panel;
  }

  const description = document.createElement("p");
  description.textContent = "Вот реальные оценки, на которых основан умный подбор. Оценки 4–5 помогают определить жанры, которые зрителю нравятся.";
  const list = document.createElement("ul");
  for (const item of opinion.rated_movies) {
    const entry = document.createElement("li");
    entry.textContent = `${item.title_ru || item.title} — ${item.rating}/5`;
    list.append(entry);
  }
  panel.append(description, list);
  return panel;
}

function movieCard(movie, index, recommendationMode, source = "", selectedMovie = null) {
  const article = document.createElement("article");
  article.className = "movie-card";
  const displayTitle = movie.title_ru || movie.title;

  const poster = document.createElement("div");
  poster.className = `poster poster-${(index % 4) + 1}`;
  const posterImage = document.createElement("img");
  posterImage.className = "poster-image";
  posterImage.alt = `Постер фильма «${displayTitle}»`;
  posterImage.loading = "lazy";
  posterImage.decoding = "async";
  if (movie.poster_url || movie.poster_path) {
    posterImage.src = movie.poster_url
      || `https://image.tmdb.org/t/p/w342${movie.poster_path}`;
    posterImage.addEventListener("error", () => poster.classList.add("is-fallback"), { once: true });
  } else {
    poster.classList.add("is-fallback");
  }
  const posterTitle = document.createElement("span");
  posterTitle.className = "poster-title";
  posterTitle.textContent = displayTitle;
  const posterYear = document.createElement("span");
  posterYear.className = "poster-year";
  posterYear.textContent = movie.year;
  poster.append(posterImage, posterTitle, posterYear);

  const details = document.createElement("div");
  details.className = "movie-details";
  const genre = document.createElement("p");
  genre.className = "movie-genre";
  genre.textContent = movie.genres.split("|").slice(0, 2).join(" · ");
  const title = document.createElement("h3");
  title.textContent = displayTitle;
  const director = document.createElement("p");
  director.className = "movie-director";
  director.textContent = movie.director;
  const language = languageNames[movie.original_language];
  let languageNote;
  if (language && movie.original_language !== "en") {
    article.classList.add("has-local-language");
    languageNote = document.createElement("p");
    languageNote.className = "movie-language";
    languageNote.textContent = `Язык оригинала · ${language}`;
  }
  const score = document.createElement("p");
  score.className = "movie-score";
  score.textContent = recommendationMode === "collaborative"
    ? `Оценка зрителей · ${movie.score} / 5 · ${movie.rating_count} ${ratingCountLabel(movie.rating_count)}`
    : recommendationMode === "genre"
      ? `Средняя оценка · ${movie.score} / 5`
      : recommendationMode === "popular"
        ? `★ ${movie.score} / 5 · ${movie.rating_count} оценок`
      : recommendationMode === "logic"
        ? `Совпавшие жанры · ${movie.matched_genres.map((genre) => genreNames[genre] || genre).join(" · ")}`
        : `Сходство · ${Math.round(movie.score * 100)}%`;
  const comments = document.createElement("section");
  comments.className = "comments";
  comments.innerHTML = `
    <div class="comments-heading">
      <span>Реальные отзывы зрителей</span>
      <span class="comments-count">0</span>
    </div>
    <div class="comments-list"></div>
    <form class="comment-form">
      <input name="author" maxlength="80" placeholder="Ваше имя" aria-label="Ваше имя" required>
      <label class="review-rating-field">
        <span>Оценка · необязательно</span>
        <select name="rating" aria-label="Оценка фильма">
          <option value="" selected>Без оценки</option>
          <option value="5">5 / 5</option>
          <option value="4">4 / 5</option>
          <option value="3">3 / 5</option>
          <option value="2">2 / 5</option>
          <option value="1">1 / 5</option>
        </select>
      </label>
      <textarea name="text" maxlength="1000" rows="2" placeholder="Поделитесь впечатлением" aria-label="Комментарий" required></textarea>
      <button type="submit">Опубликовать отзыв</button>
    </form>`;
  const commentsList = comments.querySelector(".comments-list");
  const commentsCount = comments.querySelector(".comments-count");
  const commentForm = comments.querySelector(".comment-form");
  commentsList.textContent = "Загружаем отзывы...";

  function renderComments(items) {
    commentsCount.textContent = items.length;
    commentsList.replaceChildren();
    if (!items.length) {
      const emptyMessage = document.createElement("p");
      emptyMessage.className = "comment-empty";
      emptyMessage.textContent = "Пока нет отзывов об этом фильме. Оставьте первое мнение.";
      commentsList.append(emptyMessage);
      return;
    }

    for (const item of items) {
      const comment = document.createElement("p");
      comment.className = "comment";
      const author = document.createElement("strong");
      author.textContent = item.author;
      const rating = document.createElement("span");
      rating.className = "comment-rating";
      rating.textContent = item.rating ? `Оценка ${item.rating}/5` : "Без оценки";
      const text = document.createElement("span");
      text.textContent = item.text;
      comment.append(author, rating, text);
      commentsList.append(comment);
    }
  }

  function showCommentsError() {
    commentsCount.textContent = "!";
    commentsList.replaceChildren();
    const errorMessage = document.createElement("p");
    errorMessage.className = "comment-empty is-error";
    errorMessage.textContent = "Не удалось загрузить отзывы. Попробуйте обновить страницу.";
    commentsList.append(errorMessage);
  }

  commentForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submitComment = commentForm.querySelector("button");
    const formData = new FormData(commentForm);
    submitComment.disabled = true;
    try {
      const response = await fetch("/api/comments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          movie_id: movie.movie_id,
          author: formData.get("author"),
          text: formData.get("text"),
          rating: formData.get("rating"),
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Не удалось отправить комментарий.");
      renderComments([...currentComments, data]);
      currentComments.push(data);
      if (data.user_id && !Array.from(profileSelect.options).some(
        (option) => option.value === data.user_id,
      )) {
        profileSelect.add(new Option("Оценки из отзывов", data.user_id));
        syncRuleDemoProfiles();
      }
      commentForm.reset();
    } catch (error) {
      showMessage(error.message, true);
    } finally {
      submitComment.disabled = false;
    }
  });

  let currentComments = [];
  fetch(`/api/comments?movie_id=${encodeURIComponent(movie.movie_id)}`)
    .then((response) => {
      if (!response.ok) throw new Error("Не удалось загрузить отзывы.");
      return response.json();
    })
    .then((items) => {
      currentComments = items;
      renderComments(items);
    })
    .catch(showCommentsError);
  details.append(genre, title, director);
  if (languageNote) details.append(languageNote);
  if (recommendationMode !== "catalog") details.append(score);
  details.append(comments);
  if (["content", "collaborative", "logic", "genre"].includes(recommendationMode)) {
    const explanation = document.createElement("section");
    explanation.className = "logic-explanation";
    const explanationHeading = document.createElement("h4");
    explanationHeading.textContent = "Почему в подборке";
    const rationale = document.createElement("p");
    rationale.textContent = recommendationExplanation(
      movie,
      recommendationMode,
      source,
      selectedMovie,
    );
    explanation.append(explanationHeading, rationale);
    details.append(explanation);
  }
  if (recommendationMode === "logic") {
    const explanation = document.createElement("section");
    explanation.className = "logic-explanation";
    const synopsisHeading = document.createElement("h4");
    synopsisHeading.textContent = "О чём фильм";
    const synopsis = document.createElement("p");
    synopsis.textContent = movie.overview_ru || movie.overview || "Описание фильма пока отсутствует.";
    explanation.append(synopsisHeading, synopsis);
    details.append(explanation);
  }
  article.append(poster, details);
  return article;
}

function showMessage(message, isError = false) {
  resultsGrid.replaceChildren();
  const state = document.createElement("p");
  state.className = `empty-state${isError ? " is-error" : ""}`;
  state.textContent = message;
  resultsGrid.append(state);
}

function ratingCountLabel(count) {
  if (count % 10 === 1 && count % 100 !== 11) return "оценка";
  if (count % 10 >= 2 && count % 10 <= 4 && (count % 100 < 12 || count % 100 > 14)) {
    return "оценки";
  }
  return "оценок";
}

async function loadClassificationReport() {
  const response = await fetch("/api/classification/results");
  const report = await response.json();
  if (!response.ok) {
    throw new Error(report.error || "Не удалось загрузить результаты классификации.");
  }

  classifierDatasetSummary.textContent = `${report.samples} оценок · ${report.viewers} зрителей · ${report.class_distribution.liked} положительных · ${report.class_distribution.disliked} отрицательных`;
  classifierValidation.textContent = report.validation;
  const formatPercent = (value) => new Intl.NumberFormat("ru-RU", {
    style: "percent",
    maximumFractionDigits: 1,
  }).format(value);
  const metricDefinitions = [
    ["Доля верных ответов", "accuracy"],
    ["Точность для обоих классов", "balanced_accuracy"],
    ["Верность положительного прогноза", "precision_liked"],
    ["Найденные оценки 4–5", "recall_liked"],
    ["Общая оценка качества", "f1_liked"],
  ];
  const modelCards = [
    ["01", "Текстовая модель", "Логистическая регрессия", report.model, "text"],
    ["02", "Нейросеть", "Два слоя · 32 и 16 нейронов", report.neural_network, "neural"],
    ["03", "Простой прогноз", "Всем фильмам присвоен положительный класс", report.baseline, "baseline"],
  ].map(([number, title, subtitle, metrics, kind]) => {
    const card = document.createElement("article");
    card.className = `classifier-model-card classifier-model-card-${kind}`;
    const header = document.createElement("header");
    header.className = "classifier-model-heading";
    const slate = document.createElement("span");
    slate.className = "classifier-model-number";
    slate.textContent = `КАДР ${number}`;
    const name = document.createElement("h3");
    name.textContent = title;
    const description = document.createElement("p");
    description.textContent = subtitle;
    header.append(slate, name, description);

    const metricList = document.createElement("ul");
    metricList.className = "classifier-model-metrics";
    for (const [label, key] of metricDefinitions) {
      const item = document.createElement("li");
      const line = document.createElement("div");
      line.className = "classifier-model-metric-label";
      const metricName = document.createElement("span");
      metricName.textContent = label;
      const value = document.createElement("strong");
      value.textContent = formatPercent(metrics[key]);
      line.append(metricName, value);
      const track = document.createElement("span");
      track.className = "classifier-meter";
      track.setAttribute("role", "img");
      track.setAttribute("aria-label", `${label}: ${formatPercent(metrics[key])}`);
      const fill = document.createElement("span");
      fill.className = "classifier-meter-fill";
      fill.style.width = `${Math.max(0, Math.min(100, metrics[key] * 100))}%`;
      track.append(fill);
      item.append(line, track);
      metricList.append(item);
    }
    card.append(header, metricList);
    return card;
  });
  classifierScoreboard.replaceChildren(...modelCards);

  const [[trueNegative, falsePositive], [falseNegative, truePositive]] = report.neural_network.confusion_matrix;
  const confusionItems = [
    ["Фактически ниже 4 · сеть тоже сказала «не понравился»", trueNegative],
    ["Фактически ниже 4 · сеть ошиблась и сказала «понравился»", falsePositive],
    ["Фактически 4–5 · сеть ошиблась и сказала «не понравился»", falseNegative],
    ["Фактически 4–5 · сеть тоже сказала «понравился»", truePositive],
  ].map(([label, value]) => {
    const item = document.createElement("div");
    item.className = "classifier-confusion-item";
    const term = document.createElement("dt");
    term.textContent = label;
    const count = document.createElement("dd");
    count.textContent = value;
    item.append(term, count);
    return item;
  });
  classifierConfusion.replaceChildren(...confusionItems);

  const recognitionRows = report.neural_recognition_examples.map((example) => {
    const item = document.createElement("li");
    const heading = document.createElement("h4");
    heading.textContent = `${example.movie_title} · оценка ${example.viewer_name}`;
    const actual = example.actual_liked ? "понравился" : "не понравился";
    const predicted = example.predicted_liked ? "понравился" : "не понравился";
    const result = document.createElement("p");
    result.className = "classifier-preview-rating";
    result.textContent = `Оценка зрителя: ${Number(example.rating)}/5, фактически «${actual}».`;
    const prediction = document.createElement("p");
    prediction.className = "classifier-preview-text";
    prediction.textContent = `Прогноз сети: «${predicted}». Вероятность, что фильм понравится: ${formatPercent(example.probability_liked)}. ${actual === predicted ? "Ответ верный." : "Сеть ошиблась."}`;
    item.append(heading, result, prediction);
    return item;
  });
  classifierRecognitionRows.replaceChildren(...recognitionRows);

  const previewRows = report.dataset_preview.map((sample) => {
    const item = document.createElement("li");
    const heading = document.createElement("h4");
    heading.textContent = `${sample.movie_title} · зритель ${sample.viewer_name}`;
    const rating = document.createElement("p");
    rating.className = "classifier-preview-rating";
    rating.textContent = `Оценка: ${Number(sample.rating)}/5 · ${sample.liked ? "понравился" : "не понравился"}`;
    const features = document.createElement("p");
    features.className = "classifier-preview-features";
    for (const [label, value] of [
      ["Жанры", sample.genres.join(", ")],
      ["Режиссёр", sample.director],
      ["В ролях", sample.cast],
      ["Сюжет", sample.overview],
    ]) {
      const line = document.createElement("p");
      const term = document.createElement("strong");
      term.textContent = `${label}: `;
      const description = document.createElement("span");
      description.textContent = value.length > 180 ? `${value.slice(0, 180)}…` : value;
      line.append(term, description);
      features.append(line);
    }
    item.append(heading, rating, features);
    return item;
  });
  classifierPreviewRows.replaceChildren(...previewRows);
  classifierStatus.textContent = report.neural_network.balanced_accuracy > report.baseline.balanced_accuracy
    ? "Модель превзошла простой прогноз по сбалансированной точности."
    : "Простой прогноз оказался лучше по сбалансированной точности. На 54 оценках результат предварительный.";
}

async function requestRecommendations(event) {
  event.preventDefault();
  const selectedId = mode === "content"
    || mode === "collaborative"
    ? movieSelect.value
    : mode === "logic"
      ? profileSelect.value
      : genreSelect.value;
  if (!selectedId) {
    showMessage(mode === "content"
      ? "Сначала выберите фильм."
      : mode === "logic"
        ? "Сначала выберите профиль."
        : "Сначала выберите жанр.");
    return;
  }

  submitButton.disabled = true;
  submitButton.textContent = "Подбираем...";
  resultsTitle.textContent = mode === "collaborative"
    ? "Что ещё понравилось зрителям"
    : "Вам может понравиться";
  showMessage("Ищем подходящие истории...");
  const params = new URLSearchParams({ mode });
  const parameter = { content: "movie_id", collaborative: "movie_id", logic: "user_id", genre: "genre" }[mode];
  params.set(parameter, selectedId);
  try {
    const response = await fetch(`/api/recommendations?${params}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Не удалось получить рекомендации.");
    resultsContext.textContent = mode === "content"
      ? `Похоже на «${data.source}»`
      : mode === "collaborative"
        ? `Зрителям, которым понравился фильм «${data.source}»`
        : mode === "logic"
          ? `Логический вывод для профиля: ${data.source}`
        : `Жанр: ${genreNames[data.source] || data.source}`;
    if (!data.recommendations.length) {
      showMessage(mode === "collaborative"
        ? "Пока нет других фильмов с высокими оценками от зрителей, которым понравился этот фильм."
        : "Для этого выбора пока нет рекомендаций.");
      if (mode === "logic" && data.viewer_opinion) {
        resultsGrid.prepend(viewerOpinionPanel(data.viewer_opinion));
      }
      return;
    }
    resultsGrid.replaceChildren(
      ...(mode === "logic" && data.viewer_opinion
        ? [viewerOpinionPanel(data.viewer_opinion)]
        : []),
      ...data.recommendations.map((movie, index) => movieCard(
        movie,
        index,
        mode,
        data.source,
        mode === "content" ? catalogById.get(movieSelect.value) : null,
      )),
    );
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    submitButton.disabled = false;
    submitButton.innerHTML = 'Подобрать фильмы <span aria-hidden="true">↗</span>';
  }
}

async function requestAssistantAnswer(event) {
  event.preventDefault();
  const question = assistantQuestion.value.trim();
  if (!question) return;

  assistantSubmit.disabled = true;
  assistantSubmit.textContent = "Анализируем запрос...";
  assistantAnswer.hidden = false;
  assistantAnswer.classList.remove("is-error");
  assistantAnswer.textContent = "ИИ-помощник ищет решение и готовит ответ...";
  try {
    const response = await fetch("/api/assistant", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Не удалось получить ответ.");
    assistantAnswer.textContent = data.answer;
  } catch (error) {
    assistantAnswer.classList.add("is-error");
    assistantAnswer.textContent = error.message;
  } finally {
    assistantSubmit.disabled = false;
    assistantSubmit.innerHTML = 'Спросить ИИ <span aria-hidden="true">↗</span>';
  }
}

document.querySelectorAll(".mode-tab").forEach((tab) => {
  tab.addEventListener("click", () => setMode(tab.dataset.mode));
});
form.addEventListener("submit", requestRecommendations);
assistantForm.addEventListener("submit", requestAssistantAnswer);
fetch("/api/assistant/status")
  .then((response) => {
    if (!response.ok) throw new Error("Не удалось проверить подключение к ИИ.");
    return response.json();
  })
  .then(({ configured, message }) => {
    assistantStatus.textContent = message;
    assistantStatus.classList.toggle("is-unavailable", !configured);
  })
  .catch(() => {
    assistantStatus.textContent = "Не удалось проверить подключение";
    assistantStatus.classList.add("is-unavailable");
  });
frameHierarchyTab.addEventListener("click", () => setFrameTab("hierarchy"));
frameInstancesTab.addEventListener("click", () => setFrameTab("instances"));
if (window.location.hash === "#framebook") {
  document.querySelector("#framebook").open = true;
}
loadFrameModel().catch((error) => {
  const message = document.createElement("p");
  message.className = "frame-loading is-error";
  message.textContent = error.message;
  frameTree.replaceChildren(message);
});

Promise.all([
  loadCatalogOptions(),
  loadOptions("/api/profiles", profileSelect, "Выберите профиль"),
  loadRules(),
  fetch("/api/genres").then((response) => {
    if (!response.ok) throw new Error("Не удалось загрузить жанры.");
    return response.json();
  }).then((genres) => {
    genreSelect.replaceChildren(new Option("Выберите любой жанр", ""));
    for (const genre of genres) {
      genreSelect.add(new Option(genreNames[genre] || genre, genre));
    }
    genreSelect.disabled = false;
    return genres.length;
  }),
]).then(([movieCount]) => {
  syncRuleDemoProfiles();
  document.querySelector("#catalog-count").textContent = `Каталог · ${movieCount} фильмов`;
  document.querySelector("#catalog-total").textContent = `${movieCount} фильмов`;
}).catch((error) => {
  showMessage(error.message, true);
});
loadPopularMovies();
loadClassificationReport().catch((error) => {
  classifierStatus.textContent = error.message;
  classifierStatus.classList.add("is-error");
});