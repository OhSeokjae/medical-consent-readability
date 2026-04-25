"""발표용 PPT 생성 스크립트"""

from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"
OUTPUT_PATH = PROJECT_ROOT / "outputs" / "reports" / "presentation.pptx"

# 색상 팔레트
PRIMARY = RGBColor(0x2C, 0x3E, 0x50)    # 짙은 남색
ACCENT = RGBColor(0x27, 0xAE, 0x60)     # 초록
RED = RGBColor(0xE7, 0x4C, 0x3C)        # 빨강
BLUE = RGBColor(0x34, 0x98, 0xDB)       # 파랑
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GRAY = RGBColor(0x7F, 0x8C, 0x8D)
LIGHT_BG = RGBColor(0xEC, 0xF0, 0xF1)


def set_slide_bg(slide, color):
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_text_box(slide, left, top, width, height, text,
                 font_size=18, bold=False, color=PRIMARY, alignment=PP_ALIGN.LEFT,
                 font_name="Apple SD Gothic Neo"):
    txBox = slide.shapes.add_textbox(Inches(left), Inches(top),
                                      Inches(width), Inches(height))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.bold = bold
    p.font.color.rgb = color
    p.font.name = font_name
    p.alignment = alignment
    return txBox


def add_bullet_slide(slide, items, left=0.8, top=2.0, font_size=16):
    """글머리 기호 목록 추가"""
    txBox = slide.shapes.add_textbox(
        Inches(left), Inches(top), Inches(8.4), Inches(4.5)
    )
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = item
        p.font.size = Pt(font_size)
        p.font.color.rgb = PRIMARY
        p.font.name = "Apple SD Gothic Neo"
        p.space_after = Pt(8)
        p.level = 0


def add_table(slide, rows, cols, data, left=0.8, top=2.2, width=8.4, row_height=0.45):
    """표 추가"""
    table_shape = slide.shapes.add_table(
        rows, cols,
        Inches(left), Inches(top),
        Inches(width), Inches(row_height * rows)
    )
    table = table_shape.table

    for r in range(rows):
        for c in range(cols):
            cell = table.cell(r, c)
            cell.text = str(data[r][c])
            for paragraph in cell.text_frame.paragraphs:
                paragraph.font.size = Pt(12)
                paragraph.font.name = "Apple SD Gothic Neo"
                if r == 0:
                    paragraph.font.bold = True
                    paragraph.font.color.rgb = WHITE
                else:
                    paragraph.font.color.rgb = PRIMARY

            if r == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = PRIMARY
            elif r % 2 == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = LIGHT_BG

    return table_shape


