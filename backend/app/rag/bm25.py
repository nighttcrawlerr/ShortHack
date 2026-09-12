"""BM25 — отраслевой стандарт лексического поиска, в чистом Python.

Заменяет самодельную меру совпадения слов. Учитывает редкость слова
и длину документа: совпадение по слову «ERR_TUNNEL_FAILED» весит намного
больше, чем совпадение по слову «работает».
"""
import math
from collections import Counter

K1 = 1.5
B = 0.75


class BM25:
    def __init__(self, documents: list[list[str]]) -> None:
        self.documents = documents
        self.doc_count = len(documents)
        self.doc_lengths = [len(doc) for doc in documents]
        self.avg_length = (
            sum(self.doc_lengths) / self.doc_count if self.doc_count else 0.0
        )
        self.term_frequencies = [Counter(doc) for doc in documents]

        document_frequency: Counter[str] = Counter()
        for doc in documents:
            document_frequency.update(set(doc))

        self.idf = {
            term: math.log(1 + (self.doc_count - freq + 0.5) / (freq + 0.5))
            for term, freq in document_frequency.items()
        }

    def score(self, query_terms: list[str], index: int) -> float:
        if not self.avg_length:
            return 0.0
        frequencies = self.term_frequencies[index]
        length = self.doc_lengths[index]
        total = 0.0
        for term in query_terms:
            frequency = frequencies.get(term)
            if not frequency:
                continue
            idf = self.idf.get(term, 0.0)
            numerator = frequency * (K1 + 1)
            denominator = frequency + K1 * (1 - B + B * length / self.avg_length)
            total += idf * numerator / denominator
        return total

    def rank(self, query_terms: list[str]) -> list[tuple[int, float]]:
        scored = [
            (index, self.score(query_terms, index)) for index in range(self.doc_count)
        ]
        scored = [pair for pair in scored if pair[1] > 0]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored
