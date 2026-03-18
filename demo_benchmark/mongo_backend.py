from __future__ import annotations

import re
from typing import Any


class MongoUnavailableError(RuntimeError):
    """Raised when pymongo is not installed or MongoDB is unreachable."""


class MongoRepository:
    def __init__(self, uri: str, database: str, collection: str) -> None:
        self.uri = uri
        self.database = database
        self.collection = collection
        self._client = None
        self._collection = None

    def _connect(self):
        if self._collection is not None:
            return self._collection
        try:
            from pymongo import MongoClient
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on local env
            raise MongoUnavailableError(
                "pymongo is not installed. Run `pip install -e .` before using MongoDB-backed flows."
            ) from exc

        self._client = MongoClient(self.uri, serverSelectionTimeoutMS=1000)
        self._client.admin.command("ping")
        self._collection = self._client[self.database][self.collection]
        return self._collection

    def get_document(self, key: str) -> dict[str, Any] | None:
        collection = self._connect()
        document = collection.find_one({"key": key}, {"_id": 0})
        return document

    def upsert_document(self, key: str, payload: dict[str, Any]) -> None:
        collection = self._connect()
        collection.update_one({"key": key}, {"$set": payload}, upsert=True)

    def search_listings(
        self,
        query: str = "",
        location: str = "",
        category: str = "",
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        collection = self._connect()
        filters: dict[str, Any] = {"doc_type": "listing"}
        if query:
            pattern = re.escape(query)
            filters["$or"] = [
                {"title": {"$regex": pattern, "$options": "i"}},
                {"description": {"$regex": pattern, "$options": "i"}},
                {"keywords": {"$elemMatch": {"$regex": pattern, "$options": "i"}}},
            ]
        if location and location != "all":
            filters["location"] = location
        if category and category != "all":
            filters["category"] = category
        cursor = collection.find(filters, {"_id": 0}).sort("score", -1).limit(limit)
        return list(cursor)

    def get_listing_by_id(self, listing_id: int) -> dict[str, Any] | None:
        collection = self._connect()
        return collection.find_one({"doc_type": "listing", "listing_id": listing_id}, {"_id": 0})
