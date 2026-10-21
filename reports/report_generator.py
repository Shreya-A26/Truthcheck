import io
from datetime import datetime, timezone
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# TruthLens Palette
PRIMARY_INK = colors.HexColor("#172B3A")
DEEP_NAVY = colors.HexColor("#102A43")
WARM_BG = colors.HexColor("#F7F6F2")
TEAL_ACCENT = colors.HexColor("#147D78")
SOFT_TEAL = colors.HexColor("#E6F3F0")
MUTED_TEXT = colors.HexColor("#637381")
DIVIDER_COLOR = colors.HexColor("#E2E6E8")
SUCCESS_COLOR = colors.HexColor("#21845B")
WARNING_COLOR = colors.HexColor("#B7791F")
ERROR_COLOR = colors.HexColor("#C13B42")

def generate_pdf_report(result_data: dict) -> io.BytesIO:
    """
    Generates a beautifully formatted, editorial-quality PDF credibility report.
    Returns in-memory BytesIO buffer.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=45,
        leftMargin=45,
        topMargin=45,
        bottomMargin=45
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    style_header_brand = ParagraphStyle(
        'BrandTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=DEEP_NAVY
    )
    style_tagline = ParagraphStyle(
        'BrandTagline',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=MUTED_TEXT
    )
    style_doc_title = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=PRIMARY_INK
    )
    style_section_h = ParagraphStyle(
        'SectionH',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=DEEP_NAVY,
        spaceBefore=10,
        spaceAfter=5
    )
    style_body = ParagraphStyle(
        'BodyTxt',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=PRIMARY_INK
    )
    style_muted = ParagraphStyle(
        'MutedTxt',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=MUTED_TEXT
    )
    style_badge_text = ParagraphStyle(
        'BadgeText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        alignment=TA_CENTER
    )

    story = []

    # 1. Header Banner
    header_data = [
        [
            Paragraph("<b>TRUTHLENS</b> &mdash; Credibility Report", style_header_brand),
            Paragraph(f"Date: {datetime.now(timezone.utc).strftime('%B %d, %Y')}<br/>Ref: {result_data.get('id', 'N/A')[:8]}", style_tagline)
        ]
    ]
    t_header = Table(header_data, colWidths=[360, 160])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1, color=DIVIDER_COLOR, spaceAfter=12))

    # 2. Article Information
    article_title = result_data.get("article_title", "Submitted News Item")
    story.append(Paragraph(f"<b>Article / Headline:</b> {article_title}", style_doc_title))
    story.append(Spacer(1, 6))

    source_info = result_data.get("source_info", {})
    meta_info = [
        f"<b>Input Type:</b> {result_data.get('input_type', 'Text').title()}",
        f"<b>Publisher:</b> {source_info.get('domain', 'User Submitted')}",
        f"<b>Author:</b> {source_info.get('author', 'Not specified')}",
        f"<b>Published:</b> {source_info.get('publication_date', 'Not available')}"
    ]
    meta_table_data = [
        [Paragraph(meta_info[0], style_body), Paragraph(meta_info[1], style_body)],
        [Paragraph(meta_info[2], style_body), Paragraph(meta_info[3], style_body)]
    ]
    t_meta = Table(meta_table_data, colWidths=[260, 260])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), WARM_BG),
        ('BOX', (0, 0), (-1, -1), 0.5, DIVIDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, DIVIDER_COLOR),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 14))

    # 3. Model Assessment Panel
    prediction = result_data.get("prediction_label", "Uncertain")
    confidence = result_data.get("confidence", 0.0)
    word_count = result_data.get("word_count", 0)

    if prediction == "Likely Credible":
        pred_color = SUCCESS_COLOR
        badge_bg = SOFT_TEAL
    elif prediction == "Likely Misleading":
        pred_color = ERROR_COLOR
        badge_bg = colors.HexColor("#FBEAEB")
    else:
        pred_color = WARNING_COLOR
        badge_bg = colors.HexColor("#FEF7EA")

    style_pred_label = ParagraphStyle(
        'PredLabel',
        parent=style_badge_text,
        textColor=pred_color
    )

    pred_card = [
        [
            Paragraph(f"ASSESSMENT: {prediction.upper()}", style_pred_label),
            Paragraph(f"<b>Model Confidence:</b> {confidence}%<br/><b>Words Analyzed:</b> {word_count}", style_body)
        ]
    ]
    t_pred = Table(pred_card, colWidths=[260, 260])
    t_pred.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), badge_bg),
        ('BOX', (0, 0), (-1, -1), 1, pred_color),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, DIVIDER_COLOR),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t_pred)
    story.append(Spacer(1, 12))

    # 4. Plain-language Explanation
    story.append(Paragraph("Why did the model make this assessment?", style_section_h))
    explanation = result_data.get("explanation", "Assessment generated from statistical pattern analysis.")
    story.append(Paragraph(explanation, style_body))
    story.append(Spacer(1, 6))

    # Feature influence terms
    features = result_data.get("feature_contributions", [])
    if features:
        feature_rows = [["Influential Term / Phrase", "Directional Influence", "Impact Weight"]]
        for f in features[:6]:
            lean_text = "Pushed toward Credible" if f.get("lean") == "real" else "Pushed toward Misleading"
            feature_rows.append([
                f.get("term", ""),
                lean_text,
                f"{round(f.get('abs_score', 0), 3)}"
            ])
        t_feat = Table(feature_rows, colWidths=[200, 200, 120])
        t_feat.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), WARM_BG),
            ('TEXTCOLOR', (0, 0), (-1, 0), DEEP_NAVY),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOX', (0, 0), (-1, -1), 0.5, DIVIDER_COLOR),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, DIVIDER_COLOR),
        ]))
        story.append(t_feat)
        story.append(Spacer(1, 6))
        story.append(Paragraph("<i>Note: Word patterns reflect statistical associations in the training data and do not individually prove veracity or intent.</i>", style_muted))

    story.append(Spacer(1, 12))

    # 5. Independent Claim Verification
    story.append(Paragraph("Independent Evidence Verification", style_section_h))
    verification = result_data.get("verification", {})
    if not verification.get("available", False):
        story.append(Paragraph("<i>Independent verification is not currently available. The result in this report is based on the machine-learning model only.</i>", style_body))
    else:
        claims = verification.get("claims", [])
        if not claims:
            story.append(Paragraph("<i>No specific factual claims were isolated from the text for external verification.</i>", style_body))
        else:
            for c in claims:
                claim_box = [
                    [Paragraph(f"<b>Claim:</b> \"{c.get('claim', '')}\"", style_body)],
                    [Paragraph(f"<b>Status:</b> {c.get('status', 'Unknown')} &mdash; {c.get('summary', '')}", style_muted)]
                ]
                t_c = Table(claim_box, colWidths=[520])
                t_c.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#FAFAFA")),
                    ('BOX', (0, 0), (-1, -1), 0.5, DIVIDER_COLOR),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                story.append(t_c)
                story.append(Spacer(1, 4))

    story.append(Spacer(1, 12))

    # 6. Recommended Next Steps
    story.append(Paragraph("Recommended Verification Steps", style_section_h))
    checklist_text = (
        "&bull; Read the primary original source directly.<br/>"
        "&bull; Verify the date of publication to guard against out-of-context recirculations.<br/>"
        "&bull; Cross-reference claims with established official public archives or peer-reviewed databases.<br/>"
        "&bull; Never assume an ML prediction constitutes definitive factual confirmation."
    )
    story.append(Paragraph(checklist_text, style_body))
    story.append(Spacer(1, 14))

    # 7. Limitations & Methodology Note
    story.append(HRFlowable(width="100%", thickness=0.5, color=DIVIDER_COLOR, spaceAfter=8))
    disclaimer_text = (
        "<b>TruthLens Methodology & Limitations:</b> This report is generated by an automated natural language "
        "processing model (TF-IDF + Logistic Regression, evaluated at 99.08% test accuracy on reference corpora). "
        "Model classification reflects linguistic similarity to documented training exemplars and cannot substitute for "
        "investigative human fact-checking. TruthLens does not store personal document contents permanently."
    )
    story.append(Paragraph(disclaimer_text, style_muted))

    doc.build(story)
    buffer.seek(0)
    return buffer
