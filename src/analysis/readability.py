"""한국어 임상시험 동의서(ICF) 가독성 분석 모듈

프레임워크 구조:
  전처리 (MeCab-ko + kss)
    → A. 문장 지표 (평균/최장 문장길이, 절 수)
    → B. 어휘 지표 (쉬운 단어 비율, 한자어 비율, TTR, 형태소 수)
    → C. 전문용어 분석 (사전 매칭 + MedReadMe 4단계)
    → 이독성 공식 [R1] (학년 수준)
    → 종합 점수 (0-100) → 난이도 등급

근거 연구:
  [R1] 이순영(2017) 이독성 공식
  [R2] 최임순 외(2016) ICF 가독성 평가
  [R4] 국립국어원(2023) 기초어휘
  [R5] Paasche-Orlow(2003) ICF readability
  [R6] Jiang et al.(2024) MedReadMe
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import MeCab
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "configs" / "config.yaml"
DICT_DIR = PROJECT_ROOT / "data" / "dictionaries"

MECAB_ARGS = "-r /opt/homebrew/etc/mecabrc -d /opt/homebrew/lib/mecab/dic/mecab-ko-dic"

with open(CONFIG_PATH, encoding="utf-8") as _f:
    CONFIG = yaml.safe_load(_f)

_RC = CONFIG["readability"]


# ──────────────────────────────────────────────
# 데이터 클래스
# ──────────────────────────────────────────────

@dataclass
class MorphToken:
    """형태소 분석 결과 토큰"""
    surface: str       # 표면형
    pos: str           # 품사 태그 (NNG, NNP, JKS, ...)
    reading: str = ""  # 읽기
    detail: str = ""   # MeCab 상세 정보


@dataclass
class SentenceMetrics:
    """A. 문장 수준 지표"""
    avg_sentence_length: float = 0.0     # 문장당 평균 어절 수
    max_sentence_length: int = 0         # 최장 문장 어절 수
    avg_clause_count: float = 0.0        # 문장당 평균 절 수


@dataclass
class VocabularyMetrics:
    """B. 어휘 수준 지표"""
    easy_word_ratio: float = 0.0         # 쉬운 단어 비율 (기초어휘 1-2등급)
    sino_korean_ratio: float = 0.0       # 한자어 비율
    type_token_ratio: float = 0.0        # TTR
    avg_morphemes_per_word: float = 0.0  # 어절당 평균 형태소 수
    passive_causative_ratio: float = 0.0 # 피동·사동 비율


@dataclass
class JargonMetrics:
    """C. 전문용어 분석 지표"""
    tech_term_ratio: float = 0.0         # 전문용어 비율
    jargon_span_count: int = 0           # 전문용어 span 수
    hard_jargon_ratio: float = 0.0       # Google-Hard 비율
    abbreviation_count: int = 0          # 미설명 약어 수
    jargon_density: float = 0.0          # 문장당 평균 전문용어 수


@dataclass
class DocumentMetrics:
    """문서 수준 지표"""
    total_sentences: int = 0
    total_words: int = 0
    total_chars: int = 0


@dataclass
class ReadabilityResult:
    """가독성 분석 결과"""
    grade_level: float = 0.0             # 이독성 공식 학년 수준
    composite_score: float = 0.0         # 종합 점수 (0-100)
    difficulty: str = ""                 # Easy / Moderate / Difficult
    sentence: SentenceMetrics = field(default_factory=SentenceMetrics)
    vocabulary: VocabularyMetrics = field(default_factory=VocabularyMetrics)
    jargon: JargonMetrics = field(default_factory=JargonMetrics)
    document: DocumentMetrics = field(default_factory=DocumentMetrics)

    def to_dict(self) -> dict:
        return {
            "grade_level": round(self.grade_level, 2),
            "composite_score": round(self.composite_score, 1),
            "difficulty": self.difficulty,
            "metrics": {
                "avg_sentence_length": round(self.sentence.avg_sentence_length, 2),
                "max_sentence_length": self.sentence.max_sentence_length,
                "avg_clause_count": round(self.sentence.avg_clause_count, 2),
                "easy_word_ratio": round(self.vocabulary.easy_word_ratio, 4),
                "sino_korean_ratio": round(self.vocabulary.sino_korean_ratio, 4),
                "ttr": round(self.vocabulary.type_token_ratio, 4),
                "avg_morphemes_per_word": round(self.vocabulary.avg_morphemes_per_word, 2),
                "passive_causative_ratio": round(self.vocabulary.passive_causative_ratio, 4),
                "tech_term_ratio": round(self.jargon.tech_term_ratio, 4),
                "jargon_span_count": self.jargon.jargon_span_count,
                "hard_jargon_ratio": round(self.jargon.hard_jargon_ratio, 4),
                "abbreviation_count": self.jargon.abbreviation_count,
                "jargon_density": round(self.jargon.jargon_density, 2),
                "total_sentences": self.document.total_sentences,
                "total_words": self.document.total_words,
                "total_chars": self.document.total_chars,
            },
        }


# ──────────────────────────────────────────────
# 사전 로더
# ──────────────────────────────────────────────

class DictionaryLoader:
    """기초어휘 및 의학용어 사전을 로드한다."""

    def __init__(self, dict_dir: Path = DICT_DIR):
        self.easy_words: dict[str, int] = {}      # 어휘 → 등급
        self.medical_terms: dict[str, str] = {}    # 용어 → 난이도
        self._load_easy_words(dict_dir / "easy_words.txt")
        self._load_medical_terms(dict_dir / "medical_terms.txt")

    def _load_easy_words(self, path: Path) -> None:
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            word = parts[0]
            grade = int(parts[1]) if len(parts) > 1 else 1
            self.easy_words[word] = grade

    def _load_medical_terms(self, path: Path) -> None:
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            term = parts[0]
            level = parts[1] if len(parts) > 1 else "G-Hard"
            self.medical_terms[term] = level

    def is_easy_word(self, lemma: str) -> bool:
        """기초어휘 1-2등급에 해당하면 True"""
        return self.easy_words.get(lemma, 99) <= 2

    def get_medical_level(self, text: str) -> str | None:
        """의학용어 사전에서 난이도를 반환한다. 없으면 None."""
        return self.medical_terms.get(text)


# ──────────────────────────────────────────────
# 전처리 (MeCab-ko + kss)
# ──────────────────────────────────────────────

class KoreanPreprocessor:
    """MeCab-ko 기반 형태소 분석 + kss 문장 분리"""

    # 피동·사동 접미사 패턴 (-이/히/리/기/우/추/이키 등)
    PASSIVE_CAUSATIVE_SUFFIXES = re.compile(
        r"(이|히|리|기|우|추|이키|시키)(다|어|아|었|겠|ㄴ|는|ㄹ)?$"
    )

    # 절(clause) 경계 표지: 연결어미(EC), 전성어미(ETN, ETM)
    CLAUSE_POS = {"EC", "ETN", "ETM"}

    def __init__(self):
        self.tagger = MeCab.Tagger(MECAB_ARGS)

    # 문장 종결 패턴: 마침표/물음표/느낌표 + 공백 또는 줄바꿈
    _SENT_SPLIT = re.compile(r"(?<=[.?!。])\s+")

    def split_sentences(self, text: str) -> list[str]:
        """텍스트를 문장 단위로 분리한다 (정규식 기반)."""
        text = self._clean_text(text)
        if not text.strip():
            return []
        # 줄바꿈도 문장 경계로 활용
        text = re.sub(r"\n+", "\n", text)
        parts = []
        for paragraph in text.split("\n"):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            sents = self._SENT_SPLIT.split(paragraph)
            parts.extend(s.strip() for s in sents if s.strip())
        return parts

    def tokenize(self, text: str) -> list[MorphToken]:
        """텍스트를 형태소 분석하여 토큰 리스트로 반환한다."""
        parsed = self.tagger.parse(text)
        tokens = []
        for line in parsed.splitlines():
            if line == "EOS" or line == "":
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            surface = parts[0]
            features = parts[1].split(",")
            pos = features[0] if features else "UNK"
            reading = features[7] if len(features) > 7 else ""
            tokens.append(MorphToken(
                surface=surface,
                pos=pos,
                reading=reading,
                detail=parts[1],
            ))
        return tokens

    def get_eojeols(self, text: str) -> list[str]:
        """텍스트를 어절(띄어쓰기 단위)로 분리한다."""
        return [w for w in text.split() if w.strip()]

    @staticmethod
    def _clean_text(text: str) -> str:
        """마크다운 헤더, 표 구분선 등 비텍스트 요소를 정리한다."""
        lines = []
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if re.match(r"^\|[-:| ]+\|$", stripped):
                continue
            if stripped.startswith("|") and stripped.endswith("|"):
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                lines.append(" ".join(cells))
                continue
            if stripped:
                lines.append(stripped)
        return "\n".join(lines)

    def count_clauses(self, tokens: list[MorphToken]) -> int:
        """토큰 리스트에서 절(clause) 수를 추정한다.
        연결어미(EC), 전성어미(ETN/ETM) 개수 + 1 (주절)
        """
        clause_markers = sum(1 for t in tokens if t.pos in self.CLAUSE_POS)
        return clause_markers + 1

    def is_passive_causative(self, token: MorphToken) -> bool:
        """피동·사동 표현 포함 여부를 판단한다."""
        if token.pos.startswith("VV") or token.pos.startswith("XSV"):
            return bool(self.PASSIVE_CAUSATIVE_SUFFIXES.search(token.surface))
        return False


# ──────────────────────────────────────────────
# 한자어 판별
# ──────────────────────────────────────────────

def is_sino_korean(token: MorphToken) -> bool:
    """MeCab 상세 정보에서 한자어 여부를 추정한다.
    - NNG(일반명사), NNP(고유명사) 중 한자 읽기가 있는 경우
    - 또는 유니코드 CJK 범위의 문자가 포함된 경우
    """
    if token.pos not in ("NNG", "NNP"):
        return False
    # MeCab-ko 상세 정보에서 한자 정보 확인 (Compound 분석)
    if "Compound" in token.detail:
        return True
    # 표면형에 한자가 직접 포함된 경우
    for ch in token.surface:
        if "\u4e00" <= ch <= "\u9fff":
            return True
    # 2음절 이상 NNG에서 한자어 추정 (heuristic)
    # MeCab-ko의 Compound 태그가 없으면 보수적으로 False
    return False


# ──────────────────────────────────────────────
# 전문용어 매칭
# ──────────────────────────────────────────────

class JargonMatcher:
    """의학 전문용어를 텍스트에서 매칭하고 난이도를 분류한다."""

    # 영문 약어 패턴 (2글자 이상 대문자 또는 대문자+숫자 조합)
    ABBREV_PATTERN = re.compile(r"\b[A-Z][A-Za-z0-9]{1,10}\b")

    def __init__(self, dictionary: DictionaryLoader):
        self.dict = dictionary
        # 긴 용어부터 매칭 (greedy)
        self._sorted_terms = sorted(
            self.dict.medical_terms.keys(), key=len, reverse=True
        )

    def find_jargon_spans(self, text: str) -> list[tuple[str, str]]:
        """텍스트에서 전문용어 span을 찾아 (용어, 난이도) 리스트를 반환한다."""
        found = []
        remaining = text

        # 1) 사전 기반 매칭 (긴 용어 우선)
        matched_positions = set()
        for term in self._sorted_terms:
            start = 0
            while True:
                idx = remaining.find(term, start)
                if idx < 0:
                    break
                pos_range = range(idx, idx + len(term))
                if not any(p in matched_positions for p in pos_range):
                    level = self.dict.medical_terms[term]
                    found.append((term, level))
                    matched_positions.update(pos_range)
                start = idx + 1

        # 2) 영문 약어 추가 탐지 (사전에 없는 것도)
        for m in self.ABBREV_PATTERN.finditer(text):
            abbrev = m.group()
            pos_range = range(m.start(), m.end())
            if any(p in matched_positions for p in pos_range):
                continue
            dict_level = self.dict.get_medical_level(abbrev)
            if dict_level:
                found.append((abbrev, dict_level))
            elif len(abbrev) >= 2 and abbrev.isupper():
                found.append((abbrev, "Abbrev"))
            matched_positions.update(pos_range)

        return found


# ──────────────────────────────────────────────
# 가독성 분석기 (메인)
# ──────────────────────────────────────────────

class ReadabilityAnalyzer:
    """한국어 ICF 가독성 분석기

    사용법:
        analyzer = ReadabilityAnalyzer()
        result = analyzer.analyze(text)
        print(result.to_dict())
    """

    def __init__(self, dict_dir: Path = DICT_DIR):
        self.preprocessor = KoreanPreprocessor()
        self.dictionary = DictionaryLoader(dict_dir)
        self.jargon_matcher = JargonMatcher(self.dictionary)

        # config에서 이독성 공식 계수 로드
        formula = _RC["korean_readability_formula"]
        self._intercept = formula["intercept"]
        self._coeff_sl = formula["coeff_sentence_length"]
        self._coeff_ew = formula["coeff_easy_word_ratio"]

        # 종합 점수 가중치
        self._weights = _RC["composite_weights"]

    def analyze(self, text: str) -> ReadabilityResult:
        """텍스트의 가독성을 분석하여 ReadabilityResult를 반환한다."""
        result = ReadabilityResult()

        # 전처리
        sentences = self.preprocessor.split_sentences(text)
        if not sentences:
            return result

        all_tokens = self.preprocessor.tokenize(text)
        eojeols = self.preprocessor.get_eojeols(
            self.preprocessor._clean_text(text)
        )

        # 문서 지표
        result.document.total_sentences = len(sentences)
        result.document.total_words = len(eojeols)
        result.document.total_chars = len(text.replace(" ", "").replace("\n", ""))

        # A. 문장 지표
        result.sentence = self._compute_sentence_metrics(sentences)

        # B. 어휘 지표
        result.vocabulary = self._compute_vocabulary_metrics(all_tokens, eojeols)

        # C. 전문용어 분석
        result.jargon = self._compute_jargon_metrics(text, eojeols, sentences)

        # 이독성 공식 [R1]
        result.grade_level = self._compute_grade_level(
            result.sentence.avg_sentence_length,
            result.vocabulary.easy_word_ratio,
        )

        # 종합 점수 및 등급
        result.composite_score = self._compute_composite_score(result)
        result.difficulty = self._judge_difficulty(result.composite_score)

        return result

    # ── A. 문장 수준 지표 ──

    def _compute_sentence_metrics(self, sentences: list[str]) -> SentenceMetrics:
        metrics = SentenceMetrics()
        if not sentences:
            return metrics

        sent_lengths = []
        clause_counts = []

        for sent in sentences:
            words = self.preprocessor.get_eojeols(sent)
            sent_lengths.append(len(words))

            tokens = self.preprocessor.tokenize(sent)
            clause_counts.append(self.preprocessor.count_clauses(tokens))

        metrics.avg_sentence_length = sum(sent_lengths) / len(sent_lengths)
        metrics.max_sentence_length = max(sent_lengths) if sent_lengths else 0
        metrics.avg_clause_count = sum(clause_counts) / len(clause_counts)

        return metrics

    # ── B. 어휘 수준 지표 ──

    def _compute_vocabulary_metrics(
        self, tokens: list[MorphToken], eojeols: list[str]
    ) -> VocabularyMetrics:
        metrics = VocabularyMetrics()
        if not tokens or not eojeols:
            return metrics

        # 내용어 추출 (명사, 동사, 형용사, 부사)
        content_pos = {"NNG", "NNP", "NNB", "VV", "VA", "MAG", "MAJ"}
        content_tokens = [t for t in tokens if t.pos in content_pos]

        if not content_tokens:
            return metrics

        # 쉬운 단어 비율 [R1, R4]
        easy_count = sum(
            1 for t in content_tokens
            if self.dictionary.is_easy_word(t.surface)
        )
        metrics.easy_word_ratio = easy_count / len(content_tokens)

        # 한자어 비율 [R2]
        sino_count = sum(1 for t in content_tokens if is_sino_korean(t))
        metrics.sino_korean_ratio = sino_count / len(content_tokens)

        # TTR (어휘 다양성)
        all_surfaces = [t.surface for t in content_tokens]
        metrics.type_token_ratio = len(set(all_surfaces)) / len(all_surfaces)

        # 어절당 평균 형태소 수
        total_morphemes = len(tokens)
        metrics.avg_morphemes_per_word = total_morphemes / len(eojeols) if eojeols else 0

        # 피동·사동 비율
        pc_count = sum(
            1 for t in tokens if self.preprocessor.is_passive_causative(t)
        )
        metrics.passive_causative_ratio = pc_count / len(eojeols) if eojeols else 0

        return metrics

    # ── C. 전문용어 분석 [R2, R6] ──

    def _compute_jargon_metrics(
        self, text: str, eojeols: list[str], sentences: list[str]
    ) -> JargonMetrics:
        metrics = JargonMetrics()
        if not eojeols:
            return metrics

        spans = self.jargon_matcher.find_jargon_spans(text)
        metrics.jargon_span_count = len(spans)
        metrics.tech_term_ratio = len(spans) / len(eojeols) if eojeols else 0

        if spans:
            levels = Counter(level for _, level in spans)
            hard_count = levels.get("G-Hard", 0)
            metrics.hard_jargon_ratio = hard_count / len(spans)
            metrics.abbreviation_count = levels.get("Abbrev", 0)

        metrics.jargon_density = (
            len(spans) / len(sentences) if sentences else 0
        )

        return metrics

    # ── 이독성 공식 [R1] ──

    def _compute_grade_level(
        self, avg_sentence_length: float, easy_word_ratio: float
    ) -> float:
        """학년 수준 = 4.874 + (0.591 × 평균 문장 길이) − (9.201 × 쉬운 단어 비율)"""
        return (
            self._intercept
            + self._coeff_sl * avg_sentence_length
            + self._coeff_ew * easy_word_ratio
        )

    # ── 종합 점수 (0-100) ──

    def _compute_composite_score(self, result: ReadabilityResult) -> float:
        """가중합 → 0-100 정규화. 높을수록 읽기 쉬움."""
        # 각 지표를 0-1 스케일로 정규화
        # 학년 수준: 6(쉬움) ~ 18(어려움) → 역변환
        grade_norm = 1.0 - _clamp((result.grade_level - 6) / 12, 0, 1)

        # 쉬운 단어 비율: 0 ~ 1 → 정변환
        easy_norm = _clamp(result.vocabulary.easy_word_ratio, 0, 1)

        # 평균 문장 길이: 10(쉬움) ~ 35(어려움) → 역변환
        sl_norm = 1.0 - _clamp(
            (result.sentence.avg_sentence_length - 10) / 25, 0, 1
        )

        # 전문용어 비율: 0(쉬움) ~ 0.20(어려움) → 역변환
        tech_norm = 1.0 - _clamp(result.jargon.tech_term_ratio / 0.20, 0, 1)

        # 한자어 비율: 0(쉬움) ~ 0.60(어려움) → 역변환
        sino_norm = 1.0 - _clamp(result.vocabulary.sino_korean_ratio / 0.60, 0, 1)

        score = (
            self._weights["korean_readability_grade"] * grade_norm
            + self._weights["easy_word_ratio"] * easy_norm
            + self._weights["avg_sentence_length"] * sl_norm
            + self._weights["technical_term_ratio"] * tech_norm
            + self._weights["sino_korean_ratio"] * sino_norm
        ) * 100

        return round(_clamp(score, 0, 100), 1)

    @staticmethod
    def _judge_difficulty(score: float) -> str:
        if score >= 70:
            return "Easy"
        elif score >= 40:
            return "Moderate"
        else:
            return "Difficult"


# ──────────────────────────────────────────────
# 유틸리티
# ──────────────────────────────────────────────

def _clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, value))


# ──────────────────────────────────────────────
# ICF 파일 분석 (배치)
# ──────────────────────────────────────────────

def analyze_icf_file(path: Path) -> dict:
    """모의 ICF JSON 파일 1건을 분석하여 결과를 반환한다."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    analyzer = ReadabilityAnalyzer()

    # 문서 전체 분석
    full_text = data.get("full_text", "")
    doc_result = analyzer.analyze(full_text)

    # 섹션별 분석
    sections = data.get("sections", {})
    section_results = {}
    for section_id, section_text in sections.items():
        if section_text.strip():
            sec_result = analyzer.analyze(section_text)
            section_results[section_id] = sec_result.to_dict()

    return {
        "trial_id": data.get("trial_id", ""),
        "document_level": doc_result.to_dict(),
        "section_level": section_results,
        "num_sections_analyzed": len(section_results),
    }


