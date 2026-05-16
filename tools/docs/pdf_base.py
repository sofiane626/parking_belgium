"""
Classe PDF stylée commune à tous les documents TFE de Parking.Belgium.

Helpers principaux :
    pdf = PBPdf(title="...", subtitle="...")
    pdf.cover()           # page de garde
    pdf.h1("Section")     # titre principal (nouvelle page)
    pdf.h2("Sous-section")
    pdf.h3("Détail")
    pdf.p("paragraphe…")
    pdf.bullet("item")
    pdf.code("...")       # bloc de code monospace
    pdf.table(headers, rows)
    pdf.kv(label, value)  # ligne clé:valeur
    pdf.save("path.pdf")

Charte couleurs (alignée sur le branding Parking.Belgium) :
    - brand-700 #08447F (titres principaux)
    - brand-500 #2375C0 (accents)
    - signal-400 #FFCD00 (séparateurs)
    - slate-700 #334155 (corps de texte)
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from fpdf import FPDF

# Polices Unicode (Arial Windows). Permettent d'afficher accents, • et caractères spéciaux.
WIN_FONTS = Path("C:/Windows/Fonts")
ARIAL_TTF    = WIN_FONTS / "arial.ttf"
ARIAL_BD     = WIN_FONTS / "arialbd.ttf"
ARIAL_IT     = WIN_FONTS / "ariali.ttf"
COURIER_TTF  = WIN_FONTS / "cour.ttf"

# Couleurs (RGB)
BRAND_700 = (8, 68, 127)
BRAND_500 = (35, 117, 192)
BRAND_100 = (212, 231, 248)
SIGNAL_400 = (255, 205, 0)
SLATE_900 = (15, 23, 42)
SLATE_700 = (51, 65, 85)
SLATE_500 = (100, 116, 139)
SLATE_300 = (203, 213, 225)
SLATE_100 = (241, 245, 249)
WHITE = (255, 255, 255)


class PBPdf(FPDF):
    """PDF stylé pour les livrables TFE."""

    def __init__(self, *, title: str, subtitle: str = "", **kw):
        super().__init__(orientation="P", unit="mm", format="A4", **kw)
        self.doc_title = title
        self.doc_subtitle = subtitle
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(left=18, top=22, right=18)
        # Charge Arial Unicode (depuis Windows) pour pouvoir afficher
        # accents, • et caractères spéciaux.
        self.add_font("Arial", "",  str(ARIAL_TTF))
        self.add_font("Arial", "B", str(ARIAL_BD))
        self.add_font("Arial", "I", str(ARIAL_IT))
        if COURIER_TTF.exists():
            self.add_font("Mono", "", str(COURIER_TTF))
        self.set_font("Arial", size=10)
        self._cover_done = False

    # ----- header / footer (auto) ------------------------------------------

    def header(self):
        # Pas de header sur la page de garde.
        if self.page_no() == 1 and self._cover_done:
            return
        if not self._cover_done:
            return
        self.set_y(8)
        self.set_font("Arial", "", 8)
        self.set_text_color(*SLATE_500)
        self.cell(0, 5, self.doc_title, align="L")
        self.set_x(-50)
        self.cell(40, 5, "Parking.Belgium", align="R")
        # Liseré jaune sous le header
        self.set_draw_color(*SIGNAL_400)
        self.set_line_width(0.8)
        self.line(18, 14, 192, 14)
        self.set_line_width(0.2)
        self.ln(8)

    def footer(self):
        if self.page_no() == 1 and self._cover_done:
            return
        self.set_y(-12)
        self.set_font("Arial", "", 8)
        self.set_text_color(*SLATE_500)
        self.cell(0, 5, f"Page {self.page_no()}", align="C")

    # ----- cover -----------------------------------------------------------

    def cover(self, *, subtitle: str | None = None):
        """Page de garde plein écran avec gradient brand."""
        self.add_page()
        # Bandeau couleur brand en haut
        self.set_fill_color(*BRAND_700)
        self.rect(0, 0, 210, 110, "F")
        # Bandeau jaune signal
        self.set_fill_color(*SIGNAL_400)
        self.rect(0, 110, 210, 3, "F")

        # Logo / marque
        self.set_y(30)
        self.set_font("Arial", "B", 36)
        self.set_text_color(*WHITE)
        self.cell(0, 18, "Parking.Belgium", align="C")
        self.ln(20)

        # Sous-titre projet
        self.set_font("Arial", "", 12)
        self.cell(0, 6, "Plateforme unique de stationnement", align="C")
        self.ln(5)
        self.cell(0, 6, "pour les 19 communes de Bruxelles", align="C")

        # Titre du document
        self.set_y(130)
        self.set_font("Arial", "B", 22)
        self.set_text_color(*BRAND_700)
        self.multi_cell(0, 10, self.doc_title, align="C")
        if subtitle or self.doc_subtitle:
            self.ln(2)
            self.set_font("Arial", "", 12)
            self.set_text_color(*SLATE_700)
            self.multi_cell(0, 6, subtitle or self.doc_subtitle, align="C")

        # Métadonnées en bas
        self.set_y(-50)
        self.set_font("Arial", "", 10)
        self.set_text_color(*SLATE_700)
        self.cell(0, 5, "Travail de fin d'études", align="C")
        self.ln(5)
        self.cell(0, 5, "Sofiane Ezzahti", align="C")
        self.ln(5)
        self.cell(0, 5, date.today().isoformat(), align="C")

        self._cover_done = True

    # ----- typography ------------------------------------------------------

    def h1(self, text: str, *, new_page: bool = True):
        if new_page:
            self.add_page()
        else:
            self.ln(6)
        self.set_font("Arial", "B", 18)
        self.set_text_color(*BRAND_700)
        self.multi_cell(0, 9, text)
        # Filet sous le titre
        self.set_draw_color(*SIGNAL_400)
        self.set_line_width(0.8)
        y = self.get_y() + 1
        self.line(18, y, 60, y)
        self.set_line_width(0.2)
        self.ln(5)

    def h2(self, text: str):
        self.ln(3)
        self.set_font("Arial", "B", 13)
        self.set_text_color(*BRAND_500)
        self.multi_cell(0, 7, text)
        self.ln(1)

    def h3(self, text: str):
        self.ln(1)
        self.set_font("Arial", "B", 11)
        self.set_text_color(*SLATE_900)
        self.multi_cell(0, 6, text)
        self.ln(0.5)

    def p(self, text: str):
        self.set_font("Arial", "", 10)
        self.set_text_color(*SLATE_700)
        self.multi_cell(0, 5.2, text)
        self.ln(1.5)

    def bullet(self, text: str, *, level: int = 0):
        self.set_font("Arial", "", 10)
        self.set_text_color(*SLATE_700)
        indent = 4 + level * 4
        self.set_x(self.l_margin + indent)
        # Bullet caractère
        bullet_char = "•" if level == 0 else "—"
        self.cell(4, 5.2, bullet_char)
        self.multi_cell(0, 5.2, text)
        self.ln(0.5)

    def kv(self, label: str, value: str, *, label_width: int = 50):
        self.set_x(self.l_margin)
        self.set_font("Arial", "B", 10)
        self.set_text_color(*SLATE_900)
        self.cell(label_width, 5.5, label)
        self.set_font("Arial", "", 10)
        self.set_text_color(*SLATE_700)
        self.multi_cell(0, 5.5, value)

    def code(self, text: str):
        self.set_font("Mono", "", 9)
        self.set_fill_color(*SLATE_100)
        self.set_text_color(*SLATE_900)
        # Boîte autour
        x_start = self.get_x()
        for line in text.split("\n"):
            self.cell(0, 5, "  " + line, fill=True, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def table(self, headers: list[str], rows: list[list[str]], *,
              col_widths: list[float] | None = None):
        """Tableau simple avec en-tête couleur brand."""
        page_width = 210 - 36
        if col_widths is None:
            col_widths = [page_width / len(headers)] * len(headers)
        # En-tête
        self.set_font("Arial", "B", 9)
        self.set_fill_color(*BRAND_700)
        self.set_text_color(*WHITE)
        for w, h in zip(col_widths, headers):
            self.cell(w, 7, h, border=0, fill=True)
        self.ln(7)
        # Lignes
        self.set_font("Arial", "", 9)
        self.set_text_color(*SLATE_700)
        fill = False
        for row in rows:
            if fill:
                self.set_fill_color(*SLATE_100)
            else:
                self.set_fill_color(*WHITE)
            # Calcul de la hauteur de la ligne (multi-cell)
            line_h = 5.5
            # Détermine combien de lignes prend chaque cellule
            n_lines = 1
            for w, cell in zip(col_widths, row):
                lines = max(1, len(str(cell)) // max(1, int(w / 2)) + (1 if "\n" in str(cell) else 0))
                if lines > n_lines:
                    n_lines = lines
            row_h = line_h * n_lines
            # Si on dépasse la page : nouvelle page
            if self.get_y() + row_h > 280:
                self.add_page()
            # Dessiner les cellules
            y_top = self.get_y()
            x_start = self.get_x()
            x = x_start
            for w, cell in zip(col_widths, row):
                self.set_xy(x, y_top)
                self.multi_cell(w, line_h, str(cell), border="B", fill=fill,
                                max_line_height=line_h)
                x += w
            self.set_y(y_top + row_h)
            fill = not fill
        self.ln(3)

    def badge(self, text: str, *, color: tuple = SIGNAL_400):
        """Petite pastille couleur en ligne."""
        self.set_font("Arial", "B", 8)
        self.set_fill_color(*color)
        self.set_text_color(*SLATE_900)
        w = self.get_string_width(text) + 4
        self.cell(w, 5, text, fill=True, border=0)


def save_to(pdf: PBPdf, filename: str) -> Path:
    """Sauve dans documents/<filename> et retourne le path."""
    out_dir = Path(__file__).resolve().parent.parent.parent / "documents"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / filename
    pdf.output(str(path))
    return path
