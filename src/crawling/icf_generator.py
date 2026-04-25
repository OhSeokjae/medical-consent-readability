"""CRIS 임상시험 정보 기반 모의 동의서(ICF) 생성기 (GPT-4o)"""

import json
import os
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "configs" / "config.yaml"
TRIALS_PATH = PROJECT_ROOT / "data" / "raw" / "cris_trials.json"
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "mock_icf"

with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

REQUIRED_ELEMENTS = CONFIG["required_elements"]

SYSTEM_PROMPT = """당신은 한국 대형 대학병원 IRB에서 15년 경력의 임상시험 동의서(ICF) 작성 전문가입니다.
주어진 임상시험 정보를 바탕으로 KGCP(의약품 임상시험 관리기준) 제7호아목10)에 따른
시험대상자설명서 및 동의서를 작성해주세요.

[중요: 분량 기준]
- 전체 동의서는 최소 10,000자(한글 기준) 이상이어야 합니다.
- 각 섹션은 최소 500자 이상으로 작성합니다. 짧은 섹션은 부적합합니다.
- 실제 병원에서 사용하는 10~20페이지 분량의 동의서를 목표로 합니다.

작성 규칙:
1. 실제 병원에서 사용하는 동의서와 동일한 형식과 어조를 사용합니다.
2. 아래 20개 필수항목을 각각 별도 섹션으로 구분하여 작성합니다.
3. 각 섹션은 "## [항목ID] 항목명" 형식의 마크다운 헤더로 시작합니다.
4. 의학적으로 타당하고 현실적인 내용을 작성합니다.
5. 전문용어와 평이한 설명을 혼합하여 다양한 가독성 수준이 나타나도록 합니다.
6. 응답은 반드시 한국어로 작성합니다.
7. 각 섹션에 아래와 같은 구체적 내용을 반드시 포함합니다:
   - [research_purpose]: 연구의 배경, 해당 질환의 역학, 기존 치료의 한계, 본 연구의 필요성
   - [study_objective]: 1차/2차 평가변수, 구체적 연구 가설
   - [drug_info_randomization]: 약물 작용기전, 용법·용량, 투여경로, 배정비율, 눈가림 방법
   - [procedures]: 방문별(스크리닝/투여/추적) 검사 스케줄표(마크다운 표 형식), 채혈량, 검사 항목 상세
   - [compliance]: 금지약물 목록, 피임 요건, 음주/흡연/운동 제한, 일지 작성 의무
   - [risks]: 부작용을 빈도별(매우 흔함≥10%/흔함1~10%/흔하지않음0.1~1%/드묾0.01~0.1%/매우드묾<0.01%)로 분류한 목록, 임부·수유부 위험
   - [benefits]: 직접적 이익과 간접적 이익 구분, 이익이 없을 수 있다는 점
   - [alternatives]: 대체 치료법의 구체적 명칭, 각각의 장단점
   - [injury_compensation]: 보상 절차, 임상시험배상책임보험 정보, 인과관계 판정 절차
   - [financial_compensation]: 방문별 보상 금액, 중도 탈락 시 보상 기준
   - [procedures]: 총 방문 횟수, 각 방문 소요 시간, 입원 여부
   - [contact]: 연구책임자, 24시간 응급연락처, IRB 연락처를 모두 포함
8. 마크다운 표(|---|---|)와 번호 목록을 적극 활용하여 가독성을 높입니다.

필수항목 목록 (20개):
"""

for elem in REQUIRED_ELEMENTS:
    SYSTEM_PROMPT += f"- [{elem['id']}] {elem['name']} (KGCP {elem['kgcp_ref']})\n"


def build_user_prompt(trial: dict) -> str:
    """임상시험 메타데이터로 유저 프롬프트를 구성한다."""
    return f"""다음 임상시험 정보를 바탕으로 시험대상자설명서 및 동의서를 작성해주세요.

## 임상시험 정보
- 등록번호: {trial.get('trial_id', '')}
- 연구 제목(국문): {trial.get('scientific_title_kr', '')}
- 연구 제목(영문): {trial.get('scientific_title_en', '')}
- 중재 종류: {trial.get('i_freetext_kr', '')}
- 임상시험 단계: {trial.get('phase_kr', '')}
- 연구책임기관: {trial.get('primary_sponsor_kr', '')}
- 출처 기관: {trial.get('source_name_kr', '')}
- 주요 결과변수: {trial.get('primary_outcome_1_kr', '')}
- 등록일: {trial.get('date_registration', '')}

위 정보를 기반으로 20개 필수항목을 각각 "## [항목ID] 항목명" 헤더 아래에 작성해주세요.
실제 동의서처럼 구체적이고 현실적인 내용으로 작성하되, 적절한 가상 데이터(방문 횟수, 채혈량, 보상금액 등)를 포함해주세요."""


def parse_sections(text: str) -> dict[str, str]:
    """생성된 동의서 텍스트에서 항목별 섹션을 파싱한다."""
    sections = {}
    current_id = None
    current_lines = []

    for line in text.split("\n"):
        if line.startswith("## ["):
            if current_id:
                sections[current_id] = "\n".join(current_lines).strip()
            bracket_end = line.index("]")
            current_id = line[4:bracket_end]
            current_lines = []
        elif current_id is not None:
            current_lines.append(line)

    if current_id:
        sections[current_id] = "\n".join(current_lines).strip()

    return sections


