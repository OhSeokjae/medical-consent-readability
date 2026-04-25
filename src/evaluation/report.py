"""ICF 가독성 분석 종합 리포트 및 시각화 모듈

Step 1~5 결과를 종합하여:
  1. 가독성 분포 시각화 (학년 수준, 종합 점수)
  2. 섹션별 난이도 히트맵
  3. 평이화 전후 비교 차트
  4. 완전성 분석 요약
  5. 종합 리포트 텍스트 생성
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns
import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"
REPORTS_DIR = PROJECT_ROOT / "outputs" / "reports"

# 데이터 경로
READABILITY_PATH = PROJECT_ROOT / "data" / "processed" / "readability_results.json"
COMPLETENESS_PATH = PROJECT_ROOT / "data" / "processed" / "completeness_results.json"
COMPARISON_PATH = PROJECT_ROOT / "data" / "processed" / "comparison_results.json"

# 한글 폰트 설정 (macOS)
_FONT_CANDIDATES = [
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/Library/Fonts/NanumGothic.ttf",
]

def _setup_korean_font():
    for fp in _FONT_CANDIDATES:
        if Path(fp).exists():
            fm.fontManager.addfont(fp)
            prop = fm.FontProperties(fname=fp)
            name = prop.get_name()
            plt.rcParams["font.family"] = name
            plt.rcParams["font.sans-serif"] = [name, "Arial"]
            break
    plt.rcParams["axes.unicode_minus"] = False

# 공통 스타일 (폰트 설정 전에 sns.set_theme 호출)
sns.set_theme(style="whitegrid", font_scale=1.1)
_setup_korean_font()
COLORS = {"original": "#e74c3c", "simplified": "#2ecc71", "target": "#3498db"}


# ──────────────────────────────────────────────
# 데이터 로드
# ──────────────────────────────────────────────

def load_readability() -> list[dict]:
    with open(READABILITY_PATH, encoding="utf-8") as f:
        return json.load(f)

def load_completeness() -> list[dict]:
    with open(COMPLETENESS_PATH, encoding="utf-8") as f:
        return json.load(f)

def load_comparison() -> list[dict]:
    with open(COMPARISON_PATH, encoding="utf-8") as f:
        return json.load(f)


# ──────────────────────────────────────────────
# Figure 1: 가독성 분포 (학년 수준 히스토그램)
# ──────────────────────────────────────────────

def fig1_grade_distribution(readability: list[dict]) -> Path:
    grades = [r["document_level"]["grade_level"] for r in readability]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(grades, bins=15, color=COLORS["original"], alpha=0.7, edgecolor="white")
    ax.axvline(x=8, color=COLORS["target"], linestyle="--", linewidth=2,
               label="ICF 권장 기준 (≤8학년)")
    ax.set_xlabel("학년 수준 (Grade Level)")
    ax.set_ylabel("ICF 수")
    ax.set_title("원문 ICF 가독성 분포 (이독성 공식 학년 수준)")
    ax.legend()

    mean_grade = np.mean(grades)
    ax.annotate(f"평균: {mean_grade:.1f}학년",
                xy=(mean_grade, 0), xytext=(mean_grade + 1, ax.get_ylim()[1] * 0.8),
                arrowprops=dict(arrowstyle="->", color="gray"),
                fontsize=11, color="gray")

    path = FIGURES_DIR / "fig1_grade_distribution.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


# ──────────────────────────────────────────────
# Figure 2: 섹션별 평균 학년 수준 (수평 막대)
# ──────────────────────────────────────────────

def fig2_section_difficulty(readability: list[dict]) -> Path:
    # 섹션별 평균 학년 집계
    section_grades = {}
    for r in readability:
        for sid, sec in r.get("section_level", {}).items():
            section_grades.setdefault(sid, []).append(sec["grade_level"])

    df = pd.DataFrame([
        {"section": sid, "avg_grade": np.mean(grades)}
        for sid, grades in section_grades.items()
    ]).sort_values("avg_grade")

    fig, ax = plt.subplots(figsize=(10, 8))
    bars = ax.barh(df["section"], df["avg_grade"],
                   color=[COLORS["original"] if g > 8 else COLORS["simplified"]
                          for g in df["avg_grade"]],
                   edgecolor="white")
    ax.axvline(x=8, color=COLORS["target"], linestyle="--", linewidth=2,
               label="권장 기준 (≤8학년)")
    ax.set_xlabel("평균 학년 수준")
    ax.set_title("KGCP 섹션별 평균 가독성 수준 (원문)")
    ax.legend(loc="lower right")

    for bar, grade in zip(bars, df["avg_grade"]):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                f"{grade:.1f}", va="center", fontsize=9)

    path = FIGURES_DIR / "fig2_section_difficulty.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


# ──────────────────────────────────────────────
# Figure 3: 평이화 전후 비교 (paired bar chart)
# ──────────────────────────────────────────────

def fig3_simplification_comparison(comparison: list[dict]) -> Path:
    # 섹션별 전후 평균 집계
    orig_grades = {}
    simp_grades = {}
    for r in comparison:
        for sid, comp in r.get("section_comparisons", {}).items():
            orig_grades.setdefault(sid, []).append(comp["original"]["grade_level"])
            simp_grades.setdefault(sid, []).append(comp["simplified"]["grade_level"])

    sections = sorted(orig_grades.keys(),
                      key=lambda s: np.mean(orig_grades[s]), reverse=True)

    orig_means = [np.mean(orig_grades[s]) for s in sections]
    simp_means = [np.mean(simp_grades[s]) for s in sections]

    x = np.arange(len(sections))
    width = 0.35

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.bar(x - width / 2, orig_means, width, label="원문", color=COLORS["original"], alpha=0.8)
    ax.bar(x + width / 2, simp_means, width, label="평이화", color=COLORS["simplified"], alpha=0.8)
    ax.axhline(y=8, color=COLORS["target"], linestyle="--", linewidth=2,
               label="권장 기준 (≤8학년)")

    ax.set_xticks(x)
    ax.set_xticklabels(sections, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("평균 학년 수준")
    ax.set_title("KGCP 섹션별 평이화 전후 학년 수준 비교")
    ax.legend()

    path = FIGURES_DIR / "fig3_simplification_comparison.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


# ──────────────────────────────────────────────
# Figure 4: 종합 점수 변화 (scatter plot)
# ──────────────────────────────────────────────

def fig4_score_improvement(comparison: list[dict]) -> Path:
    orig_scores = []
    simp_scores = []

    for r in comparison:
        s = r.get("document_summary", {})
        if s:
            orig_scores.append(s["original_avg_grade"])
            simp_scores.append(s["simplified_avg_grade"])

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.scatter(orig_scores, simp_scores, alpha=0.6, s=60, color=COLORS["original"],
               edgecolor="white", linewidth=0.5)

    # 대각선 (변화 없음)
    lims = [min(min(orig_scores), min(simp_scores)) - 1,
            max(max(orig_scores), max(simp_scores)) + 1]
    ax.plot(lims, lims, "k--", alpha=0.3, label="변화 없음")

    # 목표선
    ax.axhline(y=8, color=COLORS["target"], linestyle="--", alpha=0.7, label="목표 (≤8학년)")

    ax.set_xlabel("원문 평균 학년 수준")
    ax.set_ylabel("평이화 평균 학년 수준")
    ax.set_title("ICF별 평이화 전후 학년 수준")
    ax.legend()
    ax.set_xlim(lims)
    ax.set_ylim(lims)

    path = FIGURES_DIR / "fig4_score_improvement.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


# ──────────────────────────────────────────────
# Figure 5: 완전성 분석 요약
# ──────────────────────────────────────────────

def fig5_completeness(completeness: list[dict]) -> Path:
    scores = [r["completeness_score"] for r in completeness]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # 왼쪽: 완전성 점수 분포
    axes[0].hist(scores, bins=10, color="#9b59b6", alpha=0.7, edgecolor="white")
    axes[0].set_xlabel("완전성 점수")
    axes[0].set_ylabel("ICF 수")
    axes[0].set_title("KGCP 완전성 점수 분포")
    axes[0].axvline(x=1.0, color="green", linestyle="--", label="완전(20/20)")
    axes[0].legend()

    # 오른쪽: 항목별 탐지율
    from collections import Counter
    label_counts = Counter()
    for r in completeness:
        for label in r["present"]:
            label_counts[label] += 1
    total = len(completeness)

    labels_sorted = sorted(label_counts.keys(),
                           key=lambda k: label_counts[k])
    rates = [label_counts[l] / total for l in labels_sorted]

    axes[1].barh(labels_sorted, rates, color="#9b59b6", alpha=0.7, edgecolor="white")
    axes[1].set_xlabel("탐지율")
    axes[1].set_title("KGCP 항목별 탐지율")
    axes[1].set_xlim(0, 1.05)

    path = FIGURES_DIR / "fig5_completeness.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


# ──────────────────────────────────────────────
# 종합 텍스트 리포트
# ──────────────────────────────────────────────

def generate_text_report(
    readability: list[dict],
    completeness: list[dict],
    comparison: list[dict],
) -> str:
    """종합 리포트 텍스트를 생성한다."""

    # 가독성 통계
    doc_grades = [r["document_level"]["grade_level"] for r in readability]
    doc_scores = [r["document_level"]["composite_score"] for r in readability]

    # 완전성 통계
    comp_scores = [r["completeness_score"] for r in completeness]
    full_count = sum(1 for s in comp_scores if s >= 1.0)

    # 비교 통계
    summaries = [r["document_summary"] for r in comparison if r["document_summary"]]
    avg_orig_grade = np.mean([s["original_avg_grade"] for s in summaries])
    avg_simp_grade = np.mean([s["simplified_avg_grade"] for s in summaries])
    avg_grade_red = np.mean([s["grade_reduction"] for s in summaries])
    avg_score_imp = np.mean([s["score_improvement"] for s in summaries])
    avg_target_rate = np.mean([s["target_achievement_rate"] for s in summaries])

    # 섹션별 난이도 (원문)
    section_grades = {}
    for r in readability:
        for sid, sec in r.get("section_level", {}).items():
            section_grades.setdefault(sid, []).append(sec["grade_level"])

    hardest = sorted(section_grades.items(), key=lambda x: -np.mean(x[1]))[:5]
    easiest = sorted(section_grades.items(), key=lambda x: np.mean(x[1]))[:5]

    report = f"""# ICF 가독성 분석 종합 리포트

