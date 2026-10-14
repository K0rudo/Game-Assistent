# rag_engine.py
import os
import json
import requests
from typing import List, Dict, Tuple, Optional

from rdflib import Graph, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS
from rdflib import Namespace

from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings
from sentence_transformers import SentenceTransformer


PPLX_URL = "https://api.perplexity.ai/chat/completions"  # Perplexity Chat Completions endpoint [web:415]
PPLX_MODEL = "sonar"


def shorten(node, g: Optional[Graph] = None) -> str:
    if isinstance(node, Literal):
        return str(node)
    if isinstance(node, URIRef):
        s = str(node)
        if g is not None:
            try:
                return g.namespace_manager.normalizeUri(node)
            except Exception:
                pass
        if "#" in s:
            return s.split("#")[-1]
        if "/" in s:
            return s.rstrip("/").split("/")[-1]
    return str(node)


def make_describe_node(g: Graph):
    def describe_node(node, depth=0) -> str:
        if isinstance(node, BNode):
            triples = list(g.predicate_objects(node))
            if not triples:
                return "_:BlankNode"
            parts = []
            for p, o in triples:
                pname = shorten(p, g)
                oname = describe_node(o, depth + 1)
                parts.append(f"{pname} {oname}")
            return "Restriction(" + ", ".join(parts) + ")"
        return shorten(node, g)

    return describe_node


def owl_to_documents(owl_path: str) -> List[Document]:
    g = Graph()
    g.parse(owl_path, format="xml")

    EX = Namespace("http://www.semanticweb.org/vasya/ontologies/2026/0/untitled-ontology-8#")
    GAME_CLASS = EX.Game

    describe_node = make_describe_node(g)
    docs: List[Document] = []

    game_subjects = set(g.subjects(RDF.type, GAME_CLASS))

    for s in game_subjects:
        if isinstance(s, BNode):
            continue

        subject_name = shorten(s, g)

        labels = [str(o) for o in g.objects(s, RDFS.label)]
        comments = [str(o) for o in g.objects(s, RDFS.comment)]
        types = [shorten(o, g) for o in g.objects(s, RDF.type)]

        lines = [f"Subject: {subject_name}"]
        if labels:
            lines.append("Labels: " + ", ".join(labels))
        if comments:
            lines.append("Comments: " + ", ".join(comments))
        if types:
            lines.append("Types: " + ", ".join(types))

        for p, o in g.predicate_objects(s):
            if p in (RDFS.label, RDFS.comment, RDF.type):
                continue
            lines.append(f"{shorten(p, g)} -> {describe_node(o)}")

        docs.append(Document(
            page_content="\n".join(lines),
            metadata={"subject": subject_name, "types": types, "doc_type": "game"}
        ))

    return docs


def docs_to_chunks(docs: List[Document], chunk_size: int = 800, chunk_overlap: int = 100) -> Tuple[List[str], List[Dict]]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    texts: List[str] = []
    metadatas: List[Dict] = []
    for doc in docs:
        pieces = splitter.split_text(doc.page_content)
        for i, piece in enumerate(pieces):
            texts.append(piece)
            md = dict(doc.metadata)
            md["chunk_index"] = i
            metadatas.append(md)

    return texts, metadatas


class STEmbeddings(Embeddings):
    def __init__(self, model_name: str, device: str = "cpu"):
        self.model = SentenceTransformer(model_name, device=device)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(texts, convert_to_numpy=True).tolist()

    def embed_query(self, text: str) -> List[float]:
        return self.model.encode(text, convert_to_numpy=True).tolist()


def build_query_from_game_preferences(profile: dict) -> str:
    prefs = profile.get("game_preferences", {})
    parts = [
        prefs.get("genre", ""),
        prefs.get("subgenre", ""),
        prefs.get("game_mode", ""),
        prefs.get("age_rating", ""),
    ]
    return " ".join([p for p in parts if p]).strip()


def pplx_chat(messages: List[dict], api_key: str, model: str = PPLX_MODEL,
             temperature: float = 0.2, max_tokens: int = 700, response_format: Optional[dict] = None) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if response_format is not None:
        payload["response_format"] = response_format
    headers = {
        "Authorization": f"Bearer {api_key}",  # Bearer auth header [web:415]
        "Content-Type": "application/json",
    }
    r = requests.post(PPLX_URL, headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]


