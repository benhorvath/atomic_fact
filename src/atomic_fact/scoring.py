"""Post-extraction scoring — IDF-based specificity scoring for atomic facts.

Each extracted fact is treated as a "document" for IDF purposes. Terms that
appear in many facts get low IDF (generic), terms that appear in few facts
get high IDF (specific). The mean IDF of a fact's tokens measures how
specific/rare that fact is relative to the rest of the extraction.

Entropy measures the information content of a single fact's token
distribution (after removing stop words). Higher entropy means more
diverse vocabulary; lower entropy means repetitive or simple phrasing.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from atomic_fact.models import AtomicFact

# Standard English stop words (tidytext / snowball set)
STOP_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "about",
        "above",
        "after",
        "again",
        "against",
        "all",
        "am",
        "an",
        "and",
        "any",
        "are",
        "aren't",
        "as",
        "at",
        "be",
        "because",
        "been",
        "before",
        "being",
        "below",
        "between",
        "both",
        "but",
        "by",
        "can",
        "can't",
        "cannot",
        "could",
        "couldn't",
        "did",
        "didn't",
        "do",
        "does",
        "doesn't",
        "doing",
        "don't",
        "down",
        "during",
        "each",
        "few",
        "for",
        "from",
        "further",
        "get",
        "got",
        "had",
        "hadn't",
        "has",
        "hasn't",
        "have",
        "haven't",
        "having",
        "he",
        "he'd",
        "he'll",
        "he's",
        "her",
        "here",
        "here's",
        "hers",
        "herself",
        "him",
        "himself",
        "his",
        "how",
        "how's",
        "i",
        "i'd",
        "i'll",
        "i'm",
        "i've",
        "if",
        "in",
        "into",
        "is",
        "isn't",
        "it",
        "it's",
        "its",
        "itself",
        "let's",
        "me",
        "more",
        "most",
        "mustn't",
        "my",
        "myself",
        "no",
        "nor",
        "not",
        "of",
        "off",
        "on",
        "once",
        "only",
        "or",
        "other",
        "ought",
        "our",
        "ours",
        "ourselves",
        "out",
        "over",
        "own",
        "same",
        "shan't",
        "she",
        "she'd",
        "she'll",
        "she's",
        "should",
        "shouldn't",
        "so",
        "some",
        "such",
        "than",
        "that",
        "that's",
        "the",
        "their",
        "theirs",
        "them",
        "themselves",
        "then",
        "there",
        "there's",
        "these",
        "they",
        "they'd",
        "they'll",
        "they're",
        "they've",
        "this",
        "those",
        "through",
        "to",
        "too",
        "under",
        "until",
        "up",
        "very",
        "was",
        "wasn't",
        "we",
        "we'd",
        "we'll",
        "we're",
        "we've",
        "were",
        "weren't",
        "what",
        "what's",
        "when",
        "when's",
        "where",
        "where's",
        "which",
        "while",
        "who",
        "who's",
        "whom",
        "why",
        "why's",
        "will",
        "with",
        "won't",
        "would",
        "wouldn't",
        "you",
        "you'd",
        "you'll",
        "you're",
        "you've",
        "your",
        "yours",
        "yourself",
        "yourselves",
    }
)


def _tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split on whitespace."""
    return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text.lower())


def compute_idf_scores(facts: list[AtomicFact]) -> list[AtomicFact]:
    """Compute mean IDF for each fact and set fact.idf_score.

    Each fact is treated as a document. IDF for a term t is:
        log(N / df(t))
    where N = number of facts, df(t) = number of facts containing t.

    Args:
        facts: List of extracted atomic facts.

    Returns:
        The same list with idf_score populated on each fact.
    """
    if not facts:
        return facts

    n = len(facts)
    fact_tokens = [[t for t in _tokenize(f.fact) if t not in STOP_WORDS] for f in facts]

    # Document frequency: how many facts contain each term
    df: Counter[str] = Counter()
    for tokens in fact_tokens:
        for term in set(tokens):
            df[term] += 1

    # Compute mean IDF per fact
    for i, tokens in enumerate(fact_tokens):
        if not tokens:
            facts[i].idf_score = 0.0
            continue
        idf_sum = sum(math.log(n / df[t]) for t in tokens)
        facts[i].idf_score = round(idf_sum / len(tokens), 4)

    return facts


def compute_entropy(facts: list[AtomicFact]) -> list[AtomicFact]:
    """Compute Shannon entropy for each fact's token distribution.

    Replicates the R logic:
        tokenize → remove stop words → count terms →
        p = n / sum(n) → entropy = -sum(p * log2(p))

    Args:
        facts: List of extracted atomic facts.

    Returns:
        The same list with entropy populated on each fact.
    """
    for fact in facts:
        tokens = _tokenize(fact.fact)
        tokens = [t for t in tokens if t not in STOP_WORDS]

        if not tokens:
            fact.entropy = 0.0
            continue

        counts = Counter(tokens)
        total = sum(counts.values())
        entropy = -sum((n / total) * math.log2(n / total) for n in counts.values())
        fact.entropy = round(entropy, 4)

    return facts