## 1. 분석 개요

| 항목 | 값 |
|------|-----|
| 분석 대상 | 모의 ICF {len(readability)}건 |
| KGCP 필수항목 | 20개 |
| 분석 프레임워크 | 이독성 공식 [R1] + 전문용어 분석 [R6] + 종합 점수 |
| 평이화 모델 | GPT-4o |
| 목표 수준 | ≤ 중학교 2학년 (≤8th grade) [R5] |

## 2. 원문 가독성 분석 결과

### 2-1. 문서 수준

| 지표 | 평균 | 최소 | 최대 |
|------|------|------|------|
| 학년 수준 | {np.mean(doc_grades):.1f} | {np.min(doc_grades):.1f} | {np.max(doc_grades):.1f} |
| 종합 점수 (0-100) | {np.mean(doc_scores):.1f} | {np.min(doc_scores):.1f} | {np.max(doc_scores):.1f} |
| 난이도 | Moderate (50건 전체) | | |

- 평균 학년 수준 {np.mean(doc_grades):.1f} = **고등학교 수준**
- ICF 국제 권장 기준(≤8th grade) [R5]을 **{np.mean(doc_grades) - 8:.1f}학년 초과**
- Paasche-Orlow et al.(2003) [R5]의 미국 ICF 평균(10.6)과 유사한 패턴

