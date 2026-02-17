"""
Script de generation du PDF de la documentation LIONS.
Utilise fpdf2 pour produire un PDF propre a partir du fichier Markdown.
"""
import re
import os
from fpdf import FPDF
from fpdf.enums import XPos, YPos

# Chemins
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MD_FILE = os.path.join(SCRIPT_DIR, 'DOCUMENTATION_LIONS.md')
PDF_FILE = os.path.join(SCRIPT_DIR, 'DOCUMENTATION_LIONS.pdf')


class DocPDF(FPDF):
    """PDF personnalise avec en-tete et pied de page."""

    def header(self):
        if self.page_no() > 1:
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 5, 'LIONS - Documentation Technique Complete', align='C')
            self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', align='C')


def clean_text(text):
    """Nettoie le texte markdown pour l'affichage PDF."""
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    return text.strip()


def parse_table(lines, start_idx):
    """Parse un tableau markdown et retourne (rows, end_idx)."""
    rows = []
    idx = start_idx
    while idx < len(lines):
        line = lines[idx].strip()
        if not line.startswith('|'):
            break
        if re.match(r'^\|[\s\-:|]+\|$', line):
            idx += 1
            continue
        cells = [c.strip() for c in line.split('|')[1:-1]]
        rows.append(cells)
        idx += 1
    return rows, idx


def nl(pdf):
    """Passe a la ligne suivante (equivalent de ln=True dans cell)."""
    pdf.set_x(pdf.l_margin)
    pdf.set_y(pdf.get_y())


def cell_ln(pdf, w, h, txt, **kwargs):
    """cell() suivi d'un passage a la ligne."""
    pdf.cell(w, h, txt, new_x=XPos.LMARGIN, new_y=YPos.NEXT, **kwargs)


def fit_text(pdf, txt, max_w):
    """Tronque le texte pour qu'il tienne dans max_w (mm)."""
    if pdf.get_string_width(txt) + 1 <= max_w:
        return txt
    while len(txt) > 0 and pdf.get_string_width(txt + '..') + 1 > max_w:
        txt = txt[:-1]
    return txt + '..' if txt else ''


