import random
from datetime import datetime, timedelta
from pymongo import MongoClient, InsertMany
from pymongo import ASCENDING
import uuid

# ── 설정 ──────────────────────────────────────────
MONGO_URI = "mongodb://localhost:27017"
DB_NAME   = "qa_db"
COL_NAME  = "products"
TOTAL     = 500_000
BATCH     = 5_000          # 한 번에 insert할 개수
# ──────────────────────────────────────────────────

CATEGORIES = ["digital", "fashion", "furniture", "sports", "beauty", "food", "book", "toy"]
LOCATIONS  = ["성남시 분당구", "서울시 강남구", "서울시 마포구", "부산시 해운대구",
               "인천시 연수구", "대구시 수성구", "광주시 북구", "수원시 영통구"]
STATUSES   = ["판매중", "예약중", "판매완료"]
TITLES     = ["아이폰 14 프로 256GB", "갤럭시 S23", "맥북 프로 M2", "나이키 운동화",
               "소파 3인용", "요가매트", "텀블러", "무선 이어폰", "키보드", "모니터 27인치"]
KEYWORDS_POOL = ["아이폰", "갤럭시", "맥북", "나이키", "가구", "디지털", "중고", "직거래",
                 "성남시", "서울", "부산", "A급", "무료배송"]

def random_date():
    base = datetime(2024, 1, 1)
    offset = random.randint(0, 365 * 2)
    dt = base + timedelta(days=offset, hours=random.randint(0, 23), minutes=random.randint(0, 59))
    return dt.strftime("%Y-%m-%dT%H:%M:%S+09:00")

def make_doc(i):
    listing_id = 1001 + i
    category   = random.choice(CATEGORIES)
    location   = random.choice(LOCATIONS)
    title      = random.choice(TITLES)
    seller_id  = random.randint(1, 10000)

    return {
        "key":         f"listing:{listing_id}",
        "category":    category,
        "created_at":  random_date(),
        "description": f"{title} 중고 매물입니다. 직거래는 {location} 가능하고, 상태는 A급입니다.",
        "doc_type":    "listing",
        "keywords":    random.sample(KEYWORDS_POOL, k=3),
        "likes":       random.randint(0, 500),
        "listing_id":  listing_id,
        "location":    location,
        "price":       random.randint(1000, 500000),
        "score":       random.randint(100, 9999),
        "seller": {
            "seller_id":     seller_id,
            "nickname":      f"동네판매자{seller_id}",
            "area":          location,
            "rating":        round(random.uniform(1.0, 5.0), 1),
            "trade_count":   random.randint(0, 200),
            "response_rate": f"{random.randint(50, 100)}%",
        },
        "status":  random.choice(STATUSES),
        "title":   title,
        "views":   random.randint(0, 5000),
    }

def main():
    client = MongoClient(MONGO_URI)
    col    = client[DB_NAME][COL_NAME]

    print(f"[시작] {TOTAL:,}개 insert → {DB_NAME}.{COL_NAME}")
    inserted = 0

    while inserted < TOTAL:
        batch_size = min(BATCH, TOTAL - inserted)
        docs = [make_doc(inserted + j) for j in range(batch_size)]
        col.insert_many(docs, ordered=False)
        inserted += batch_size
        print(f"  {inserted:>7,} / {TOTAL:,} ({inserted/TOTAL*100:.1f}%)")

    print(f"[완료] 총 {inserted:,}개 insert 완료")
    client.close()

if __name__ == "__main__":
    main()