### 2-2. 가장 어려운 섹션 (Top 5)

| 순위 | 섹션 | 평균 학년 |
|------|------|-----------|
"""
    for i, (sid, grades) in enumerate(hardest):
        report += f"| {i+1} | {sid} | {np.mean(grades):.1f} |\n"

    report += f"""
### 2-3. 가장 쉬운 섹션 (Top 5)

| 순위 | 섹션 | 평균 학년 |
|------|------|-----------|
"""
    for i, (sid, grades) in enumerate(easiest):
        report += f"| {i+1} | {sid} | {np.mean(grades):.1f} |\n"

    report += f"""
## 3. KGCP 완전성 분석 결과

| 지표 | 값 |
|------|-----|
| 평균 완전성 점수 | {np.mean(comp_scores):.1%} |
| 20/20 항목 완전 | {full_count}/{len(completeness)}건 ({full_count/len(completeness):.0%}) |
| 모델 | KoBERT (monologg/kobert) |
| macro F1 | 0.81 |

## 4. 평이화 결과

### 4-1. 전후 비교 요약

| 지표 | 원문 | 평이화 | 변화 |
|------|------|--------|------|
| 평균 학년 수준 | {avg_orig_grade:.1f} | {avg_simp_grade:.1f} | **↓{avg_grade_red:.1f}** |
| 종합 점수 | — | — | **+{avg_score_imp:.1f}점** |
| 목표 달성률 (≤8학년) | — | — | **{avg_target_rate:.1%}** |

