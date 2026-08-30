"""
@changelog
| Version | Description                                          | Reference                                     |
| v1.0.0  | Initial implementation: LightRAG proxy + mock fallback | DEV: local playtest without LightRAG service |
/@changelog

@author chuckyang123
"""
import logging
import os

import requests
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

# LightRAG service URL, e.g. http://localhost:9621. When unset (local dev without
# docker), the endpoint falls back to a deterministic mock so the full
# "generate feedback -> version history" flow can still be demonstrated.
LIGHTRAG_URL = os.getenv("LIGHTRAG_URL")
LIGHTRAG_API_KEY = os.getenv("LIGHTRAG_API_KEY", "your-secure-api-key-here")


def _mock_playtest_feedback(query: str) -> str:
    """Deterministic mock for local demo. Deliberately carries NO numeric
    scores so students never see a score leaking through the mock
    (PRD 20260824-playtest评分展示控制); real LightRAG output is stripped
    student-side by stripScoresFromMarkdown instead."""
    preview = " ".join(query.split())[:200]
    return (
        "**Professor Feedback:** "
        f"(Local mock mode \u2013 LightRAG service not reachable) Simulated "
        f"feedback for: \"{preview}\"\n\n"
        "**Final Summary:** Your reflection was logged; rerun with the "
        "LightRAG service (docker compose) for knowledge-graph feedback."
    )


class PlaytestFeedbackView(APIView):
    """Proxies playtest feedback requests to the LightRAG /query endpoint.

    In production nginx routes /api/playtest/ straight to the lightrag
    container, so this view is only exercised in local dev where the Django
    server is hit directly at http://localhost:8001/api/playtest/.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        query = request.data.get("query", "")
        mode = request.data.get("mode", "hybrid")

        if LIGHTRAG_URL:
            try:
                resp = requests.post(
                    f"{LIGHTRAG_URL}/query",
                    json={"query": query, "mode": mode},
                    headers={"X-API-Key": LIGHTRAG_API_KEY},
                    timeout=15,
                )
                resp.raise_for_status()
                return Response({"response": resp.json().get("response", "")})
            except requests.RequestException as exc:
                logger.warning(
                    "LightRAG unavailable (%s); falling back to mock feedback.", exc
                )

        return Response({"response": _mock_playtest_feedback(query)})
