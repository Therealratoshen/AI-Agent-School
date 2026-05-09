from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from typing import Optional
import uuid


class QdrantConfig:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        collection_name: str = "ai_agent_school",
    ):
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.client: Optional[QdrantClient] = None

    def connect(self) -> QdrantClient:
        self.client = QdrantClient(host=self.host, port=self.port)
        return self.client

    def create_collection(self, vector_size: int = 1536):
        if not self.client:
            self.connect()

        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self.collection_name not in collection_names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                ),
            )

    def insert_memory(
        self,
        vector: list[float],
        payload: dict,
        mem_id: Optional[str] = None,
    ) -> str:
        if not self.client:
            self.connect()

        point_id = mem_id or str(uuid.uuid4())

        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            ],
        )

        return point_id

    def search_memories(
        self,
        query_vector: list[float],
        limit: int = 5,
        filter_conditions: Optional[dict] = None,
    ) -> list[dict]:
        if not self.client:
            self.connect()

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=filter_conditions,
        )

        return [
            {
                "id": hit.id,
                "score": hit.score,
                "payload": hit.payload,
            }
            for hit in results
        ]

    def delete_memory(self, mem_id: str) -> bool:
        if not self.client:
            self.connect()

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=[mem_id],
        )

        return True


qdrant_config = QdrantConfig()