def _build_batch_prompt(trial: dict, elements: list[dict]) -> str:
    """배치(부분) 생성용 유저 프롬프트를 구성한다."""
    elem_list = "\n".join(
        f"- [{e['id']}] {e['name']}" for e in elements
    )
    return f"""다음 임상시험 정보를 바탕으로 아래 항목들만 작성해주세요.

## 임상시험 정보
- 등록번호: {trial.get('trial_id', '')}
- 연구 제목(국문): {trial.get('scientific_title_kr', '')}
- 연구 제목(영문): {trial.get('scientific_title_en', '')}
- 중재 종류: {trial.get('i_freetext_kr', '')}
- 임상시험 단계: {trial.get('phase_kr', '')}
- 연구책임기관: {trial.get('primary_sponsor_kr', '')}
- 출처 기관: {trial.get('source_name_kr', '')}
- 주요 결과변수: {trial.get('primary_outcome_1_kr', '')}
- 등록일: {trial.get('date_registration', '')}

## 작성할 항목 ({len(elements)}개)
{elem_list}

각 항목을 "## [항목ID] 항목명" 헤더 아래에 최소 500자 이상으로 상세히 작성해주세요.
실제 동의서처럼 구체적 수치, 표, 목록을 포함하세요."""


# 20개 항목을 4개 배치로 분할
BATCH_SIZE = 5


def generate_icf(client: OpenAI, trial: dict, model: str = "gpt-4o") -> dict:
    """GPT-4o로 모의 동의서를 배치 분할 생성한다 (4회 호출)."""
    all_sections = {}
    all_texts = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    used_model = model

    batches = [
        REQUIRED_ELEMENTS[i : i + BATCH_SIZE]
        for i in range(0, len(REQUIRED_ELEMENTS), BATCH_SIZE)
    ]

    for batch_idx, batch_elems in enumerate(batches):
        resp = client.chat.completions.create(
            model=model,
            max_tokens=CONFIG["llm"]["max_tokens"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_batch_prompt(trial, batch_elems)},
            ],
        )

        batch_text = resp.choices[0].message.content
        batch_sections = parse_sections(batch_text)

        all_texts.append(batch_text)
        all_sections.update(batch_sections)
        total_prompt_tokens += resp.usage.prompt_tokens
        total_completion_tokens += resp.usage.completion_tokens
        used_model = resp.model

        if batch_idx < len(batches) - 1:
            time.sleep(0.5)

    full_text = "\n\n".join(all_texts)

    return {
        "trial_id": trial["trial_id"],
        "metadata": trial,
        "full_text": full_text,
        "sections": all_sections,
        "model": used_model,
        "usage": {
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
        },
    }


def select_trials(
    trials: list[dict],
    n: int = 50,
    priority_types: list[str] | None = None,
) -> list[dict]:
    """모의 동의서 생성 대상 임상시험을 선별한다."""
    if priority_types is None:
        priority_types = ["의약품", "시술수술", "의료기구"]

    priority = [t for t in trials if t.get("i_freetext_kr", "") in priority_types]
    others = [t for t in trials if t.get("i_freetext_kr", "") not in priority_types]

    selected = priority[:n]
    if len(selected) < n:
        selected += others[: n - len(selected)]

    return selected[:n]


def run(n: int = 50, delay: float = 1.0):
    """메인 실행: 임상시험 선별 → 모의 동의서 생성 → 저장"""
    client = OpenAI()
    model = CONFIG["llm"]["model"]

    with open(TRIALS_PATH, encoding="utf-8") as f:
        all_trials = json.load(f)

    selected = select_trials(all_trials, n=n)
    print(f"선별된 임상시험: {len(selected)}건 (전체 {len(all_trials)}건 중)")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    total_tokens = 0

    for i, trial in enumerate(selected):
        trial_id = trial["trial_id"]
        output_path = OUTPUT_DIR / f"{trial_id}.json"

        if output_path.exists():
            print(f"  [{i+1}/{len(selected)}] {trial_id} — 이미 존재, 건너뜀")
            continue

        print(f"  [{i+1}/{len(selected)}] {trial_id} 생성 중... ", end="", flush=True)

        try:
            result = generate_icf(client, trial, model=model)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            n_sections = len(result["sections"])
            tokens = result["usage"]["prompt_tokens"] + result["usage"]["completion_tokens"]
            total_tokens += tokens
            print(f"완료 (항목 {n_sections}/20, {tokens} tokens)")

        except Exception as e:
            print(f"실패: {e}")

        if i < len(selected) - 1:
            time.sleep(delay)

    print(f"\n생성 완료: {OUTPUT_DIR}")
    print(f"총 토큰 사용량: {total_tokens:,}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="모의 동의서(ICF) 생성")
    parser.add_argument("-n", type=int, default=50, help="생성할 동의서 수 (기본: 50)")
    parser.add_argument("--delay", type=float, default=1.0, help="API 호출 간 대기 시간(초)")
    args = parser.parse_args()

    run(n=args.n, delay=args.delay)
