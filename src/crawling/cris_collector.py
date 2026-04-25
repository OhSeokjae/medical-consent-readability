"""CRIS 임상연구 데이터 수집기 (공공데이터포털 API)"""

import json
import time
import requests
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

API_URL = "http://apis.data.go.kr/1352159/crisinfodataview/list"
SERVICE_KEY = os.getenv("DATA_GO_KR_API_KEY")
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "data" / "raw" / "cris_trials.json"

FIELDS_TO_KEEP = [
    "trial_id",
    "scientific_title_kr",
    "scientific_title_en",
    "study_type_kr",
    "i_freetext_kr",
    "phase_kr",
    "primary_sponsor_kr",
    "source_name_kr",
    "primary_outcome_1_kr",
    "date_registration",
    "date_enrolment",
    "results_date_completed",
]


def fetch_page(page_no: int, num_of_rows: int = 50) -> dict:
    """API에서 한 페이지 데이터를 가져온다."""
    params = {
        "serviceKey": SERVICE_KEY,
        "resultType": "JSON",
        "numOfRows": num_of_rows,
        "pageNo": page_no,
    }
    resp = requests.get(API_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def filter_item(item: dict) -> dict | None:
    """중재연구만 필터링하고 필요한 필드만 추출한다."""
    if item.get("study_type_kr") != "중재연구":
        return None
    return {k: item.get(k, "") for k in FIELDS_TO_KEEP}


def collect_all(delay: float = 1.0) -> list[dict]:
    """전체 페이지를 순회하며 중재연구 데이터를 수집한다."""
    first = fetch_page(1, num_of_rows=50)
    total_count = int(first["totalCount"])
    num_of_rows = 50
    total_pages = (total_count + num_of_rows - 1) // num_of_rows

    print(f"전체 데이터: {total_count}건 / {total_pages}페이지")

    trials = []

    for page_no in range(1, total_pages + 1):
        if page_no == 1:
            data = first
        else:
            data = fetch_page(page_no, num_of_rows)

        items = data.get("items", [])
        for item in items:
            filtered = filter_item(item)
            if filtered:
                trials.append(filtered)

        print(f"  [{page_no}/{total_pages}] 수집된 중재연구: {len(trials)}건", end="\r")

        if page_no < total_pages:
            time.sleep(delay)

    print(f"\n수집 완료: 중재연구 {len(trials)}건")
    return trials


def save(trials: list[dict]) -> None:
    """수집된 데이터를 JSON 파일로 저장한다."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(trials, f, ensure_ascii=False, indent=2)
    print(f"저장 완료: {OUTPUT_PATH} ({len(trials)}건)")


if __name__ == "__main__":
    trials = collect_all(delay=1.0)
    save(trials)
