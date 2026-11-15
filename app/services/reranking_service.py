"""
Reranking Service

Provides transparent, explainable multi-factor relevance reranking
beyond dense vector cosine similarity.

Evaluates:
1. Dense semantic vector score (cosine similarity)
2. Lexical term and n-gram overlap between post and agent manifesto
3. Industry category alignment and commercial synergy
4. Agent trust score
"""

import re
from typing import Dict, List, Optional, Set, Tuple

from app.models.agent import Agent
from app.models.post import Post

STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "cannot", "could", "did", "do",
    "does", "doing", "don't", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is",
    "isn't", "it", "its", "itself", "just", "me", "more", "most", "my", "myself",
    "no", "nor", "not", "now", "of", "off", "on", "once", "only", "or", "other",
    "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should",
    "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they", "this", "those", "through",
    "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", "were",
    "what", "when", "where", "which", "while", "who", "whom", "why", "with",
    "you", "your", "yours", "yourself", "yourselves",
}

# Industry domain clusters mapping categories to relevant keywords
INDUSTRY_DOMAINS: Dict[str, Set[str]] = {
    "food delivery": {
        "food", "delivery", "restaurant", "restaurants", "dining", "meal", "meals",
        "grocery", "groceries", "discounts", "festivals", "eat", "cafe", "dishes",
        "snack", "snacks", "order", "ordering", "swiggy", "zomato",
    },
    "fintech": {
        "fintech", "payment", "payments", "upi", "wallet", "cashback", "merchant",
        "merchants", "transaction", "transactions", "checkout", "rewards", "transfer",
        "qr", "gateway", "phonepe", "paytm", "gpay",
    },
    "digital payments": {
        "payment", "payments", "upi", "cashback", "merchant", "merchants", "qr",
        "pay", "transfers", "digital", "wallet", "rewards", "google pay", "gpay",
    },
    "banking": {
        "bank", "banking", "credit", "card", "cards", "debit", "loan", "loans",
        "savings", "account", "finance", "financial", "services", "deposit", "interest",
        "hdfc", "sbi", "icici", "axis",
    },
    "automobile": {
        "automobile", "automobiles", "automotive", "vehicle", "vehicles", "motorcycle",
        "motorcycles", "bike", "bikes", "car", "cars", "scooter", "scooters", "launches",
        "auto", "drive", "ride", "bajaj", "tata", "maruti",
    },
}

# Cross-industry commercial partnerships / synergy matrix
INDUSTRY_SYNERGY: Dict[Tuple[str, str], float] = {
    ("food delivery", "fintech"): 0.80,
    ("food delivery", "digital payments"): 0.85,
    ("food delivery", "banking"): 0.70,
    ("fintech", "banking"): 0.90,
    ("fintech", "digital payments"): 0.95,
    ("digital payments", "banking"): 0.90,
    ("automobile", "banking"): 0.65,  # Auto finance / loans
    ("automobile", "food delivery"): 0.10,  # Negligible direct synergy
    ("automobile", "fintech"): 0.20,
}


class RerankingService:
    """Intelligent, multi-factor reranking engine."""

    def __init__(
        self,
        weight_vector: float = 0.35,
        weight_lexical: float = 0.30,
        weight_industry: float = 0.25,
        weight_trust: float = 0.10,
    ):
        self.w_vector = weight_vector
        self.w_lexical = weight_lexical
        self.w_industry = weight_industry
        self.w_trust = weight_trust

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        """Normalize text and extract meaningful content tokens without stopwords."""
        words = re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", text.lower())
        return {w for w in words if w not in STOPWORDS}

    def compute_lexical_overlap(self, post_tokens: Set[str], agent_tokens: Set[str]) -> float:
        """Calculate overlap ratio between post tokens and agent manifesto."""
        if not post_tokens or not agent_tokens:
            return 0.0
        intersection = post_tokens & agent_tokens
        overlap = len(intersection) / len(agent_tokens)
        return min(1.0, overlap)

    def compute_industry_alignment(self, post_tokens: Set[str], agent_category: str) -> float:
        """Calculate thematic alignment between post tokens and agent industry category."""
        agent_cat_norm = agent_category.strip().lower()
        cat_keywords = INDUSTRY_DOMAINS.get(agent_cat_norm, set())

        direct_matches = len(post_tokens & cat_keywords)
        if direct_matches > 0:
            return min(1.0, 0.5 + (direct_matches * 0.15))

        # Check cross-industry synergy
        best_synergy = 0.05
        for (cat_a, cat_b), synergy_score in INDUSTRY_SYNERGY.items():
            if agent_cat_norm == cat_a:
                other_keywords = INDUSTRY_DOMAINS.get(cat_b, set())
                if len(post_tokens & other_keywords) > 0:
                    best_synergy = max(best_synergy, synergy_score)
            elif agent_cat_norm == cat_b:
                other_keywords = INDUSTRY_DOMAINS.get(cat_a, set())
                if len(post_tokens & other_keywords) > 0:
                    best_synergy = max(best_synergy, synergy_score)

        return best_synergy

    def rerank_candidate(
        self,
        post: Post,
        agent: Agent,
        vector_score: float,
    ) -> Dict:
        """Compute transparent multi-factor rerank score for an agent candidate."""
        post_text = f"{post.title} {post.content}"
        post_tokens = self._tokenize(post_text)
        agent_tokens = self._tokenize(agent.interest_manifesto)

        lexical_score = self.compute_lexical_overlap(post_tokens, agent_tokens)
        industry_score = self.compute_industry_alignment(post_tokens, agent.industry_category)
        trust_score = float(agent.trust_score if agent.trust_score is not None else 1.0)

        # Composite weighted formula
        raw_rerank = (
            self.w_vector * vector_score +
            self.w_lexical * lexical_score +
            self.w_industry * industry_score +
            self.w_trust * trust_score
        )
        final_rerank = round(max(0.0, min(1.0, raw_rerank)), 4)

        explanation = (
            f"Vector={vector_score:.3f}, Lexical={lexical_score:.3f}, "
            f"Industry={industry_score:.3f} ({agent.industry_category}), Trust={trust_score:.2f}"
        )

        return {
            "rerank_score": final_rerank,
            "vector_score": round(vector_score, 4),
            "breakdown": {
                "vector_component": round(self.w_vector * vector_score, 4),
                "lexical_score": round(lexical_score, 4),
                "industry_score": round(industry_score, 4),
                "trust_score": round(trust_score, 4),
                "explanation": explanation,
            },
        }

    def rerank_candidates(
        self,
        post: Post,
        candidates: List[Tuple[Agent, float]],
        min_threshold: float = 0.50,
    ) -> List[Dict]:
        """Rerank all candidate agents, sort by rerank_score, and filter below threshold."""
        scored = []
        for agent, vec_score in candidates:
            score_data = self.rerank_candidate(post, agent, vec_score)
            if score_data["rerank_score"] >= min_threshold:
                scored.append({
                    "agent": agent,
                    "agent_id": agent.id,
                    "company_name": agent.company_name,
                    "industry_category": agent.industry_category,
                    "webhook_url": agent.webhook_url,
                    "vector_score": score_data["vector_score"],
                    "rerank_score": score_data["rerank_score"],
                    "breakdown": score_data["breakdown"],
                })

        # Sort descending by rerank_score
        scored.sort(key=lambda x: x["rerank_score"], reverse=True)
        return scored


reranking_service = RerankingService()
