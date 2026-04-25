"""평이화 전후 가독성 비교 분석 모듈

원문과 평이화 텍스트의 가독성 지표를 비교하여
평이화 효과를 정량적으로 평가한다.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from src.analysis.readability import ReadabilityAnalyzer

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SIMPLIFIED_DIR = PROJECT_ROOT / "data" / "processed" / "simplified_icf"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "comparison_results.json"


def compare_single(simplified_path: Path) -> dict:
    """평이화 결과 1건의 전후 비교를 수행한다."""
    with open(simplified_path, encoding="utf-8") as f:
        data = json.load(f)

    analyzer = ReadabilityAnalyzer()
    trial_id = data["trial_id"]
    sections_orig = data.get("sections_original", {})
    sections_simp = data.get("sections_simplified", {})

    section_comparisons = {}

    for sid in sections_orig:
        if sid not in sections_simp:
            continue
        orig_text = sections_orig[sid]
        simp_text = sections_simp[sid]

        if not orig_text.strip() or not simp_text.strip():
            continue

        orig_result = analyzer.analyze(orig_text)
        simp_result = analyzer.analyze(simp_text)

        section_comparisons[sid] = {
            "original": {
                "grade_level": round(orig_result.grade_level, 2),
                "composite_score": round(orig_result.composite_score, 1),
                "difficulty": orig_result.difficulty,
                "avg_sentence_length": round(orig_result.sentence.avg_sentence_length, 2),
                "easy_word_ratio": round(orig_result.vocabulary.easy_word_ratio, 4),
                "tech_term_ratio": round(orig_result.jargon.tech_term_ratio, 4),
            },
            "simplified": {
                "grade_level": round(simp_result.grade_level, 2),
                "composite_score": round(simp_result.composite_score, 1),
                "difficulty": simp_result.difficulty,
                "avg_sentence_length": round(simp_result.sentence.avg_sentence_length, 2),
                "easy_word_ratio": round(simp_result.vocabulary.easy_word_ratio, 4),
                "tech_term_ratio": round(simp_result.jargon.tech_term_ratio, 4),
            },
            "delta": {
                "grade_level": round(simp_result.grade_level - orig_result.grade_level, 2),
                "composite_score": round(simp_result.composite_score - orig_result.composite_score, 1),
                "avg_sentence_length": round(
                    simp_result.sentence.avg_sentence_length - orig_result.sentence.avg_sentence_length, 2
                ),
                "easy_word_ratio": round(
                    simp_result.vocabulary.easy_word_ratio - orig_result.vocabulary.easy_word_ratio, 4
                ),
                "tech_term_ratio": round(
                    simp_result.jargon.tech_term_ratio - orig_result.jargon.tech_term_ratio, 4
                ),
            },
        }

    # 문서 수준 집계
    if section_comparisons:
        orig_grades = [v["original"]["grade_level"] for v in section_comparisons.values()]
        simp_grades = [v["simplified"]["grade_level"] for v in section_comparisons.values()]
        orig_scores = [v["original"]["composite_score"] for v in section_comparisons.values()]
        simp_scores = [v["simplified"]["composite_score"] for v in section_comparisons.values()]

        n = len(orig_grades)
        doc_summary = {
            "num_sections_compared": n,
            "original_avg_grade": round(sum(orig_grades) / n, 2),
            "simplified_avg_grade": round(sum(simp_grades) / n, 2),
            "grade_reduction": round(
                (sum(orig_grades) - sum(simp_grades)) / n, 2
            ),
            "original_avg_score": round(sum(orig_scores) / n, 1),
            "simplified_avg_score": round(sum(simp_scores) / n, 1),
            "score_improvement": round(
                (sum(simp_scores) - sum(orig_scores)) / n, 1
            ),
            "sections_reaching_target": sum(
                1 for g in simp_grades if g <= 8.0
            ),
            "target_achievement_rate": round(
                sum(1 for g in simp_grades if g <= 8.0) / n, 4
            ),
        }
    else:
        doc_summary = {}

    return {
        "trial_id": trial_id,
        "document_summary": doc_summary,
        "section_comparisons": section_comparisons,
    }


def compare_all(
    simplified_dir: Path = SIMPLIFIED_DIR,
    output_path: Path = OUTPUT_PATH,
) -> list[dict]:
    """전체 평이화 결과를 비교 분석한다."""
    files = sorted(simplified_dir.glob("*.json"))
    print(f"비교 분석 대상: {len(files)}건")

    results = []
    for i, fpath in enumerate(files):
        print(f"  [{i+1}/{len(files)}] {fpath.stem} 비교 중... ", end="", flush=True)
        try:
            result = compare_single(fpath)
            results.append(result)
            summary = result["document_summary"]
            if summary:
                grade_red = summary["grade_reduction"]
                score_imp = summary["score_improvement"]
                target_rate = summary["target_achievement_rate"]
                print(
                    f"완료 (학년 -{grade_red:.1f}, 점수 +{score_imp:.1f}, "
                    f"목표달성 {target_rate:.0%})"
                )
            else:
                print("완료 (비교 섹션 없음)")
        except Exception as e:
            print(f"실패: {e}")

    # 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 전체 요약
    if results:
        all_summaries = [r["document_summary"] for r in results if r["document_summary"]]
        if all_summaries:
            avg_grade_red = sum(s["grade_reduction"] for s in all_summaries) / len(all_summaries)
            avg_score_imp = sum(s["score_improvement"] for s in all_summaries) / len(all_summaries)
            avg_target = sum(s["target_achievement_rate"] for s in all_summaries) / len(all_summaries)
            avg_orig_grade = sum(s["original_avg_grade"] for s in all_summaries) / len(all_summaries)
            avg_simp_grade = sum(s["simplified_avg_grade"] for s in all_summaries) / len(all_summaries)

            print(f"\n{'='*60}")
            print(f"전체 요약 ({len(all_summaries)}건)")
            print(f"{'='*60}")
            print(f"평균 학년 수준:  원문 {avg_orig_grade:.1f} → 평이화 {avg_simp_grade:.1f} (↓{avg_grade_red:.1f})")
            print(f"평균 종합 점수:  +{avg_score_imp:.1f}점 향상")
            print(f"목표 달성률 (≤8학년):  {avg_target:.1%}")
            print(f"{'='*60}")

    print(f"\n저장 완료: {output_path}")
    return results


if __name__ == "__main__":
    compare_all()