def build_llm_context(profile: dict, candidate_full_docs: List[Document], max_chars: int = 7000) -> str:
    blocks = []
    blocks.append("USER_PC_SPECS:\n" + json.dumps(profile.get("pc_specs", {}), ensure_ascii=False))
    blocks.append("USER_GAME_PREFERENCES:\n" + json.dumps(profile.get("game_preferences", {}), ensure_ascii=False))
    blocks.append("CANDIDATE_GAMES:")
    for d in candidate_full_docs:
        blocks.append(d.page_content)
    ctx = "\n\n---\n\n".join(blocks)
    return ctx[:max_chars]


def pick_best_games_with_requirements(profile: dict, candidate_full_docs: List[Document], api_key: str) -> str:
    context = build_llm_context(profile, candidate_full_docs)

    system_prompt = (
        "Ты консультант по играм. Используй только данные из CONTEXT (ничего не придумывай). "
        "Отсортируй кандидатов и приведи их системные требования."
        "Английский допустим только для названий игр и моделей железа/видеокарт/процессоров."
    )

    user_prompt = f"""CONTEXT:
{context}

TASK:
1) В CANDIDATE_GAMES ровно {len(candidate_full_docs)} игры. Верни их ВСЕ, просто отсортируй по лучшей пригодности для ПК пользователя и предпочтений.
2) Не добавляй новые игры и не удаляй игры из списка кандидатов.
3) Для КАЖДОЙ игры выведи:
   - Название (title, если есть в тексте; иначе Subject)
   - Место в рейтинге (1..{len(candidate_full_docs)})
   - Почему это место (2-3 пункта)
   - Системные требования (строки), строго из контекста: minCpu, minGpu, minRamGb/minRam (или похожие)

Формат: кратко, списком.
Запреты:
- Не используй ссылки/URL.
- Не добавляй раздел References/Источники.
"""
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "game_ranking_why",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "games": {
                        "type": "array",
                        "minItems": len(candidate_full_docs),
                        "maxItems": len(candidate_full_docs),
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "rank": {"type": "integer", "minimum": 1},
                                "title": {"type": "string"},
                                "why": {
                                    "type": "array",
                                    "minItems": 2,
                                    "maxItems": 3,
                                    "items": {"type": "string"}
                                }
                            },
                            "required": ["rank", "title", "why"]
                        }
                    }
                },
                "required": ["games"]
            }
        }
    }
    return pplx_chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        api_key=api_key,
        model=PPLX_MODEL,
        temperature=0.2,
        max_tokens=700,
        response_format=response_format
    )


class RagRecommender:
    def __init__(self, owl_file: str, embed_model_name: str,
                 chunk_size: int = 800, chunk_overlap: int = 100, device: str = "cpu"):
        self.owl_file = owl_file
        self.embed_model_name = embed_model_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self.docs_full = owl_to_documents(owl_file)
        self.full_by_subject = {d.metadata["subject"]: d for d in self.docs_full}

        texts, metadatas = docs_to_chunks(self.docs_full, chunk_size, chunk_overlap)
        self.vector_store = FAISS.from_texts(
            texts=texts,
            embedding=STEmbeddings(embed_model_name, device=device),
            metadatas=metadatas
        )

    def recommend(self, profile: dict, api_key: str,
                  rag_chunks_k: int = 10, rag_top_games: int = 3,
                  debug_print: bool = False) -> str:
        query = build_query_from_game_preferences(profile)

        results = self.vector_store.similarity_search_with_relevance_scores(query, k=rag_chunks_k)

        if debug_print:
            print("\n=== TOP CHUNKS WITH SCORES ===")
            for i, (doc_chunk, score) in enumerate(results, start=1):
                subj = doc_chunk.metadata.get("subject")
                print(f"#{i} score={score:.4f} subject={subj} chunk_index={doc_chunk.metadata.get('chunk_index')}")
                print(doc_chunk.page_content[:220].replace("\n", " "))

        best_by_subject = {}
        for doc_chunk, score in results:
            subj = doc_chunk.metadata.get("subject")
            if not subj:
                continue
            if subj not in best_by_subject or score > best_by_subject[subj]:
                best_by_subject[subj] = score

        ranked = sorted(best_by_subject.items(), key=lambda x: x[1], reverse=True)
        topN = ranked[:rag_top_games]

        candidate_full_docs = [self.full_by_subject[subj] for subj, _ in topN]

        if debug_print:
            print("\n=== RAG TOP GAMES ===")
            for i, (subj, score) in enumerate(topN, start=1):
                print(f"#{i} best_score={score:.4f} subject={subj}")

        return pick_best_games_with_requirements(profile, candidate_full_docs, api_key=api_key)
