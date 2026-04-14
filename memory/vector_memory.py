"""Simple FAISS-based memory for past travel decisions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List

import faiss
import numpy as np


@dataclass
class MemoryRecord:
    query_text: str
    decision: str
    reason: str
    suggestion: str
    preference_note: str = ""


class TravelMemoryStore:
    """Stores and retrieves travel decisions using FAISS vectors."""

    def __init__(self, data_dir: str = "memory_data", dim: int = 128) -> None:
        self.dim = dim
        self.data_path = Path(data_dir)
        self.data_path.mkdir(parents=True, exist_ok=True)

        self.index_path = self.data_path / "travel.index"
        self.meta_path = self.data_path / "travel_meta.json"
        self.index = faiss.IndexFlatL2(self.dim)
        self.metadata: List[Dict] = []
        self._load()

    def _embed(self, text: str) -> np.ndarray:
        """Create deterministic vector embedding from text tokens."""
        vector = np.zeros(self.dim, dtype=np.float32)
        tokens = [tok for tok in text.lower().split() if tok]
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:2], "big") % self.dim
            sign = 1.0 if digest[2] % 2 == 0 else -1.0
            vector[idx] += sign

        norm = np.linalg.norm(vector)
        if norm > 0:
            vector /= norm
        return vector

    def _load(self) -> None:
        if self.index_path.exists():
            self.index = faiss.read_index(str(self.index_path))
        if self.meta_path.exists():
            with self.meta_path.open("r", encoding="utf-8") as file:
                self.metadata = json.load(file)

    def _persist(self) -> None:
        faiss.write_index(self.index, str(self.index_path))
        with self.meta_path.open("w", encoding="utf-8") as file:
            json.dump(self.metadata, file, indent=2)

    def add_memory(self, record: MemoryRecord) -> None:
        vector = self._embed(
            f"{record.query_text} {record.decision} {record.reason} {record.preference_note}"
        )
        self.index.add(np.array([vector], dtype=np.float32))
        self.metadata.append(asdict(record))
        self._persist()

    def retrieve_similar(self, query_text: str, top_k: int = 3) -> List[Dict]:
        if self.index.ntotal == 0:
            return []

        vector = self._embed(query_text)
        _, indices = self.index.search(np.array([vector], dtype=np.float32), top_k)

        matches: List[Dict] = []
        for idx in indices[0]:
            if idx < 0 or idx >= len(self.metadata):
                continue
            matches.append(self.metadata[idx])
        return matches