def create_presentation():
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)

    # ════════════════════════════════════════
    # Slide 1: 표지
    # ════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank
    set_slide_bg(slide, PRIMARY)

    add_text_box(slide, 0.8, 1.5, 8.4, 1.5,
                 "한국어 임상시험 동의서의\n가독성 자동 평가 및 AI 기반 평이화",
                 font_size=32, bold=True, color=WHITE, alignment=PP_ALIGN.CENTER)

    add_text_box(slide, 0.8, 3.5, 8.4, 0.8,
                 "Automated Readability Assessment and AI-based Simplification\nfor Korean Informed Consent Forms",
                 font_size=16, color=RGBColor(0xBD, 0xC3, 0xC7), alignment=PP_ALIGN.CENTER)

    add_text_box(slide, 0.8, 5.5, 8.4, 0.5,
                 "Phase 1: 파이프라인 구축 및 검증",
                 font_size=18, color=ACCENT, alignment=PP_ALIGN.CENTER)

    # ════════════════════════════════════════
    # Slide 2: 연구 배경
    # ════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_text_box(slide, 0.8, 0.4, 8.4, 0.7, "연구 배경",
                 font_size=28, bold=True, color=PRIMARY)

    items = [
        "임상시험 동의서(ICF)는 참여자의 자기결정권 보장의 핵심 문서",
        "미국 ICF 평균 가독성: 10.6학년 — 권장 기준(≤8학년) 초과 [Paasche-Orlow, NEJM 2003]",
        "국내 ICF: 평이한 어휘 12% 부족, 전문용어 4.5% 과다 [최임순 외, 2016]",
        "참여자가 기본 개념(무작위배정, 위약)을 충분히 이해하지 못함 [Park et al., 2019]",
        "",
        "문제: 한국어 ICF의 가독성을 정량적으로 평가하고",
        "        자동으로 개선하는 체계적 연구가 부족",
    ]
    add_bullet_slide(slide, items, font_size=16)

    # ════════════════════════════════════════
    # Slide 3: 연구 목적
    # ════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_text_box(slide, 0.8, 0.4, 8.4, 0.7, "연구 목적",
                 font_size=28, bold=True, color=PRIMARY)

    items = [
        "1. 한국어 이독성 공식 기반 ICF 가독성 자동 측정 프레임워크 개발",
        "2. 의학 전문용어 난이도 세분화 분석 (MedReadMe 방법론 차용)",
        "3. KGCP 20개 필수항목 완전성 자동 평가 (KoBERT)",
        "4. GPT-4o 기반 동의서 평이화 및 효과 검증",
        "",
        "목표: 수집 → 분석 → 평이화 → 평가 end-to-end 파이프라인",
    ]
    add_bullet_slide(slide, items, font_size=16)

    # ════════════════════════════════════════
    # Slide 4: 파이프라인 개요
    # ════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_text_box(slide, 0.8, 0.4, 8.4, 0.7, "전체 파이프라인",
                 font_size=28, bold=True, color=PRIMARY)

    steps = [
        ("Step 1", "CRIS 데이터 수집", "공공데이터 API\n중재연구 8,785건"),
        ("Step 2", "모의 ICF 생성", "GPT-4o 배치 분할\n50건, 평균 10,912자"),
        ("Step 3", "가독성 분석", "이독성 공식 + 전문용어\n종합 점수 (0-100)"),
        ("Step 4", "완전성 분류", "KoBERT multi-label\nF1 = 0.81"),
        ("Step 5", "평이화", "GPT-4o\n학년 11.0 → 7.1"),
        ("Step 6", "평가 리포트", "시각화 + 종합 보고서"),
    ]

    for i, (step, title, desc) in enumerate(steps):
        left = 0.5 + i * 1.55
        top = 1.8

        # 박스
        shape = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(left), Inches(top), Inches(1.4), Inches(4.0)
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = PRIMARY if i % 2 == 0 else ACCENT
        shape.line.fill.background()

        # 텍스트
        tf = shape.text_frame
        tf.word_wrap = True
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER

        p = tf.paragraphs[0]
        p.text = step
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = WHITE
        p.font.name = "Apple SD Gothic Neo"

        p2 = tf.add_paragraph()
        p2.text = "\n" + title
        p2.font.size = Pt(12)
        p2.font.bold = True
        p2.font.color.rgb = WHITE
        p2.font.name = "Apple SD Gothic Neo"
        p2.alignment = PP_ALIGN.CENTER

        p3 = tf.add_paragraph()
        p3.text = "\n" + desc
        p3.font.size = Pt(9)
        p3.font.color.rgb = RGBColor(0xEC, 0xF0, 0xF1)
        p3.font.name = "Apple SD Gothic Neo"
        p3.alignment = PP_ALIGN.CENTER

    # ════════════════════════════════════════
    # Slide 5: 가독성 프레임워크
    # ════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_text_box(slide, 0.8, 0.4, 8.4, 0.7, "가독성 평가 프레임워크",
                 font_size=28, bold=True, color=PRIMARY)

    items = [
        "이독성 공식 [이순영, 2017]:",
        "  학년 수준 = 4.874 + 0.591 × 평균 문장 길이 − 9.201 × 쉬운 단어 비율",
        "",
        "개별 지표 (3개 레이어):",
        "  A. 문장 지표: 평균/최장 문장 길이, 절 수 (MeCab-ko)",
        "  B. 어휘 지표: 쉬운 단어 비율 (국립국어원 기초어휘), 한자어 비율, TTR",
        "  C. 전문용어: 사전 매칭 + MedReadMe 4단계 세분화",
        "",
        "종합 점수 (0-100, 높을수록 쉬움):",
        "  학년 수준 30% + 쉬운 단어 25% + 문장 길이 20% + 전문용어 15% + 한자어 10%",
        "",
        "등급: Easy (≤중2, 70-100) | Moderate (고교, 40-69) | Difficult (대학+, 0-39)",
    ]
    add_bullet_slide(slide, items, font_size=14)

    # ════════════════════════════════════════
    # Slide 6: 원문 가독성 결과 (표)
    # ════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_text_box(slide, 0.8, 0.4, 8.4, 0.7, "결과 1: 원문 ICF 가독성 (N=50)",
                 font_size=28, bold=True, color=PRIMARY)

    data = [
        ["지표", "M", "SD", "Range"],
        ["이독성 공식 학년 수준", "10.05", "0.51", "8.7 – 11.3"],
        ["종합 가독성 점수", "64.38", "1.89", "60.2 – 68.5"],
        ["평균 문장 길이 (어절)", "12.94", "0.84", "—"],
        ["쉬운 단어 비율", "0.269", "0.015", "—"],
        ["전문용어 비율", "0.049", "0.010", "—"],
        ["한자어 비율", "0.069", "0.009", "—"],
    ]
    add_table(slide, len(data), 4, data, top=1.5)

    add_text_box(slide, 0.8, 5.2, 8.4, 1.5,
                 "• 50건 전체 Moderate(고교 수준) — ICF 권장 기준(≤8학년) 평균 2.05학년 초과\n"
                 "• Paasche-Orlow(2003)의 미국 ICF 평균(10.6학년)과 유사한 패턴",
                 font_size=14, color=GRAY)

    # ════════════════════════════════════════
    # Slide 7: 가독성 분포 (Figure 1)
    # ════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_text_box(slide, 0.8, 0.4, 8.4, 0.7, "결과 2: 원문 ICF 가독성 분포",
                 font_size=28, bold=True, color=PRIMARY)

    fig_path = FIGURES_DIR / "fig1_grade_distribution.png"
    if fig_path.exists():
        slide.shapes.add_picture(str(fig_path), Inches(1.0), Inches(1.3),
                                  Inches(8.0), Inches(5.0))

    # ════════════════════════════════════════
    # Slide 8: 섹션별 난이도 (Figure 2)
    # ════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_text_box(slide, 0.8, 0.4, 8.4, 0.7, "결과 3: KGCP 섹션별 난이도",
                 font_size=28, bold=True, color=PRIMARY)

    fig_path = FIGURES_DIR / "fig2_section_difficulty.png"
    if fig_path.exists():
        slide.shapes.add_picture(str(fig_path), Inches(0.5), Inches(1.3),
                                  Inches(9.0), Inches(5.5))

    # ════════════════════════════════════════
    # Slide 9: 완전성 결과
    # ════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_text_box(slide, 0.8, 0.4, 8.4, 0.7, "결과 4: KGCP 완전성 분류 (KoBERT)",
                 font_size=28, bold=True, color=PRIMARY)

    data = [
        ["지표", "값"],
        ["모델", "KoBERT (monologg/kobert, 92.2M)"],
        ["학습 데이터", "990개 섹션 + 200개 mixed = 1,190"],
        ["macro F1", "0.81"],
        ["micro F1", "0.82"],
        ["Precision (macro)", "0.98"],
        ["Recall (macro)", "0.70"],
        ["평균 완전성 점수", "98.4%"],
        ["20/20 완전", "42/50건 (84%)"],
    ]
    add_table(slide, len(data), 2, data, top=1.5, width=6.0)

    # ════════════════════════════════════════
    # Slide 10: 평이화 전후 비교 (핵심 결과)
    # ════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, PRIMARY)
    add_text_box(slide, 0.8, 0.4, 8.4, 0.7, "핵심 결과: 평이화 효과",
                 font_size=28, bold=True, color=WHITE)

    # 큰 숫자 3개
    metrics = [
        ("↓ 3.92", "학년 감소", "11.03 → 7.10"),
        ("+ 15.9", "점수 향상", "종합 가독성 점수"),
        ("79.0%", "목표 달성", "≤8학년 도달 비율"),
    ]
    for i, (big, label, sub) in enumerate(metrics):
        left = 0.8 + i * 3.1
        add_text_box(slide, left, 1.8, 2.8, 1.0, big,
                     font_size=44, bold=True, color=ACCENT, alignment=PP_ALIGN.CENTER)
        add_text_box(slide, left, 3.2, 2.8, 0.5, label,
                     font_size=20, bold=True, color=WHITE, alignment=PP_ALIGN.CENTER)
        add_text_box(slide, left, 3.8, 2.8, 0.5, sub,
                     font_size=14, color=GRAY, alignment=PP_ALIGN.CENTER)

    add_text_box(slide, 0.8, 5.5, 8.4, 1.0,
                 "GPT-4o 기반 평이화로 ICF 국제 권장 기준(≤8학년) 달성",
                 font_size=18, color=RGBColor(0xBD, 0xC3, 0xC7), alignment=PP_ALIGN.CENTER)

    # ════════════════════════════════════════
    # Slide 11: 전후 비교 차트 (Figure 3)
    # ════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_text_box(slide, 0.8, 0.4, 8.4, 0.7, "결과 5: 섹션별 평이화 전후 비교",
                 font_size=28, bold=True, color=PRIMARY)

    fig_path = FIGURES_DIR / "fig3_simplification_comparison.png"
    if fig_path.exists():
        slide.shapes.add_picture(str(fig_path), Inches(0.5), Inches(1.3),
                                  Inches(9.0), Inches(5.5))

    # ════════════════════════════════════════
    # Slide 12: Scatter plot (Figure 4)
    # ════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_text_box(slide, 0.8, 0.4, 8.4, 0.7, "결과 6: ICF별 평이화 전후 학년 수준",
                 font_size=28, bold=True, color=PRIMARY)

    fig_path = FIGURES_DIR / "fig4_score_improvement.png"
    if fig_path.exists():
        slide.shapes.add_picture(str(fig_path), Inches(2.0), Inches(1.2),
                                  Inches(6.0), Inches(6.0))

    # ════════════════════════════════════════
    # Slide 13: 평이화 예시
    # ════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_text_box(slide, 0.8, 0.4, 8.4, 0.7, "평이화 예시: [unverified_trial] 학년 15.9 → 6.3",
                 font_size=24, bold=True, color=PRIMARY)

    add_text_box(slide, 0.5, 1.3, 4.3, 0.4, "원문 (학년 15.9)",
                 font_size=14, bold=True, color=RED)
    add_text_box(slide, 0.5, 1.7, 4.3, 3.5,
                 "이 연구에 사용되는 의료기구는 현재 상용화"
                 "되지 않았으며, 이에 대한 효과와 안전성이 완"
                 "전히 검증되지 않았다는 점을 설명 드립니다. "
                 "기존의 치료 표준에 비해 본 연구의 기구가 "
                 "보다 나은 치료 효과를 제공할 수 있다는 기대"
                 "가 있으나, 이는 실험적 과정을 통해 검증 중에 "
                 "있으며, 그 과정에서 해당 기구의 실제 효능이나 "
                 "잠재적인 위험을 구체적으로 밝혀낼 필요가 있"
                 "습니다.",
                 font_size=12, color=PRIMARY)

    add_text_box(slide, 5.2, 1.3, 4.3, 0.4, "평이화 (학년 6.3)",
                 font_size=14, bold=True, color=ACCENT)
    add_text_box(slide, 5.2, 1.7, 4.3, 3.5,
                 "이 기기는 아직 판매되지 않고, 효과나 안전성"
                 "이 완전히 확인되지 않았습니다. 기존 치료보다 "
                 "나은 효과가 있을 것으로 기대합니다. 하지만 "
                 "실험을 통해 자세히 검증하고 있습니다. 이 과정"
                 "에서 기기의 실제 효과와 위험성을 알아내야 "
                 "합니다.",
                 font_size=12, color=PRIMARY)

    add_text_box(slide, 0.5, 5.5, 9.0, 1.0,
                 "• 긴 문장 → 짧은 문장 분리  • 전문 표현 → 쉬운 우리말  • 피동 → 능동",
                 font_size=13, color=GRAY)

    # ════════════════════════════════════════
    # Slide 14: 한계 및 향후 계획
    # ════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_text_box(slide, 0.8, 0.4, 8.4, 0.7, "한계 및 향후 계획",
                 font_size=28, bold=True, color=PRIMARY)

    items = [
        "[한계]",
        "• 시드 사전 규모: 기초어휘 516어, 의학용어 248어 (목표: 4만 + 76,733어)",
        "• 모의 ICF 기반 분석 — 실제 IRB 동의서와 차이 가능",
        "• 평이화 품질에 대한 전문가 평가(human evaluation) 미수행",
        "• KoBERT 학습 데이터 50건 — 실제 동의서 다양성 미포착",
        "",
        "[Phase 2 계획]",
        "• 실제 IRB 동의서 확보 (기관 협조)",
        "• 국립국어원 전체 기초어휘 목록 + 의학용어집 연동",
        "• 평이화 품질 전문가 평가 (내용 보존율)",
        "• 논문 투고",
    ]
    add_bullet_slide(slide, items, font_size=15)

    # ════════════════════════════════════════
    # Slide 15: 결론
    # ════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, PRIMARY)
    add_text_box(slide, 0.8, 0.4, 8.4, 0.7, "결론",
                 font_size=28, bold=True, color=WHITE)

    items_text = (
        "1. 한국어 ICF 가독성 = 평균 10.05학년 (고교 수준)\n"
        "   → ICF 국제 권장 기준(≤8학년) 2.05학년 초과\n\n"
        "2. GPT-4o 평이화로 학년 3.92 감소 → 평균 7.10학년 달성\n"
        "   → 79% 섹션이 목표 수준 도달\n\n"
        "3. KoBERT 완전성 분류 macro F1 = 0.81\n\n"
        "4. 수집-분석-평이화-평가 end-to-end 자동화 파이프라인 실현"
    )
    add_text_box(slide, 1.0, 1.5, 8.0, 4.5, items_text,
                 font_size=18, color=WHITE)

    add_text_box(slide, 0.8, 6.2, 8.4, 0.5,
                 "감사합니다",
                 font_size=24, bold=True, color=ACCENT, alignment=PP_ALIGN.CENTER)

    # ═══ 저장 ═══
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUTPUT_PATH))
    print(f"PPT 저장 완료: {OUTPUT_PATH}")
    print(f"총 슬라이드: {len(prs.slides)}장")


if __name__ == "__main__":
    create_presentation()