def analyze_all_icfs(
    input_dir: Path | None = None,
    output_path: Path | None = None,
) -> list[dict]:
    """모의 ICF 전체를 배치 분석한다."""
    if input_dir is None:
        input_dir = PROJECT_ROOT / "data" / "raw" / "mock_icf"
    if output_path is None:
        output_path = PROJECT_ROOT / "data" / "processed" / "readability_results.json"

    icf_files = sorted(input_dir.glob("*.json"))
    print(f"분석 대상: {len(icf_files)}건")

    results = []
    for i, fpath in enumerate(icf_files):
        trial_id = fpath.stem
        print(f"  [{i+1}/{len(icf_files)}] {trial_id} 분석 중... ", end="", flush=True)
        try:
            result = analyze_icf_file(fpath)
            results.append(result)
            score = result["document_level"]["composite_score"]
            grade = result["document_level"]["grade_level"]
            diff = result["document_level"]["difficulty"]
            print(f"완료 (학년 {grade}, 점수 {score}, {diff})")
        except Exception as e:
            print(f"실패: {e}")

    # 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n저장 완료: {output_path} ({len(results)}건)")

    # 요약 통계
    if results:
        scores = [r["document_level"]["composite_score"] for r in results]
        grades = [r["document_level"]["grade_level"] for r in results]
        diffs = Counter(r["document_level"]["difficulty"] for r in results)
        print(f"\n=== 요약 통계 ===")
        print(f"종합 점수: 평균 {sum(scores)/len(scores):.1f} (범위 {min(scores):.1f} ~ {max(scores):.1f})")
        print(f"학년 수준: 평균 {sum(grades)/len(grades):.1f} (범위 {min(grades):.1f} ~ {max(grades):.1f})")
        print(f"난이도 분포: {dict(diffs)}")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ICF 가독성 분석")
    parser.add_argument("--single", type=str, help="단일 ICF 파일 분석")
    parser.add_argument("--all", action="store_true", help="전체 ICF 배치 분석")
    args = parser.parse_args()

    if args.single:
        result = analyze_icf_file(Path(args.single))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.all:
        analyze_all_icfs()
    else:
        parser.print_help()