### 4-2. 해석

- 평이화 후 평균 학년 수준이 {avg_orig_grade:.1f} → {avg_simp_grade:.1f}로 **{avg_grade_red:.1f}학년 감소**
- 전체 섹션의 **{avg_target_rate:.0%}** 가 ICF 국제 권장 기준(≤8학년) 도달
- 종합 가독성 점수 평균 **+{avg_score_imp:.1f}점** 향상
- 나머지 {100 - avg_target_rate*100:.0f}% 섹션은 추가 평이화 또는 구조적 개선 필요

## 5. 한계 및 향후 과제

1. **시드 사전 한계**: 기초어휘 516어, 의학용어 248어 (시드) → 국립국어원 4만 어휘 확보 시 정밀도 향상
2. **모의 데이터**: GPT-4o 생성 동의서 기반 → Phase 2에서 실제 IRB 동의서로 검증 필요
3. **평이화 품질**: 내용 보존율에 대한 전문가 평가(human evaluation) 필요
4. **한자어 비율**: MeCab Compound 태그 기반 추정 → 전용 한자어 사전 연동 시 개선
5. **KoBERT 성능**: 50건 학습 → 더 많은 데이터 확보 시 성능 향상 기대

## 6. 결론

본 연구의 Phase 1 파이프라인 검증 결과:
- 한국어 ICF의 가독성은 평균 **고등학교 수준**(학년 {np.mean(doc_grades):.1f})으로 국제 권장 기준을 초과
- GPT-4o 기반 평이화로 평균 **{avg_grade_red:.1f}학년 감소**, **{avg_target_rate:.0%} 목표 달성**
- 자동화 파이프라인(수집 → 분석 → 평이화 → 평가)의 실현 가능성 확인
- Phase 2에서 실제 동의서 데이터로 본 실험 수행 예정
"""

    return report


# ──────────────────────────────────────────────
# 메인 실행
# ──────────────────────────────────────────────

def run():
    """전체 시각화 및 리포트를 생성한다."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("데이터 로딩...")
    readability = load_readability()
    completeness = load_completeness()
    comparison = load_comparison()

    print(f"  가독성: {len(readability)}건, 완전성: {len(completeness)}건, 비교: {len(comparison)}건")

    # 시각화
    print("\n시각화 생성 중...")
    p1 = fig1_grade_distribution(readability)
    print(f"  [1/5] {p1.name}")
    p2 = fig2_section_difficulty(readability)
    print(f"  [2/5] {p2.name}")
    p3 = fig3_simplification_comparison(comparison)
    print(f"  [3/5] {p3.name}")
    p4 = fig4_score_improvement(comparison)
    print(f"  [4/5] {p4.name}")
    p5 = fig5_completeness(completeness)
    print(f"  [5/5] {p5.name}")

    # 텍스트 리포트
    print("\n종합 리포트 생성 중...")
    report_text = generate_text_report(readability, completeness, comparison)
    report_path = REPORTS_DIR / "final_report.md"
    report_path.write_text(report_text, encoding="utf-8")
    print(f"  {report_path.name}")

    print(f"\n완료!")
    print(f"  시각화: {FIGURES_DIR}/ (5개 파일)")
    print(f"  리포트: {report_path}")


if __name__ == "__main__":
    run()
