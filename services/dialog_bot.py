"""
🎮 Ассистент для подбора видеоигр
1 большой промпт + строгое состояние через JSON Schema (Perplexity response_format)
Собирает 7 параметров: GPU, CPU, RAM, genre, subgenre, game_mode, age_rating
Сохраняет профиль в JSON файл
"""

import json
import requests
from datetime import datetime
from pathlib import Path

from owlready2 import get_ontology

# ============= КОНФИГУРАЦИЯ =============

ONTOLOGY_FILE = "GAMES.owl"# либо owl либо json
# ВСТАВЬ СВОЙ НОВЫЙ КЛЮЧ (тот, что уже засветился в сообщениях, лучше перевыпустить)
PERPLEXITY_API_KEY = "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"

PERPLEXITY_MODEL = "sonar"
PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"


# ============= ЗАГРУЗКА ОНТОЛОГИИ =============
# def load_ontology(filename: str) -> dict:
#     with open(filename, "r", encoding="utf-8") as f:
#         return json.load(f)


# ontology = load_ontology(ONTOLOGY_FILE)

# VALID_GENRES = ontology["game_ontology"]["classes"]["Genre"]["values"]
# VALID_SUBGENRES = ontology["game_ontology"]["classes"]["SubGenre"]["values"]
# VALID_GAME_MODES = ontology["game_ontology"]["classes"]["GameMode"]["values"]
# VALID_AGE_RATINGS = ontology["game_ontology"]["classes"]["AgeRating"]["values"]


def load_owl(path: str):
    p = Path(path)

    # Если запускаешь из PyCharm и файл лежит рядом со скриптом:
    if not p.is_absolute():
        p = (Path(__file__).resolve().parent / p).resolve()

    if not p.exists():
        raise FileNotFoundError(f"OWL файл не найден: {p}")

    # ВАЖНО: передаём обычный путь, без file://
    return get_ontology(str(p)).load()

def _candidate_strings(ind) -> list[str]:
    """
    Возвращает варианты строк, которые можно показывать/принимать от пользователя:
    - rdfs:label (если есть)
    - ind.name
    - ind.name с заменой '_' на ' ' (для удобства, если в OWL нет label)
    """
    cands = []

    # rdfs:label -> .label (список)
    if hasattr(ind, "label") and ind.label:
        # берём первый label
        cands.append(str(ind.label[0]))

    name = getattr(ind, "name", None)
    if name:
        cands.append(str(name))
        cands.append(str(name).replace("_", " "))

    # уникализация с сохранением порядка
    seen = set()
    out = []
    for x in cands:
        x = x.strip()
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def build_vocab(onto, class_name: str):
    """
    Возвращает:
    - valid_values: список допустимых строк для enum (уникальные)
    - value_to_individual: словарь {строка_lower: индивид} для нормализации
    """
    cls = getattr(onto, class_name, None)
    if cls is None:
        raise ValueError(f"В онтологии нет класса {class_name}")

    values = []
    mapping = {}

    for ind in cls.instances():
        for s in _candidate_strings(ind):
            values.append(s)
            mapping[s.lower()] = ind

    # уникализация с сохранением порядка
    seen = set()
    uniq = []
    for v in values:
        if v not in seen:
            seen.add(v)
            uniq.append(v)

    return uniq, mapping


onto = load_owl(ONTOLOGY_FILE)

VALID_GENRES, GENRE_MAP = build_vocab(onto, "Genre")
VALID_SUBGENRES, SUBGENRE_MAP = build_vocab(onto, "SubGenre")
VALID_GAME_MODES, MODE_MAP = build_vocab(onto, "GameMode")
VALID_AGE_RATINGS_TEST, AGE_MAP = build_vocab(onto, "AgeRating")

VALID_GENRES, GENRE_MAP = build_vocab(onto, "Genre")
VALID_SUBGENRES, SUBGENRE_MAP = build_vocab(onto, "SubGenre")
VALID_GAME_MODES, MODE_MAP = build_vocab(onto, "GameMode")

lists = {
    "VALID_GENRES": VALID_GENRES,
    "VALID_SUBGENRES": VALID_SUBGENRES,
    "VALID_GAME_MODES": VALID_GAME_MODES,
}

for name, lst in lists.items():
    seen = set()
    tmp = []
    for x in lst:
        x2 = x.replace("_", " ").strip()
        key = x2.lower()
        if key not in seen:
            seen.add(key)
            tmp.append(x2)
    lists[name] = tmp

VALID_GENRES = lists["VALID_GENRES"]
VALID_SUBGENRES = lists["VALID_SUBGENRES"]
VALID_GAME_MODES = lists["VALID_GAME_MODES"]
VALID_AGE_RATINGS = [x for x in VALID_AGE_RATINGS_TEST if "+" in x]

