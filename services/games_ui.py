import json
from typing import Dict, List
from .steam_parser import get_game_info


def llm_json_to_dict(answer_json_text: str) -> Dict[str, str]:

    data = json.loads(answer_json_text)  # JSON string -> dict [web:512]
    games = data.get("games", []) or []

    out: Dict[str, str] = {}
    for g in games:
        title = g.get("title", "Unknown")
        rank = g.get("rank", "")
        why = g.get("why", []) or []

        # соберём красивый блок (похоже на то, что было в markdown)
        lines = [f"## {rank}. {title}", "", "**Почему:**"]
        for w in why:
            lines.append(f"- {w}")

        out[title] = "\n".join(lines)

    return out


def process_games(games_list: List[str]) -> List[dict]:
    results = []
    for game in games_list:
        result = get_game_info(game)
        if result:
            results.append(result)
    return results


def show_game_card(game: dict, idx: int, total: int) -> None:
    title = game.get("название") or game.get("llm_title") or "Unknown"
    price = game.get("цена", "—")
    discount = game.get("скидка", "—")
    url = game.get("steam_url", "—")

    print("\n" + "=" * 70)
    print(f"[{idx+1}/{total}] {title}")
    print(f"Цена: {price} | Скидка: {discount}")
    print(f"Steam: {url}")

    llm_block = game.get("llm_block")
    if llm_block:
        print("\n--- LLM описание ---")
        print(llm_block.strip())
    print("=" * 70)


def show_reviews(game: dict, max_reviews: int = 3) -> None:
    reviews = game.get("отзывы", []) or []
    if not reviews:
        print("\nОтзывов нет.")
        return

    print("\nОтзывы:")
    for i, r in enumerate(reviews[:max_reviews], start=1):
        author = r.get("автор", "?")
        rating = r.get("рейтинг", "?")
        hours = r.get("часов", "?")
        text = (r.get("текст", "") or "").strip()
        if len(text) > 300:
            text = text[:300] + "..."
        print(f"\n{i}) {rating} | {hours} ч. | {author}")
        print(text)


def run_games_dialog(results_game_info: List[dict]) -> None:
    if not results_game_info:
        print("Список игр пуст.")
        return

    i = 0
    total = len(results_game_info)

    while True:
        game = results_game_info[i]
        show_game_card(game, i, total)

        print("\nВыбор:")
        print("1 — Показать отзывы")
        print("2 — Следующая игра")
        print("3 — Предыдущая игра")
        print("0 — Выход")

        choice = input("Введите команду: ").strip()

        if choice == "1":
            show_reviews(game, max_reviews=3)
            input("\nНажмите Enter, чтобы вернуться к меню...")
        elif choice == "2":
            if i < total - 1:
                i += 1
            else:
                print("Это последняя игра.")
        elif choice == "3":
            if i > 0:
                i -= 1
            else:
                print("Это первая игра.")
        elif choice == "0":
            print("Выход.")
            break
        else:
            print("Неизвестная команда, попробуйте снова.")


def run_from_llm_answer(answer_json_text: str) -> None:
    # 1) JSON -> dict(title -> llm_block)
    games_dict = llm_json_to_dict(answer_json_text)

    # 2) titles в том порядке, в каком LLM их отсортировала (rank 1..N)
    titles = list(games_dict.keys())

    # 3) Steam-данные по этим названиям
    steam_results = process_games(titles)

    # 4) склеиваем
    results_game_info = []
    for title, steam in zip(titles, steam_results):
        steam = dict(steam)
        steam["llm_title"] = title
        steam["llm_block"] = games_dict[title]
        results_game_info.append(steam)

    run_games_dialog(results_game_info)