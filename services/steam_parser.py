import requests


def get_game_info(game_title: str):
    """Получить информацию об игре: название, цена, скидка, отзывы, картинка"""

    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        # 1 Ищем игру по названию
        print(f"Ищу '{game_title}'...")

        r1 = requests.get(
            "https://store.steampowered.com/api/storesearch/",
            params={"term": game_title, "l": "english", "cc": "ru"},
            headers=headers
        )
        data = r1.json()

        if not data.get("items"):
            print(f"Игра не найдена\n")
            return None

        # Берем первый результат
        app_id = data["items"][0]["id"]
        name = data["items"][0]["name"]
        print(f"Найдена: {name}")

        # 2 Получаем цену
        r2 = requests.get(
            "https://store.steampowered.com/api/appdetails",
            params={"appids": app_id, "cc": "ru"},
            headers=headers
        )
        resp = r2.json()

        app_data = resp.get(str(app_id), {})
        if not app_data.get("success"):
            return None

        game_data = app_data.get("data", {})
        price_info = game_data.get("price_overview")

        # Формируем цену и скидку
        if price_info:
            price = price_info.get("final", 0) / 100
            original = price_info.get("initial", 0) / 100
            discount = price_info.get("discount_percent", 0)
            price_text = f"₽{price:.2f}"
            discount_text = f"{discount}% (было ₽{original:.2f})" if discount > 0 else "Нет скидки"
        elif game_data.get("is_free"):
            price_text = "Бесплатно"
            discount_text = "N/A"
        else:
            price_text = "Недоступна"
            discount_text = "N/A"

        # 3 Получаем отзывы
        print(f"Загружаю отзывы...\n")
        r3 = requests.get(
            f"https://store.steampowered.com/appreviews/{app_id}",
            params={
                "json": 1,
                "filter": "recent",
                "language": "russian",
                "purchase_type": "all",
                "num_per_page": 3
            },
            headers=headers
        )
        reviews_data = r3.json()

        reviews = []
        if reviews_data.get("reviews"):
            for review in reviews_data["reviews"][:3]:
                author = review.get("author", {}).get("steamid", "Unknown")
                rating = "✅ Рекомендует" if review.get("voted_up") else "❌ Не рекомендует"
                hours = round(review.get("author", {}).get("playtime_forever", 0) / 60, 1)
                text = review.get("review", "")

                reviews.append({
                    "автор": author[:15],
                    "рейтинг": rating,
                    "часов": hours,
                    "текст": text
                })

        # 4 Получаем картинку
        image_url = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/library_600x900_2x.jpg"

        r4 = requests.head(image_url)
        if r4.status_code == 200:
            image_link = image_url
        else:
            image_link = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg"

        # 5 Возвращаем результат
        return {
            "название": name,
            "цена": price_text,
            "скидка": discount_text,
            "отзывы": reviews,
            "картинка": image_link,
            "steam_url": f"https://store.steampowered.com/app/{app_id}"
        }

    except Exception as e:
        print(f"Ошибка: {e}\n")
        return None