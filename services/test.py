from games_ui import run_from_llm_answer






answer = """
## 1. Dark Souls 3

**Место в рейтинге:** 1

**Почему:**
- Полностью соответствует вашим предпочтениям: RPG, Souls-like, single-player режим
- Ваш ПК значительно превосходит требования (RTX 3060 и Ryzen 5 3600 намного мощнее минимальных требований)

**Системные требования:**
- CPU: Intel Core i3-2100 / AMD® FX-6300
- GPU: NVIDIA® GeForce GTX 750 Ti / ATI Radeon HD 7950
- RAM: 4 GB

---

## 2. Lies of P

**Место в рейтинге:** 2

**Почему:**
- Соответствует жанру (RPG, Souls-like) и режиму (single-player)
- Возрастной рейтинг 16+ ниже ваших предпочтений (18+)
- Требования выше, чем у Dark Souls 3, но ваш ПК их легко потянет

**Системные требования:**
- CPU: AMD Ryzen 3 1200 / Intel Core i3-6300
- GPU: AMD Radeon RX 560 4GB / NVIDIA GeForce GTX 960 4GB
- RAM: 8 GB

---

## 3. Paladins

**Место в рейтинге:** 3

**Почему:**
- Не соответствует предпочитаемому жанру (Adventure/Horror вместо RPG/Souls-like)
- Не является Souls-like игрой
- Хотя возрастной рейтинг 18+ совпадает с вашим предпочтением

**Системные требования:**
- CPU: Intel i7-7700K / AMD Ryzen 5 2600
- GPU: NVIDIA GTX 1060 / AMD RX 480
- RAM: 8 GB
"""

run_from_llm_answer(answer)