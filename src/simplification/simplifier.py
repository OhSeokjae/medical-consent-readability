"""ICF 평이화 모듈 (GPT-4o 기반)

가독성 분석 결과 ICF 권장 수준(≤중2, ≤8th grade)을 초과하는 섹션을
GPT-4o로 평이하게 재작성하고, 평이화 전후 가독성을 비교 분석한다.

평이화 원칙 [R5, R7]:
  1. 전문용어 → 쉬운 우리말 + 괄호 원어 병기
  2. 긴 문장 → 짧은 문장으로 분리 (≤15 어절 목표)
  3. 한자어 → 순우리말 대체 (가능한 경우)
  4. 피동·사동 → 능동 표현
  5. 내용의 정확성·완전성 유지 (의미 손실 금지)
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "configs" / "config.yaml"

with open(CONFIG_PATH, encoding="utf-8") as _f:
    CONFIG = yaml.safe_load(_f)

ICF_DIR = PROJECT_ROOT / "data" / "raw" / "mock_icf"
READABILITY_PATH = PROJECT_ROOT / "data" / "processed" / "readability_results.json"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "simplified_icf"

# 평이화 대상 기준: 학년 수준 > 8 (ICF 국제 권장 초과)
GRADE_THRESHOLD = 8.0

SYSTEM_PROMPT = """당신은 한국어 의학 문서 평이화(plain language) 전문가입니다.
임상시험 동의서(ICF)의 텍스트를 중학교 2학년(8th grade) 수준으로 쉽게 재작성해주세요.

## 평이화 규칙

1. **전문용어 처리**
   - 의학 전문용어는 쉬운 우리말로 바꾸고, 괄호 안에 원래 용어를 병기합니다.
   - 예: "약동학적 생동성" → "몸속에서 약이 흡수되고 배출되는 과정이 같은지(약동학적 생동성)"
   - 예: "이중맹검" → "환자와 의사 모두 어떤 약을 받았는지 모르는 방법(이중맹검)"

2. **문장 길이**
   - 한 문장은 15단어(어절) 이내로 작성합니다.
   - 긴 문장은 여러 짧은 문장으로 나눕니다.

3. **한자어 대체**
   - "투여" → "사용" 또는 "복용"
   - "이상반응" → "원하지 않는 반응"
   - "경구" → "입으로 먹는"
   - 불가피한 한자어는 그대로 쓰되, 풀이를 덧붙입니다.

4. **문법 단순화**
   - 피동 표현 → 능동 표현: "투여됩니다" → "드립니다"/"복용합니다"
   - 이중 부정 → 긍정: "~하지 않을 수 없다" → "~해야 합니다"
   - 명사화 구문 → 서술형: "검사의 시행" → "검사를 합니다"

5. **내용 보존 (필수)**
   - 의학적으로 중요한 정보를 빠뜨리거나 왜곡하지 마세요.
   - 부작용, 위험, 절차 등의 구체적 내용은 반드시 유지합니다.
   - 숫자, 비율, 기간 등 정량 정보는 그대로 유지합니다.

6. **형식**
   - 입력과 동일한 마크다운 형식을 유지합니다.
   - 표(|---|)가 있으면 표 형식을 유지합니다.
   - 번호 목록이 있으면 목록 형식을 유지합니다.

응답은 평이화된 텍스트만 출력합니다. 설명이나 메타 코멘트를 추가하지 마세요.
"""


def simplify_section(
    client: OpenAI,
    section_text: str,
    section_id: str,
    section_name: str,
    model: str = "gpt-4o",
) -> str:
    """단일 섹션을 평이화한다."""
    user_prompt = f"""다음 임상시험 동의서의 [{section_id}] "{section_name}" 섹션을 평이화해주세요.

--- 원문 ---
{section_text}
--- 끝 ---

