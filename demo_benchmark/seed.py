from __future__ import annotations

import argparse
from random import Random

from .config import Settings
from .mongo_backend import MongoRepository


LOCATIONS = [
    "성남시 분당구",
    "서울 강남구",
    "서울 마포구",
    "수원시 영통구",
    "용인시 수지구",
]
TITLES = [
    ("아이폰 14 프로 256GB", "digital"),
    ("맥북 에어 M2 13인치", "digital"),
    ("닌텐도 스위치 OLED", "game"),
    ("에어팟 프로 2세대", "digital"),
    ("원목 책상 1200", "furniture"),
    ("캠핑 의자 세트", "outdoor"),
    ("플레이스테이션5 디스크 에디션", "game"),
    ("샤오미 공기청정기", "home"),
    ("로지텍 MX Keys 키보드", "digital"),
    ("폴로 니트 가디건", "fashion"),
]


def build_payload(index: int, randomizer: Random) -> dict:
    title, category = TITLES[(index - 1) % len(TITLES)]
    location = LOCATIONS[(index - 1) % len(LOCATIONS)]
    listing_id = 1000 + index
    price = 15000 + (index * 17000)
    likes = randomizer.randint(3, 190)
    views = randomizer.randint(80, 2400)
    score = likes * 3 + views
    seller_id = 500 + ((index - 1) % 8)
    return {
        "key": f"listing:{listing_id}",
        "doc_type": "listing",
        "listing_id": listing_id,
        "title": title,
        "category": category,
        "location": location,
        "price": price,
        "likes": likes,
        "views": views,
        "score": score,
        "status": "예약중" if index % 5 == 0 else "판매중",
        "created_at": f"2026-03-{(index % 18) + 1:02d}T1{index % 10}:30:00+09:00",
        "description": f"{title} 중고 매물입니다. 직거래는 {location} 가능하고, 상태는 A급입니다.",
        "keywords": [title.split()[0], category, location.split()[0]],
        "seller": {
            "seller_id": seller_id,
            "nickname": f"동네판매자{seller_id}",
            "area": location,
            "rating": round(4.2 + (index % 5) * 0.12, 1),
            "trade_count": 12 + index,
            "response_rate": f"{88 + (index % 10)}%",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo documents into MongoDB.")
    parser.add_argument("--count", type=int, default=20)
    args = parser.parse_args()

    settings = Settings()
    repo = MongoRepository(settings.mongo_uri, settings.mongo_database, settings.mongo_collection)
    randomizer = Random(7)
    for index in range(1, args.count + 1):
        payload = build_payload(index, randomizer)
        repo.upsert_document(payload["key"], payload)
    print(f"Seeded {args.count} documents into {settings.mongo_database}.{settings.mongo_collection}")


if __name__ == "__main__":
    main()