# print(VALID_GENRES)
# print(VALID_SUBGENRES)
# print(VALID_GAME_MODES)
# print(VALID_AGE_RATINGS)


# ============= 1 БОЛЬШОЙ ПРОМПТ =============

UNIFIED_SYSTEM_PROMPT = f"""
Ты — ассистент для сбора профиля игрока. Твоя задача — ТОЛЬКО собрать параметры и ничего больше.

СТРОГИЙ ЗАПРЕТ:
- Не предлагай игры, не давай советы, не объясняй термины, не рассуждай.
- Не пиши ничего кроме того, что нужно для сбора данных.

ПОРЯДОК ВОПРОСОВ (ОБЯЗАТЕЛЬНО):
1) Сначала собери gpu, cpu, ram — порядок СЛУЧАЙНЫЙ на каждый новый диалог.
2) Потом спроси genre (фиксированно).
3) Потом собери subgenre, game_mode, age_rating — порядок СЛУЧАЙНЫЙ.

ПАРАМЕТРЫ (всего 7):
1) gpu (строка) — видеокарта, свободный ввод
2) cpu (строка) — процессор, свободный ввод
3) ram (число, ГБ) — 1..256
4) genre — строго из списка
5) subgenre — строго из списка ИЛИ "любой"
6) game_mode — строго из списка
7) age_rating — строго из списка

СПИСКИ ДЛЯ ПРОВЕРКИ:
Жанры: {", ".join(VALID_GENRES)}
Поджанры: {", ".join(VALID_SUBGENRES)}
Режимы: {", ".join(VALID_GAME_MODES)}
Возраст: {", ".join(VALID_AGE_RATINGS)}

ПРАВИЛА СПИСКОВ (ОЧЕНЬ ВАЖНО):
- В обычном вопросе НЕ перечисляй варианты жанров/поджанров/режимов/возрастов.
- Печатай список ТОЛЬКО если пользователь ошибся (значение не из базы) ИЛИ если пользователь попросил "список"/"варианты".
- При ошибке: "Такого значения нет. Выбери из: <список>".

ПОВЕДЕНИЕ:
- Всегда используй CURRENT_STATE и заполняй только пустые поля.
- Не спрашивай повторно то, что уже заполнено.
- Если пользователь дал сразу несколько параметров — заполни несколько.
- Если ввод не распознан/невалиден — переспроси ТОЛЬКО про текущий параметр.

ФОРМАТ ДЛЯ ПОЛЬЗОВАТЕЛЯ:
- Коротко: 1 строка подтверждения/ошибки + 1 вопрос.
- Всегда только 1 вопрос.

ВАЖНО:
- Верни ответ СТРОГО в JSON по схеме response_format (без markdown и пояснений).
""".strip()


# ============= JSON SCHEMA (жёсткий формат ответа) =============

def build_response_schema():
    def nullable_string():
        return {"anyOf": [{"type": "string"}, {"type": "null"}]}

    def nullable_int():
        return {"anyOf": [{"type": "integer"}, {"type": "null"}]}

    def nullable_enum(values):
        return {"anyOf": [{"type": "string", "enum": values}, {"type": "null"}]}

    subgenre_values = list(VALID_SUBGENRES) + ["любой"]

    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["assistant_message", "state"],
        "properties": {
            "assistant_message": {"type": "string"},
            "state": {
                "type": "object",
                "additionalProperties": False,
                "required": ["pc_specs", "game_preferences", "done"],
                "properties": {
                    "pc_specs": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["gpu", "cpu", "ram"],
                        "properties": {
                            "gpu": nullable_string(),
                            "cpu": nullable_string(),
                            "ram": nullable_int(),
                        },
                    },
                    "game_preferences": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["genre", "subgenre", "game_mode", "age_rating"],
                        "properties": {
                            "genre": nullable_enum(list(VALID_GENRES)),
                            "subgenre": nullable_enum(subgenre_values),
                            "game_mode": nullable_enum(list(VALID_GAME_MODES)),
                            "age_rating": nullable_enum(list(VALID_AGE_RATINGS)),
                        },
                    },
                    "done": {"type": "boolean"},
                },
            },
        },
    }
    return schema


RESPONSE_SCHEMA = build_response_schema()


# ============= PERPLEXITY API =============

