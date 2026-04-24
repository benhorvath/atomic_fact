"""Tests for atomic_fact.scoring — IDF-based specificity scoring."""

from atomic_fact.models import AtomicFact, Confidence
from atomic_fact.scoring import compute_idf_scores, compute_entropy, _tokenize


def _fact(text: str) -> AtomicFact:
    return AtomicFact(fact=text, quote=text, confidence=Confidence.HIGH)


class TestTokenize:
    def test_basic(self):
        assert _tokenize("Hello World") == ["hello", "world"]

    def test_strips_punctuation(self):
        assert _tokenize("Hello, world!") == ["hello", "world"]

    def test_keeps_numbers(self):
        assert _tokenize("In 1968, Reid met") == ["in", "1968", "reid", "met"]

    def test_keeps_contractions(self):
        assert _tokenize("it's Reid's") == ["it's", "reid's"]


class TestComputeIdfScores:
    def test_empty_list(self):
        assert compute_idf_scores([]) == []

    def test_single_fact(self):
        facts = [_fact("Hello world")]
        compute_idf_scores(facts)
        # log(1/1) = 0 for all terms
        assert facts[0].idf_score == 0.0

    def test_unique_terms_score_higher(self):
        facts = [
            _fact("the cat sat on the mat"),
            _fact("the dog sat on the rug"),
            _fact("Patrushev met Kissinger in Moscow"),
        ]
        compute_idf_scores(facts)
        # "cat", "mat" appear only in fact 0; "dog", "rug" only in fact 1
        # "Patrushev", "Kissinger", "Moscow" only in fact 2
        # "sat" appears in facts 0 and 1 → lower IDF
        # All three facts have mostly unique content words, but fact 2
        # has no shared terms at all → highest IDF
        assert facts[2].idf_score > facts[0].idf_score
        assert facts[2].idf_score > facts[1].idf_score

    def test_all_identical_facts_score_zero(self):
        facts = [_fact("same words here")] * 3
        compute_idf_scores(facts)
        for f in facts:
            assert f.idf_score == 0.0

    def test_only_stop_words_gives_zero_idf(self):
        facts = [_fact("the and or but"), _fact("hello world")]
        compute_idf_scores(facts)
        assert facts[0].idf_score == 0.0

    def test_scores_are_populated(self):
        facts = [_fact("alpha beta"), _fact("gamma delta")]
        compute_idf_scores(facts)
        for f in facts:
            assert f.idf_score is not None
            assert f.idf_score > 0


class TestComputeEntropy:
    def test_empty_list(self):
        assert compute_entropy([]) == []

    def test_single_unique_tokens(self):
        # "Reid met Kissinger" → 3 unique tokens, each p=1/3
        # entropy = -3 * (1/3 * log2(1/3)) = log2(3) ≈ 1.585
        facts = [_fact("Reid met Kissinger")]
        compute_entropy(facts)
        assert facts[0].entropy is not None
        assert abs(facts[0].entropy - 1.585) < 0.01

    def test_repeated_token_lowers_entropy(self):
        # All same non-stop word → entropy = 0
        facts = [_fact("Reid Reid Reid")]
        compute_entropy(facts)
        assert facts[0].entropy == 0.0

    def test_stop_words_excluded(self):
        # "the cat and the dog" → stop words removed → "cat", "dog"
        # 2 unique tokens, each p=0.5 → entropy = 1.0
        facts = [_fact("the cat and the dog")]
        compute_entropy(facts)
        assert facts[0].entropy is not None
        assert abs(facts[0].entropy - 1.0) < 0.01

    def test_only_stop_words_gives_zero(self):
        facts = [_fact("the and or but")]
        compute_entropy(facts)
        assert facts[0].entropy == 0.0

    def test_more_diverse_fact_has_higher_entropy(self):
        facts = [
            _fact("Reid Reid Reid Reid"),
            _fact("Reid met Kissinger in Moscow"),
        ]
        compute_entropy(facts)
        assert facts[1].entropy > facts[0].entropy
