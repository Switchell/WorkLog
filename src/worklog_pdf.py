"""PDF-отчёт по сгруппированным данным (нужны колонки Sotrudnik, Time, Profit)."""
from __future__ import annotations

import pandas as pd
from fpdf import FPDF


def create_pdf_report(df: pd.DataFrame) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)

    def clean_txt(text):
        text = str(text)
        chars = {
            "А": "A",
            "Б": "B",
            "В": "V",
            "Г": "G",
            "Д": "D",
            "Е": "E",
            "Ё": "E",
            "Ж": "Zh",
            "З": "Z",
            "И": "I",
            "Й": "Y",
            "К": "K",
            "Л": "L",
            "М": "M",
            "Н": "N",
            "О": "O",
            "П": "P",
            "Р": "R",
            "С": "S",
            "Т": "T",
            "У": "U",
            "Ф": "F",
            "Х": "H",
            "Ц": "Ts",
            "Ч": "Ch",
            "Ш": "Sh",
            "Щ": "Sch",
            "Ъ": "",
            "Ы": "y",
            "Ь": "",
            "Э": "E",
            "Ю": "Yu",
            "Я": "Ya",
            "а": "a",
            "б": "b",
            "в": "v",
            "г": "g",
            "д": "d",
            "е": "e",
            "ё": "e",
            "ж": "zh",
            "з": "z",
            "и": "i",
            "й": "y",
            "к": "k",
            "л": "l",
            "м": "m",
            "н": "n",
            "о": "o",
            "п": "p",
            "р": "r",
            "с": "s",
            "т": "t",
            "у": "u",
            "ф": "f",
            "х": "h",
            "ц": "ts",
            "ч": "ch",
            "ш": "sh",
            "щ": "sch",
            "ъ": "",
            "ы": "y",
            "ь": "",
            "э": "e",
            "ю": "yu",
            "я": "ya",
        }
        for k, v in chars.items():
            text = text.replace(k, v)
        return text.encode("ascii", "ignore").decode("ascii")

    pdf.cell(200, 10, "WORK REPORT", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(10)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(80, 10, "Employee", border=1)
    pdf.cell(40, 10, "Hours", border=1)
    pdf.cell(50, 10, "Profit", border=1)
    pdf.ln()

    pdf.set_font("Helvetica", size=10)
    report_df = df.groupby("Sotrudnik").agg({"Time": "sum", "Profit": "sum"}).reset_index()

    for _, row in report_df.iterrows():
        name = clean_txt(row["Sotrudnik"])
        if not name.strip():
            name = "Unknown"
        pdf.cell(80, 10, name, border=1)
        pdf.cell(40, 10, f"{row['Time']:.1f}", border=1)
        pdf.cell(50, 10, f"{int(row['Profit'])}", border=1)
        pdf.ln()

    return bytes(pdf.output())