def call_perplexity(messages):
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": PERPLEXITY_MODEL,
        "messages": [{"role": "system", "content": UNIFIED_SYSTEM_PROMPT}] + messages,
        "temperature": 0.1,
        "max_tokens": 450,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "game_profile",
                "strict": True,
                "schema": RESPONSE_SCHEMA
            }
        }
    }

    try:
        r = requests.post(PERPLEXITY_URL, json=payload, headers=headers, timeout=60)
    except requests.RequestException as e:
        return None, f"Ошибка сети: {e}"

    if r.status_code == 401:
        return None, f"401 Unauthorized. Проверь API-ключ. Ответ сервера: {r.text}"

    if not r.ok:
        return None, f"HTTP {r.status_code}. Ответ сервера: {r.text}"

    try:
        data = r.json()
    except ValueError:
        return None, f"Сервер вернул не-JSON: {r.text}"

    try:
        content = data["choices"][0]["message"]["content"]
    except Exception:
        return None, f"Неожиданный формат ответа API: {data}"

    return content, None


# ============= ДИАЛОГОВЫЙ АССИСТЕНТ =============

class GameAssistant:
    def __init__(self):
        self.state = {
            "pc_specs": {"gpu": None, "cpu": None, "ram": None},
            "game_preferences": {"genre": None, "subgenre": None, "game_mode": None, "age_rating": None},
            "done": False,
        }
        self.history = []

    def _force_done_if_complete(self):
        pc = self.state["pc_specs"]
        gp = self.state["game_preferences"]
        all_filled = all(v is not None for v in pc.values()) and all(v is not None for v in gp.values())
        if all_filled:
            self.state["done"] = True

    def is_done(self):
        self._force_done_if_complete()
        return bool(self.state.get("done"))

    def build_profile_payload(self) -> dict:
        return {
        "timestamp": datetime.now().isoformat(),
        "pc_specs": self.state["pc_specs"],
        "game_preferences": self.state["game_preferences"],
        }

    def build_profile_json(self) -> str:
        payload = self.build_profile_payload()
        return json.dumps(payload, ensure_ascii=False, indent=4)

    def user_turn(self, user_input: str) -> str:
        user_payload = {
            "user_input": user_input,
            "CURRENT_STATE": self.state
        }

        self.history.append({
            "role": "user",
            "content": json.dumps(user_payload, ensure_ascii=False)
        })

        raw, err = call_perplexity(self.history)
        if err:
            return err

        # raw должен быть JSON по схеме
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            # попробуем один раз попросить модель повторить строго JSON
            self.history.append({"role": "assistant", "content": raw})
            self.history.append({
                "role": "user",
                "content": "ПОВТОРИ СТРОГО JSON по схеме. Без текста и без markdown."
            })
            raw2, err2 = call_perplexity(self.history)
            if err2:
                return err2
            try:
                obj = json.loads(raw2)
                raw = raw2
            except json.JSONDecodeError:
                return "Модель не вернула JSON. Проверь, поддерживается ли response_format на твоём ключе/тарифе."

        if "state" in obj and isinstance(obj["state"], dict):
            self.state = obj["state"]
            self._force_done_if_complete()

        assistant_message = str(obj.get("assistant_message", "")).strip()

        # сохраняем “как есть” в историю (чтобы память совпадала)
        self.history.append({"role": "assistant", "content": raw})

        if not assistant_message:
            return "Уточни, пожалуйста. (Пустой ответ модели)"
        return assistant_message


# ============= MAIN =============

def print_profile(state: dict):
    pc = state["pc_specs"]
    gp = state["game_preferences"]

    print("\n" + "=" * 50)
    print("ТВОЙ ПРОФИЛЬ")
    print("=" * 50)
    print("ПК:")
    print(f"  • Видеокарта: {pc['gpu']}")
    print(f"  • Процессор:  {pc['cpu']}")
    print(f"  • ОЗУ:        {pc['ram']} ГБ")
    print("\nИгры:")
    print(f"  • Жанр:       {gp['genre']}")
    print(f"  • Поджанр:    {gp['subgenre']}")
    print(f"  • Режим:      {gp['game_mode']}")
    print(f"  • Возраст:    {gp['age_rating']}")
    print("=" * 50 + "\n")


def dialog_bot():
    print("🎮 АССИСТЕНТ ДЛЯ ПОДБОРА ВИДЕОИГР 🎮")
    print("=" * 50)
    print("Напиши 'выход' чтобы закончить.\n")

    assistant = GameAssistant()

    first_msg = assistant.user_turn("НАЧАТЬ ДИАЛОГ. Задай первый вопрос.")
    print("Ассистент:", first_msg)

    while True:
        user_input = input("Ты: ").strip()
        if user_input.lower() in ["выход", "пока", "exit", "quit"]:
            return 0

        bot_text = assistant.user_turn(user_input)
        print("Ассистент:", bot_text)

        if assistant.is_done():
            print_profile(assistant.state)
            profile_json = assistant.build_profile_json()  # переменная со строкой JSON [web:91]

            return profile_json