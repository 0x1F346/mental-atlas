"""Hosted text embeddings over HTTP.

The plan leaves the embedding provider to the owner. This adapter speaks the
request shape shared by the common hosted embedding APIs (a JSON body with `model`
and `input`, a `data` list of `embedding` arrays back); the base URL, model and key
come from settings. The model name and dimension are stored with every vector.
"""

import httpx

from atlas.pipeline.stages import StageError


class HttpEmbedder:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        dimension: int,
        client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self.dimension = dimension
        self._client = client or httpx.Client(
            base_url=base_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=60
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            response = self._client.post("/embeddings", json={"model": self.model, "input": texts})
        except httpx.HTTPError as error:
            raise StageError("embedder_unavailable", retryable=True) from error
        if response.status_code in (401, 403):
            raise StageError("embedder_auth_failed")
        if response.status_code == 429 or response.status_code >= 500:
            raise StageError("embedder_unavailable", retryable=True)
        if response.status_code >= 400:
            raise StageError("embedder_rejected_request")
        rows = sorted(response.json()["data"], key=lambda row: row.get("index", 0))
        vectors = [[float(x) for x in row["embedding"]] for row in rows]
        if len(vectors) != len(texts):
            raise StageError("embedder_output_invalid", retryable=True)
        return vectors
