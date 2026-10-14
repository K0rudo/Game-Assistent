from services.dialog_bot import dialog_bot
from services.rag_engine import RagRecommender
from services.games_ui import  run_from_llm_answer
import json
import sys

profile_json = dialog_bot()
if profile_json == 0:
    print("До свидания!")
    sys.exit(0)

profile = json.loads(profile_json)
OWL_FILE = "services/GAMES.owl"
EMBED_MODEL_NAME = "sergeyzh/BERTA"
api_key = "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"

rag = RagRecommender(
    owl_file=OWL_FILE,
    embed_model_name=EMBED_MODEL_NAME,
    chunk_size=800,
    chunk_overlap=100,
    device="cpu",
    )

answer = rag.recommend(profile, api_key=api_key, rag_chunks_k=10, rag_top_games=3, debug_print=True)
run_from_llm_answer(answer)