def generate_pdf():
    with open(MD_FILE, 'r', encoding='utf-8') as f:
        md_text = f.read()

    lines = md_text.split('\n')

    pdf = DocPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # -- Page de titre --
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 28)
    pdf.ln(50)
    cell_ln(pdf, 0, 15, 'LIONS', align='C')
    pdf.set_font('Helvetica', '', 14)
    pdf.ln(5)
    cell_ln(pdf, 0, 10, 'Documentation Technique Complete', align='C')
    pdf.ln(10)
    pdf.set_font('Helvetica', '', 11)
    cell_ln(pdf, 0, 8, 'Programme de Simulation de Dynamique', align='C')
    cell_ln(pdf, 0, 8, "d'Ions dans un Cyclotron", align='C')
    pdf.ln(20)
    pdf.set_font('Helvetica', 'I', 10)
    cell_ln(pdf, 0, 8, 'Auteur original : Patrick Bertrand - GANIL', align='C')
    cell_ln(pdf, 0, 8, 'Conversion Python et GUI : 2026', align='C')
    pdf.ln(30)
    pdf.set_font('Helvetica', '', 9)
    cell_ln(pdf, 0, 6, 'Genere le 13 fevrier 2026', align='C')

    # -- Contenu --
    pdf.add_page()
    i = 0
    in_code_block = False
    code_buffer = []

    while i < len(lines):
        line = lines[i]

        # Blocs de code
        if line.strip().startswith('```'):
            if in_code_block:
                in_code_block = False
                pdf.set_font('Courier', '', 7)
                pdf.set_fill_color(240, 240, 240)
                pdf.set_x(pdf.l_margin)  # Reset position X
                code_text = '\n'.join(code_buffer)
                if code_text.strip():
                    pdf.multi_cell(0, 3.5, code_text, border=1, fill=True)
                pdf.ln(3)
                code_buffer = []
                pdf.set_font('Helvetica', '', 10)
            else:
                in_code_block = True
                code_buffer = []
            i += 1
            continue

        if in_code_block:
            code_buffer.append(line)
            i += 1
            continue

        stripped = line.strip()

        # Lignes vides
        if not stripped:
            i += 1
            continue

        # Separateurs ---
        if re.match(r'^-{3,}$', stripped):
            pdf.ln(3)
            pdf.set_draw_color(180, 180, 180)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(3)
            i += 1
            continue

        # Titre H1
        if stripped.startswith('# ') and not stripped.startswith('## '):
            i += 1
            continue

        # Titre H2 -> nouvelle page
        if stripped.startswith('## '):
            title = clean_text(stripped[3:])
            pdf.add_page()
            pdf.set_font('Helvetica', 'B', 18)
            pdf.set_text_color(0, 51, 102)
            cell_ln(pdf, 0, 12, title)
            pdf.set_draw_color(0, 51, 102)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font('Helvetica', '', 10)
            i += 1
            continue

        # Titre H3
        if stripped.startswith('### '):
            title = clean_text(stripped[4:])
            pdf.ln(5)
            pdf.set_font('Helvetica', 'B', 13)
            pdf.set_text_color(0, 70, 130)
            cell_ln(pdf, 0, 8, title)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font('Helvetica', '', 10)
            pdf.ln(2)
            i += 1
            continue

        # Titre H4
        if stripped.startswith('#### '):
            title = clean_text(stripped[5:])
            pdf.ln(3)
            pdf.set_font('Helvetica', 'B', 11)
            pdf.set_text_color(50, 50, 50)
            cell_ln(pdf, 0, 7, title)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font('Helvetica', '', 10)
            pdf.ln(1)
            i += 1
            continue

        # Tableaux
        if stripped.startswith('|'):
            rows, end_idx = parse_table(lines, i)
            if rows:
                n_cols = len(rows[0])
                page_w = 190
                font_size = 6 if n_cols > 6 else (7 if n_cols > 5 else (8 if n_cols > 3 else 9))

                # Calculer les largeurs adaptees au contenu
                pdf.set_font('Helvetica', 'B', font_size)
                max_lens = [0] * n_cols
                for row in rows:
                    for ci in range(min(n_cols, len(row))):
                        txt = clean_text(row[ci])
                        sw = pdf.get_string_width(txt) + 2
                        if sw > max_lens[ci]:
                            max_lens[ci] = sw
                total = sum(max_lens) if sum(max_lens) > 0 else 1
                col_widths = [max(12, ml / total * page_w) for ml in max_lens]
                # Normaliser pour que la somme = page_w
                s = sum(col_widths)
                col_widths = [w / s * page_w for w in col_widths]

                # En-tete du tableau
                pdf.set_font('Helvetica', 'B', font_size)
                pdf.set_fill_color(0, 51, 102)
                pdf.set_text_color(255, 255, 255)
                for ci, cell in enumerate(rows[0]):
                    w = col_widths[ci] if ci < len(col_widths) else col_widths[-1]
                    txt = fit_text(pdf, clean_text(cell), w)
                    pdf.cell(w, 5, txt, border=1, fill=True)
                pdf.ln()
                pdf.set_text_color(0, 0, 0)

                # Donnees
                pdf.set_font('Helvetica', '', font_size)
                for ri, row in enumerate(rows[1:]):
                    fill = (ri % 2 == 0)
                    if fill:
                        pdf.set_fill_color(245, 245, 250)
                    for ci in range(n_cols):
                        w = col_widths[ci] if ci < len(col_widths) else col_widths[-1]
                        if ci < len(row):
                            txt = fit_text(pdf, clean_text(row[ci]), w)
                        else:
                            txt = ''
                        pdf.cell(w, 5, txt, border=1, fill=fill)
                    pdf.ln()

                pdf.ln(3)
                pdf.set_font('Helvetica', '', 10)
            i = end_idx
            continue

        # Listes a puces
        if re.match(r'^[-*]\s', stripped) or re.match(r'^\d+\.\s', stripped):
            text = re.sub(r'^[-*]\s+', '', stripped)
            text = re.sub(r'^\d+\.\s+', '', text)
            text = clean_text(text)
            indent = len(line) - len(line.lstrip())
            if indent >= 4:
                prefix = '     - '
            elif stripped[0] in '-*':
                prefix = '  - '
            else:
                num = stripped.split('.')[0].strip()
                prefix = f'  {num}. '
            pdf.set_font('Helvetica', '', 9)
            pdf.set_x(pdf.l_margin)  # Reset position X
            full_text = prefix + text
            if full_text.strip():
                pdf.multi_cell(0, 4.5, full_text)
            pdf.set_font('Helvetica', '', 10)
            i += 1
            continue

        # Paragraphes normaux
        text = clean_text(stripped)
        if text:
            pdf.set_font('Helvetica', '', 10)
            pdf.set_x(pdf.l_margin)  # Reset position X
            pdf.multi_cell(0, 5, text)
            pdf.ln(2)

        i += 1

    pdf.output(PDF_FILE)
    print(f'PDF genere : {PDF_FILE}')
    print(f'Taille : {os.path.getsize(PDF_FILE) / 1024:.0f} Ko')
    print(f'Pages : {pdf.page_no()}')


if __name__ == '__main__':
    generate_pdf()
