from __future__ import annotations

import argparse
import json
from random import Random

from .config import Settings
from .mini_redis import MiniRedisTCPClient, MiniRedisStubClient
from .mongo_backend import MongoRepository


LOCATIONS = [
    "성남시 분당구",
    "서울 강남구",
    "서울 마포구",
    "서울 송파구",
    "서울 서초구",
    "서울 용산구",
    "서울 영등포구",
    "서울 노원구",
    "수원시 영통구",
    "수원시 팔달구",
    "용인시 수지구",
    "용인시 기흥구",
    "고양시 일산동구",
    "고양시 덕양구",
    "인천 남동구",
    "인천 연수구",
    "부산 해운대구",
    "부산 동래구",
    "대구 수성구",
    "대전 유성구",
]
TITLES = [
    ("아이폰 14 프로 256GB", "digital"),
    ("아이폰 13 미니 128GB", "digital"),
    ("아이폰 15 플러스 512GB", "digital"),
    ("갤럭시 S23 울트라 256GB", "digital"),
    ("갤럭시 S22 128GB", "digital"),
    ("갤럭시 Z폴드5 256GB", "digital"),
    ("갤럭시 버즈2 프로", "digital"),
    ("맥북 에어 M2 13인치", "digital"),
    ("맥북 프로 M3 14인치", "digital"),
    ("LG 그램 16인치 2023", "digital"),
    ("삼성 갤럭시북3 프로", "digital"),
    ("아이패드 프로 12.9인치 M2", "digital"),
    ("애플워치 시리즈9 45mm", "digital"),
    ("에어팟 프로 2세대", "digital"),
    ("소니 WH-1000XM5 헤드폰", "digital"),
    ("로지텍 MX Keys 키보드", "digital"),
    ("로지텍 MX Master 3 마우스", "digital"),
    ("닌텐도 스위치 OLED", "game"),
    ("닌텐도 스위치 라이트", "game"),
    ("플레이스테이션5 디스크 에디션", "game"),
    ("엑스박스 시리즈X", "game"),
    ("스팀덱 512GB", "game"),
    ("포켓몬 스칼렛 바이올렛 세트", "game"),
    ("원목 책상 1200", "furniture"),
    ("원목 책상 1400 서랍형", "furniture"),
    ("높이조절 스탠딩 책상", "furniture"),
    ("인체공학 의자 허먼밀러", "furniture"),
    ("소파 3인용 패브릭", "furniture"),
    ("접이식 선반 5단", "furniture"),
    ("이케아 빌리 책장", "furniture"),
    ("캠핑 의자 세트", "outdoor"),
    ("캠핑 텐트 4인용", "outdoor"),
    ("캠핑 테이블 경량", "outdoor"),
    ("등산 배낭 40L", "outdoor"),
    ("자전거 로드바이크 입문용", "outdoor"),
    ("샤오미 공기청정기", "home"),
    ("다이슨 청소기 V15", "home"),
    ("LG 스타일러 3벌", "home"),
    ("커피머신 드롱기 전자동", "home"),
    ("미니 냉장고 소형", "home"),
    ("에어프라이어 대형", "home"),
    ("폴로 니트 가디건", "fashion"),
    ("노스페이스 눕시 패딩", "fashion"),
    ("아디다스 운동화 280", "fashion"),
    ("나이키 조던1 레트로", "fashion"),
    ("캐나다구스 재킷 M", "fashion"),
    ("버버리 트렌치코트 L", "fashion"),
]