위 텍스트를 중학교 2학년이 읽을 수 있는 수준으로 쉽게 고쳐 주세요."""

    resp = client.chat.completions.create(
        model=model,
        max_tokens=4000,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    return resp.choices[0].message.content


def simplify_icf(
    client: OpenAI,
    icf_path: Path,
    readability: dict | None = None,
    model: str = "gpt-4o",
    grade_threshold: float = GRADE_THRESHOLD,
) -> dict:
    """ICF 1건의 어려운 섹션들을 평이화한다.

    Args:
        icf_path: 모의 ICF JSON 파일 경로
        readability: 해당 ICF의 가독성 분석 결과 (없으면 전 섹션 평이화)
        model: 사용할 LLM 모델
        grade_threshold: 평이화 대상 학년 수준 기준

    Returns:
        평이화 결과 dict
    """
    with open(icf_path, encoding="utf-8") as f:
        data = json.load(f)

    trial_id = data.get("trial_id", "")
    sections = data.get("sections", {})

    # KGCP 항목 이름 매핑
    element_names = {
        e["id"]: e["name"] for e in CONFIG["required_elements"]
    }

    # 평이화 대상 섹션 결정
    target_sections = {}
    if readability and "section_level" in readability:
        for sid, metrics in readability["section_level"].items():
            if metrics["grade_level"] > grade_threshold and sid in sections:
                target_sections[sid] = metrics["grade_level"]
    else:
        # 가독성 데이터 없으면 전체 섹션 대상
        target_sections = {sid: 0 for sid in sections}

    simplified_sections = {}
    original_sections = {}
    total_tokens = 0

    for sid in sorted(target_sections.keys()):
        if sid not in sections or not sections[sid].strip():
            continue

        original_text = sections[sid]
        section_name = element_names.get(sid, sid)

        simplified_text = simplify_section(
            client, original_text, sid, section_name, model
        )

        simplified_sections[sid] = simplified_text
        original_sections[sid] = original_text
        time.sleep(0.3)

    # 평이화하지 않은 섹션은 원문 유지
    full_simplified = {}
    for sid, text in sections.items():
        if sid in simplified_sections:
            full_simplified[sid] = simplified_sections[sid]
        else:
            full_simplified[sid] = text

    return {
        "trial_id": trial_id,
        "model": model,
        "grade_threshold": grade_threshold,
        "num_simplified": len(simplified_sections),
        "num_total_sections": len(sections),
        "simplified_section_ids": sorted(simplified_sections.keys()),
        "sections_original": original_sections,
        "sections_simplified": simplified_sections,
        "full_sections": full_simplified,
    }


def run(
    n: int = 50,
    grade_threshold: float = GRADE_THRESHOLD,
    delay: float = 1.0,
):
    """전체 ICF 배치 평이화를 실행한다."""
    client = OpenAI()
    model = CONFIG["llm"]["model"]

    # 가독성 결과 로드
    readability_map = {}
    if READABILITY_PATH.exists():
        with open(READABILITY_PATH, encoding="utf-8") as f:
            readability_data = json.load(f)
        for r in readability_data:
            readability_map[r["trial_id"]] = r

    # ICF 파일 목록
    icf_files = sorted(ICF_DIR.glob("*.json"))[:n]
    print(f"평이화 대상: {len(icf_files)}건 (학년 > {grade_threshold} 섹션)")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results_summary = []

    for i, fpath in enumerate(icf_files):
        trial_id = fpath.stem
        output_path = OUTPUT_DIR / f"{trial_id}.json"

        if output_path.exists():
            print(f"  [{i+1}/{len(icf_files)}] {trial_id} — 이미 존재, 건너뜀")
            # 기존 결과 로드하여 summary에 추가
            with open(output_path, encoding="utf-8") as f:
                existing = json.load(f)
            results_summary.append({
                "trial_id": trial_id,
                "num_simplified": existing.get("num_simplified", 0),
                "num_total_sections": existing.get("num_total_sections", 0),
            })
            continue

        readability = readability_map.get(trial_id)
        print(f"  [{i+1}/{len(icf_files)}] {trial_id} 평이화 중... ", end="", flush=True)

        try:
            result = simplify_icf(
                client, fpath, readability, model, grade_threshold
            )

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            n_simplified = result["num_simplified"]
            n_total = result["num_total_sections"]
            print(f"완료 ({n_simplified}/{n_total} 섹션 평이화)")

            results_summary.append({
                "trial_id": trial_id,
                "num_simplified": n_simplified,
                "num_total_sections": n_total,
            })

        except Exception as e:
            print(f"실패: {e}")

        if i < len(icf_files) - 1:
            time.sleep(delay)

    # 요약
    if results_summary:
        total_simplified = sum(r["num_simplified"] for r in results_summary)
        total_sections = sum(r["num_total_sections"] for r in results_summary)
        print(f"\n평이화 완료: {OUTPUT_DIR}")
        print(f"총 평이화 섹션: {total_simplified}/{total_sections}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ICF 평이화")
    parser.add_argument("-n", type=int, default=50, help="평이화할 ICF 수")
    parser.add_argument(
        "--threshold", type=float, default=GRADE_THRESHOLD,
        help=f"평이화 대상 학년 기준 (기본: {GRADE_THRESHOLD})",
    )
    parser.add_argument("--delay", type=float, default=1.0, help="API 호출 간 대기(초)")
    args = parser.parse_args()

    run(n=args.n, grade_threshold=args.threshold, delay=args.delay)