CONDITIONS = ["S급 (미사용)", "A급 (상태 최상)", "B급 (정상 사용감)", "C급 (흠집 있음)"]
DESCRIPTIONS = [
    "개인 사정으로 판매합니다. 직거래 우선이며 택배 가능합니다.",
    "선물받았는데 사용 안 해서 팝니다. 박스 풀 구성입니다.",
    "구매 후 거의 사용 안 했습니다. 상태 사진 요청 가능합니다.",
    "이사로 인해 급처합니다. 흥정 가능합니다.",
    "정품 구매 영수증 있습니다. 상태 매우 좋습니다.",
    "6개월 사용했습니다. 기능 이상 없으며 깨끗합니다.",
    "1년 사용 제품입니다. 스크래치 있지만 작동 완벽합니다.",
    "해외 직구 제품입니다. 구성품 모두 있습니다.",
]


def build_payload(index: int, randomizer: Random) -> dict:
    title, category = TITLES[randomizer.randint(0, len(TITLES) - 1)]
    location = LOCATIONS[randomizer.randint(0, len(LOCATIONS) - 1)]
    condition = CONDITIONS[randomizer.randint(0, len(CONDITIONS) - 1)]
    description_base = DESCRIPTIONS[randomizer.randint(0, len(DESCRIPTIONS) - 1)]
    listing_id = 1000 + index
    price = randomizer.randint(1, 200) * 5000
    likes = randomizer.randint(0, 300)
    views = randomizer.randint(50, 5000)
    score = likes * 3 + views
    seller_id = 500 + randomizer.randint(0, 99)
    month = randomizer.randint(1, 3)
    day = randomizer.randint(1, 28)
    hour = randomizer.randint(8, 23)
    return {
        "key": f"listing:{listing_id}",
        "doc_type": "listing",
        "listing_id": listing_id,
        "title": title,
        "category": category,
        "location": location,
        "condition": condition,
        "price": price,
        "likes": likes,
        "views": views,
        "score": score,
        "status": randomizer.choice(["판매중", "판매중", "판매중", "예약중", "판매완료"]),
        "created_at": f"2026-{month:02d}-{day:02d}T{hour:02d}:30:00+09:00",
        "description": f"{title} 중고 매물입니다. {description_base} 직거래는 {location} 가능합니다. 상태: {condition}.",
        "keywords": [title.split()[0], category, location.split()[0]],
        "seller": {
            "seller_id": seller_id,
            "nickname": f"동네판매자{seller_id}",
            "area": location,
            "rating": round(randomizer.uniform(3.5, 5.0), 1),
            "trade_count": randomizer.randint(1, 200),
            "response_rate": f"{randomizer.randint(70, 100)}%",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo documents into MongoDB.")
    parser.add_argument("--count", type=int, default=2000)
    args = parser.parse_args()

    settings = Settings()
    repo = MongoRepository(settings.mongo_uri, settings.mongo_database, settings.mongo_collection)
    randomizer = Random(7)
    for index in range(1, args.count + 1):
        payload = build_payload(index, randomizer)
        repo.upsert_document(payload["key"], payload)
    print(f"Seeded {args.count} documents into {settings.mongo_database}.{settings.mongo_collection}")


def warm() -> None:
    parser = argparse.ArgumentParser(description="Pre-warm Redis cache from MongoDB.")
    parser.add_argument("--ttl", type=int, default=300, help="TTL in seconds (default: 300)")
    args = parser.parse_args()

    settings = Settings()
    repo = MongoRepository(settings.mongo_uri, settings.mongo_database, settings.mongo_collection)

    if settings.mini_redis_backend == "stub":
        redis_client = MiniRedisStubClient()
    else:
        redis_client = MiniRedisTCPClient(settings.mini_redis_host, settings.mini_redis_port, settings.mini_redis_timeout)

    collection = repo._connect()
    docs = list(collection.find({"doc_type": "listing"}, {"_id": 0}))
    count = 0
    for doc in docs:
        key = doc.get("key")
        if not key:
            continue
        redis_client.set(key, json.dumps(doc, ensure_ascii=False))
        redis_client.expire(key, args.ttl)
        count += 1

    print(f"Warmed {count} listings into Redis (TTL={args.ttl}s)")


if __name__ == "__main__":
    main()
