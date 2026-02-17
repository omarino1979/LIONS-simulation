"""
lions_plots.py - Widget pyqtgraph pour les plots temps reel de LIONS
Plots dynamiques avec zoom/pan persistant et curseur crosshair.
"""

import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QDoubleSpinBox, QCheckBox, QPushButton, QSpinBox, QDialog,
    QFileDialog, QRubberBand
)
from PyQt5.QtCore import Qt, QEvent, QRect, QSize, QPoint
from PyQt5.QtGui import QFont, QColor, QVector3D

# OpenGL 3D (optionnel)
try:
    import pyqtgraph.opengl as gl
    HAS_GL = True
except ImportError:
    HAS_GL = False

# Palette de couleurs (fond clair, courbes vives)
BG_COLOR = '#f0f2f5'
PLOT_BG = '#ffffff'
GRID_COLOR = '#c8d0dc'
TEXT_COLOR = '#2c3e50'
TITLE_COLOR = '#1a1a2e'

# Couleurs par famille (jusqu'a 10 familles)
FAMILY_COLORS = [
    '#1565C0',  # bleu
    '#d32f2f',  # rouge
    '#2e7d32',  # vert
    '#ff6f00',  # orange
    '#7b1fa2',  # violet
    '#00838f',  # teal
    '#c62828',  # rouge fonce
    '#283593',  # indigo
    '#558b2f',  # vert lime
    '#4e342e',  # marron
]

# Configuration globale pyqtgraph
# antialias=False pour meilleures performances temps-reel
pg.setConfigOptions(antialias=False, background=BG_COLOR, foreground=TEXT_COLOR)


class CrosshairOverlay:
    """Curseur crosshair + affichage des coordonnees sur un PlotItem."""

    def __init__(self, plot_item):
        self.plot = plot_item
        self.vb = plot_item.getViewBox()

        pen = pg.mkPen(color='#888888', width=0.5, style=Qt.DashLine)
        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=pen)
        self.h_line = pg.InfiniteLine(angle=0, movable=False, pen=pen)

        self.label = pg.TextItem(
            text='', color=TEXT_COLOR, anchor=(0, 1),
            fill=pg.mkBrush(255, 255, 255, 180)
        )
        self.label.setFont(QFont('sans-serif', 8))

        self.v_line.setVisible(False)
        self.h_line.setVisible(False)
        self.label.setVisible(False)

        self.plot.addItem(self.v_line, ignoreBounds=True)
        self.plot.addItem(self.h_line, ignoreBounds=True)
        self.plot.addItem(self.label, ignoreBounds=True)

        self.proxy = pg.SignalProxy(
            self.plot.scene().sigMouseMoved,
            rateLimit=30,
            slot=self._on_mouse_moved
        )

    def _on_mouse_moved(self, evt):
        pos = evt[0]
        if self.plot.sceneBoundingRect().contains(pos):
            mouse_point = self.vb.mapSceneToView(pos)
            x = mouse_point.x()
            y = mouse_point.y()
            self.v_line.setPos(x)
            self.h_line.setPos(y)
            self.label.setText(f'x={x:.2f}\ny={y:.2f}')
            self.label.setPos(x, y)
            self.v_line.setVisible(True)
            self.h_line.setVisible(True)
            self.label.setVisible(True)
        else:
            self.v_line.setVisible(False)
            self.h_line.setVisible(False)
            self.label.setVisible(False)


class PlotCanvas(QWidget):
    """Canvas pyqtgraph avec 5 plots pour la simulation LIONS."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.graphics_widget = pg.GraphicsLayoutWidget()
        self.graphics_widget.setBackground(BG_COLOR)
        layout.addWidget(self.graphics_widget)

        # Limite de rayon pour le plot XY (0 = auto)
        self.rmax_display = 0.0
        # Limite de rayon pour le plot R-theta (0 = auto/pas de filtre)
        self.rmax_rtheta = 0.0
        # Limite de rayon pour le plot R-dphi (0 = auto/pas de filtre)
        self.rmax_rdph = 0.0

        # Grille 3x2
        self.plot_xy = self.graphics_widget.addPlot(row=0, col=0)
        self.plot_energy = self.graphics_widget.addPlot(row=0, col=1)
        self.plot_rtheta = self.graphics_widget.addPlot(row=1, col=0)
        self.plot_zpz = self.graphics_widget.addPlot(row=1, col=1)
        self.plot_rdph = self.graphics_widget.addPlot(row=2, col=0)

        # Style
        self._style_plot(self.plot_xy, 'Trajectoire XY', 'X (mm)', 'Y (mm)')
        self._style_plot(self.plot_energy, 'Energie vs Tour', 'Tour', 'Energie (MeV/A)')
        self._style_plot(self.plot_rtheta, 'R - \u03b8', '\u03b8 (deg)', 'R (mm)')
        self._style_plot(self.plot_zpz, 'Espace de phase Z - Pz', 'Z (mm)', 'Pz (mrad)')
        self._style_plot(self.plot_rdph, 'R - d\u03c6', 'R (mm)', 'd\u03c6 (deg)')

        # Aspect egal pour XY
        self.plot_xy.setAspectLocked(True, ratio=1.0)

        # Legendes (ajoutees dynamiquement quand nbrfam > 1)
        self._legends_added = False

        # Items deflecteurs dessines sur plot_xy
        self._deflector_items = []

        # Buffers et courbes par famille (crees dynamiquement)
        self._fam_data = {}    # {k: {'x':[], 'y':[], 'turn':[], ...}}
        self._fam_curves = {}  # {k: {'xy':..., 'energy':..., 'rtheta':..., 'zpz':...}}

        # Crosshairs
        self.crosshairs = []
        for plot in [self.plot_xy, self.plot_energy,
                     self.plot_rtheta, self.plot_zpz, self.plot_rdph]:
            self.crosshairs.append(CrosshairOverlay(plot))

        # Shim de compatibilite pour canvas.fig.savefig()
        self.fig = _FigShim(self)

    @staticmethod
    def _style_plot(plot_item, title, xlabel, ylabel):
        """Applique le style a un PlotItem."""
        plot_item.setTitle(title, color=TITLE_COLOR, size='11pt', bold=True)
        plot_item.setLabel('bottom', xlabel, color=TEXT_COLOR,
                           **{'font-size': '9pt'})
        plot_item.setLabel('left', ylabel, color=TEXT_COLOR,
                           **{'font-size': '9pt'})
        plot_item.getViewBox().setBackgroundColor(PLOT_BG)
        plot_item.showGrid(x=True, y=True, alpha=0.4)
        for axis_name in ['bottom', 'left']:
            axis = plot_item.getAxis(axis_name)
            axis.setPen(pg.mkPen(color='#aab5c8', width=0.8))
            axis.setTextPen(pg.mkPen(color=TEXT_COLOR))
            axis.setStyle(tickLength=-4)

    def _ensure_family(self, k, nbrfam=1):
        """Cree les buffers et courbes pour la famille k si necessaire."""
        if k in self._fam_data:
            return

        # Ajouter les legendes AVANT les courbes (pour que pyqtgraph les enregistre)
        if nbrfam > 1 and not self._legends_added:
            self._legends_added = True
            for plot in [self.plot_xy, self.plot_energy,
                         self.plot_rtheta, self.plot_zpz, self.plot_rdph]:
                legend = plot.addLegend(offset=(5, 5))
                legend.setLabelTextSize('8pt')

        color = FAMILY_COLORS[k % len(FAMILY_COLORS)]
        fam_name = f'Fam {k+1}'

        self._fam_data[k] = {
            'x': [], 'y': [], 'turn': [], 'energy': [],
            'r': [], 'theta': [], 'z': [], 'pz': [], 'dph': [],
        }

        curves = {}
        curves['xy'] = self.plot_xy.plot(
            [], [], pen=pg.mkPen(color=color, width=0.5),
            name=fam_name)
        curves['energy'] = self.plot_energy.plot(
            [], [], pen=pg.mkPen(color=color, width=1.5),
            clipToView=True, name=fam_name)
        curves['energy'].setDownsampling(auto=True, method='peak')
        curves['rtheta'] = self.plot_rtheta.plot(
            [], [], pen=None, symbol='o', symbolSize=2,
            symbolPen=None, symbolBrush=color,
            clipToView=True, name=fam_name)
        curves['zpz'] = self.plot_zpz.plot(
            [], [], pen=None, symbol='o', symbolSize=2,
            symbolPen=None, symbolBrush=color,
            clipToView=True, name=fam_name)
        curves['rdph'] = self.plot_rdph.plot(
            [], [], pen=None, symbol='o', symbolSize=2,
            symbolPen=None, symbolBrush=color,
            clipToView=True, name=fam_name)

        self._fam_curves[k] = curves

    def append_data(self, data):
        """Ajoute un point aux buffers sans rafraichir les courbes."""
        k = data.get('family', 0)
        nbrfam = data.get('nbrfam', 1)
        self._ensure_family(k, nbrfam)
        fd = self._fam_data[k]
        fd['x'].append(data['x0_mm'])
        fd['y'].append(data['y0_mm'])
        fd['turn'].append(data['numtou'])
        fd['energy'].append(data['wmevpa'])
        fd['r'].append(data['r0_mm'])
        fd['theta'].append(data['tetnew'])
        fd['z'].append(data['z0_mm'])
        fd['pz'].append(data['tpz'])
        fd['dph'].append(data.get('dph', 0.0))

    def update_plots(self, data):
        """Ajoute un point et rafraichit (compatibilite)."""
        self.append_data(data)
        self._refresh_all_curves()

    def _refresh_all_curves(self):
        """Rafraichit toutes les courbes a partir des buffers."""
        if not self._fam_data:
            return

        for k, fd in self._fam_data.items():
            if not fd['x']:
                continue
            curves = self._fam_curves[k]

            x_arr = np.array(fd['x'], dtype=np.float64)
            y_arr = np.array(fd['y'], dtype=np.float64)

            # XY : filtrer par rmax si defini
            if self.rmax_display > 0:
                mask = ((np.abs(x_arr) > self.rmax_display) |
                        (np.abs(y_arr) > self.rmax_display))
                x_filt = np.where(mask, np.nan, x_arr)
                y_filt = np.where(mask, np.nan, y_arr)
                curves['xy'].setData(x_filt, y_filt, connect='finite')
            else:
                curves['xy'].setData(x_arr, y_arr)

            # Energy
            turn_arr = np.array(fd['turn'], dtype=np.float64)
            energy_arr = np.array(fd['energy'], dtype=np.float64)
            curves['energy'].setData(turn_arr, energy_arr)

            # R-theta
            theta_arr = np.array(fd['theta'], dtype=np.float64)
            r_arr = np.array(fd['r'], dtype=np.float64)
            if self.rmax_rtheta > 0:
                mask_rt = r_arr <= self.rmax_rtheta
                curves['rtheta'].setData(theta_arr[mask_rt], r_arr[mask_rt])
            else:
                curves['rtheta'].setData(theta_arr, r_arr)

            # Z-Pz
            z_arr = np.array(fd['z'], dtype=np.float64)
            pz_arr = np.array(fd['pz'], dtype=np.float64)
            curves['zpz'].setData(z_arr, pz_arr)

            # R-dphi
            dph_arr = np.array(fd['dph'], dtype=np.float64)
            if self.rmax_rdph > 0:
                mask_rdph = r_arr <= self.rmax_rdph
                curves['rdph'].setData(r_arr[mask_rdph], dph_arr[mask_rdph])
            else:
                curves['rdph'].setData(r_arr, dph_arr)

        # Ranges globaux (une seule fois apres toutes les familles)
        if self.rmax_display > 0:
            self.plot_xy.setXRange(-self.rmax_display, self.rmax_display,
                                   padding=0)
            self.plot_xy.setYRange(-self.rmax_display, self.rmax_display,
                                   padding=0)
        if self.rmax_rtheta > 0:
            self.plot_rtheta.setYRange(0, self.rmax_rtheta, padding=0.02)
        if self.rmax_rdph > 0:
            self.plot_rdph.setXRange(0, self.rmax_rdph, padding=0.02)

    def clear_plots(self):
        """Efface toutes les donnees des plots."""
        # Supprimer les items deflecteurs
        for item in self._deflector_items:
            self.plot_xy.removeItem(item)
        self._deflector_items.clear()

        # Supprimer les courbes des plots
        for k, curves in self._fam_curves.items():
            self.plot_xy.removeItem(curves['xy'])
            self.plot_energy.removeItem(curves['energy'])
            self.plot_rtheta.removeItem(curves['rtheta'])
            self.plot_zpz.removeItem(curves['zpz'])
            self.plot_rdph.removeItem(curves['rdph'])
        self._fam_data.clear()
        self._fam_curves.clear()

        # Supprimer les legendes
        for plot in [self.plot_xy, self.plot_energy,
                     self.plot_rtheta, self.plot_zpz, self.plot_rdph]:
            if getattr(plot, 'legend', None) is not None:
                try:
                    plot.legend.clear()
                    scene = plot.legend.scene()
                    if scene is not None:
                        scene.removeItem(plot.legend)
                except Exception:
                    pass
                plot.legend = None
            plot.enableAutoRange()
        self._legends_added = False

    def reset_zoom(self):
        """Reinitialise le zoom sur tous les plots."""
        for plot in [self.plot_xy, self.plot_energy,
                     self.plot_rtheta, self.plot_zpz, self.plot_rdph]:
            plot.enableAutoRange()
        if self.rmax_display > 0:
            self.plot_xy.setXRange(-self.rmax_display, self.rmax_display,
                                   padding=0)
            self.plot_xy.setYRange(-self.rmax_display, self.rmax_display,
                                   padding=0)
        if self.rmax_rtheta > 0:
            self.plot_rtheta.setYRange(0, self.rmax_rtheta, padding=0.02)
        if self.rmax_rdph > 0:
            self.plot_rdph.setXRange(0, self.rmax_rdph, padding=0.02)

    def draw_deflectors(self, defl_list):
        """Dessine les deflecteurs sur le plot XY.

        defl_list : list of dicts, chaque dict contient :
            rdf_m, xdfi_m, ydfi_m, xdfo_m, ydfo_m, tetdfi_deg, tetdfo_deg
        """
        # Supprimer les items precedents
        for item in self._deflector_items:
            self.plot_xy.removeItem(item)
        self._deflector_items.clear()

        if not defl_list:
            return

        defl_color = '#e53935'
        defl_pen = pg.mkPen(color=defl_color, width=2.5)
        defl_pen_dash = pg.mkPen(color=defl_color, width=1.5, style=Qt.DashLine)

        for idx, defl in enumerate(defl_list):
            rdf_mm = defl['rdf_m'] * 1000.0
            xdfi_mm = defl['xdfi_m'] * 1000.0
            ydfi_mm = defl['ydfi_m'] * 1000.0
            xdfo_mm = defl['xdfo_m'] * 1000.0
            ydfo_mm = defl['ydfo_m'] * 1000.0
            tetdfi_deg = defl['tetdfi_deg']
            tetdfo_deg = defl['tetdfo_deg']

            # Angles en radians, gerer le wrap-around
            a1 = tetdfi_deg % 360
            a2 = tetdfo_deg % 360
            if a2 <= a1:
                a2 += 360
            a1_rad = np.radians(a1)
            a2_rad = np.radians(a2)

            ext = rdf_mm * 0.15  # extension radiale (15%)

            # -- Arc interieur a rdf --
            angles = np.linspace(a1_rad, a2_rad, 100)
            arc_x = rdf_mm * np.cos(angles)
            arc_y = rdf_mm * np.sin(angles)
            item = self.plot_xy.plot(arc_x, arc_y, pen=defl_pen)
            self._deflector_items.append(item)

            # -- Paroi d'entree --
            cos_a1 = np.cos(a1_rad)
            sin_a1 = np.sin(a1_rad)
            # Trouver t_start : intersection de la droite avec le cercle rdf
            b_in = xdfi_mm * cos_a1 + ydfi_mm * sin_a1
            c_in = xdfi_mm**2 + ydfi_mm**2 - rdf_mm**2
            disc_in = b_in**2 - c_in
            if disc_in >= 0:
                t_start_in = -b_in + np.sqrt(disc_in)
            else:
                t_start_in = rdf_mm  # fallback
            t_end_in = t_start_in + ext
            x_in = [xdfi_mm + t_start_in * cos_a1,
                     xdfi_mm + t_end_in * cos_a1]
            y_in = [ydfi_mm + t_start_in * sin_a1,
                     ydfi_mm + t_end_in * sin_a1]
            item = self.plot_xy.plot(x_in, y_in, pen=defl_pen)
            self._deflector_items.append(item)

            # -- Paroi de sortie --
            cos_a2 = np.cos(a2_rad)
            sin_a2 = np.sin(a2_rad)
            b_out = xdfo_mm * cos_a2 + ydfo_mm * sin_a2
            c_out = xdfo_mm**2 + ydfo_mm**2 - rdf_mm**2
            disc_out = b_out**2 - c_out
            if disc_out >= 0:
                t_start_out = -b_out + np.sqrt(disc_out)
            else:
                t_start_out = rdf_mm
            t_end_out = t_start_out + ext
            x_out = [xdfo_mm + t_start_out * cos_a2,
                      xdfo_mm + t_end_out * cos_a2]
            y_out = [ydfo_mm + t_start_out * sin_a2,
                      ydfo_mm + t_end_out * sin_a2]
            item = self.plot_xy.plot(x_out, y_out, pen=defl_pen)
            self._deflector_items.append(item)

            # -- Arc exterieur (ferme le contour) --
            outer_x = (rdf_mm + ext) * np.cos(angles)
            outer_y = (rdf_mm + ext) * np.sin(angles)
            item = self.plot_xy.plot(outer_x, outer_y, pen=defl_pen_dash)
            self._deflector_items.append(item)

            # -- Label --
            mid_angle = (a1_rad + a2_rad) / 2.0
            label_r = rdf_mm + ext + 40
            label = pg.TextItem(
                f'Defl. {idx + 1}', color=defl_color, anchor=(0.5, 0.5))
            label.setFont(QFont('sans-serif', 9, QFont.Bold))
            label.setPos(label_r * np.cos(mid_angle),
                         label_r * np.sin(mid_angle))
            self.plot_xy.addItem(label)
            self._deflector_items.append(label)

    def export_image(self, path, dpi=150):
        """Exporte les plots en image."""
        if path.lower().endswith('.svg'):
            from pyqtgraph.exporters import SVGExporter
            exporter = SVGExporter(self.graphics_widget.scene())
            exporter.export(path)
        elif path.lower().endswith('.pdf'):
            from PyQt5.QtPrintSupport import QPrinter
            from PyQt5.QtGui import QPainter
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(path)
            painter = QPainter(printer)
            self.graphics_widget.render(painter)
            painter.end()
        else:
            width = int(10 * dpi)
            height = int(8 * dpi)
            pixmap = self.graphics_widget.grab()
            scaled = pixmap.scaled(width, height,
                                   Qt.KeepAspectRatio,
                                   Qt.SmoothTransformation)
            scaled.save(path)


class _ToolbarShim:
    """Shim de compatibilite pour toolbar.home()."""

    def __init__(self, canvas):
        self._canvas = canvas

    def home(self):
        self._canvas.reset_zoom()


class _FigShim:
    """Shim de compatibilite pour fig.savefig()."""

    def __init__(self, canvas):
        self._canvas = canvas

    def savefig(self, path, dpi=150, bbox_inches='tight'):
        self._canvas.export_image(path, dpi=dpi)


class PlotWidget(QWidget):
    """Widget combinant le canvas pyqtgraph et les controles de navigation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #f0f2f5;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self.canvas = PlotCanvas(self)
        self.toolbar = _ToolbarShim(self.canvas)

        # Barre de controle
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setContentsMargins(4, 0, 4, 0)

        btn_style = (
            "QPushButton { color: #1a1a2e; background: #f0f4fa; "
            "  border: 1px solid #aab5c8; border-radius: 3px; "
            "  padding: 3px 8px; font-weight: bold; font-size: 10px; }"
            "QPushButton:hover { background: #c0d0f0; }"
            "QPushButton:pressed { background: #a0b8e0; }"
        )

        btn_home = QPushButton("\u2922 Unzoom")
        btn_home.setToolTip("Reinitialiser le zoom sur tous les plots")
        btn_home.setStyleSheet(btn_style)
        btn_home.clicked.connect(self.canvas.reset_zoom)
        ctrl_layout.addWidget(btn_home)

        ctrl_layout.addSpacing(12)

        lbl = QLabel("R max (mm) :")
        lbl.setStyleSheet("color: #2c3e50; font-weight: bold; font-size: 10px;")
        ctrl_layout.addWidget(lbl)

        self.rmax_spin = QDoubleSpinBox()
        self.rmax_spin.setRange(0, 1e8)
        self.rmax_spin.setDecimals(0)
        self.rmax_spin.setValue(3000)
        self.rmax_spin.setSpecialValueText("Auto")
        self.rmax_spin.setSingleStep(500)
        self.rmax_spin.setToolTip("0 = auto. Ajustez pour voir l'extraction.")
        self.rmax_spin.setStyleSheet(
            "QDoubleSpinBox { background: #ffffff; color: #1565C0; "
            "  border: 1px solid #aab5c8; border-radius: 3px; padding: 2px 6px; "
            "  font-weight: bold; }"
            "QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { "
            "  background: #e0e8f0; border: 1px solid #aab5c8; }"
        )
        self.rmax_spin.valueChanged.connect(self._on_rmax_changed)
        ctrl_layout.addWidget(self.rmax_spin)

        self.auto_check = QCheckBox("Auto")
        self.auto_check.setChecked(False)
        self.auto_check.setStyleSheet(
            "QCheckBox { color: #2c3e50; font-size: 10px; }"
            "QCheckBox::indicator { width: 14px; height: 14px; }"
        )
        self.auto_check.toggled.connect(self._on_auto_toggled)
        ctrl_layout.addWidget(self.auto_check)

        ctrl_layout.addSpacing(20)

        # --- R max pour R-theta ---
        lbl_rt = QLabel("R max R-\u03b8 (mm) :")
        lbl_rt.setStyleSheet("color: #2c3e50; font-weight: bold; font-size: 10px;")
        ctrl_layout.addWidget(lbl_rt)

        self.rmax_rtheta_spin = QDoubleSpinBox()
        self.rmax_rtheta_spin.setRange(0, 1e8)
        self.rmax_rtheta_spin.setDecimals(0)
        self.rmax_rtheta_spin.setValue(3000)
        self.rmax_rtheta_spin.setSpecialValueText("Auto")
        self.rmax_rtheta_spin.setSingleStep(500)
        self.rmax_rtheta_spin.setToolTip(
            "0 = auto (pas de filtre). Filtre les points R > cette valeur sur le plot R-\u03b8.")
        self.rmax_rtheta_spin.setStyleSheet(
            "QDoubleSpinBox { background: #ffffff; color: #2e7d32; "
            "  border: 1px solid #aab5c8; border-radius: 3px; padding: 2px 6px; "
            "  font-weight: bold; }"
            "QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { "
            "  background: #e0e8f0; border: 1px solid #aab5c8; }"
        )
        self.rmax_rtheta_spin.valueChanged.connect(self._on_rmax_rtheta_changed)
        ctrl_layout.addWidget(self.rmax_rtheta_spin)

        self.auto_rtheta_check = QCheckBox("Auto")
        self.auto_rtheta_check.setChecked(False)
        self.auto_rtheta_check.setStyleSheet(
            "QCheckBox { color: #2c3e50; font-size: 10px; }"
            "QCheckBox::indicator { width: 14px; height: 14px; }"
        )
        self.auto_rtheta_check.toggled.connect(self._on_auto_rtheta_toggled)
        ctrl_layout.addWidget(self.auto_rtheta_check)

        ctrl_layout.addSpacing(20)

        # --- R max pour R-dphi ---
        lbl_rdph = QLabel("R max R-d\u03c6 (mm) :")
        lbl_rdph.setStyleSheet("color: #2c3e50; font-weight: bold; font-size: 10px;")
        ctrl_layout.addWidget(lbl_rdph)

        self.rmax_rdph_spin = QDoubleSpinBox()
        self.rmax_rdph_spin.setRange(0, 1e8)
        self.rmax_rdph_spin.setDecimals(0)
        self.rmax_rdph_spin.setValue(3000)
        self.rmax_rdph_spin.setSpecialValueText("Auto")
        self.rmax_rdph_spin.setSingleStep(500)
        self.rmax_rdph_spin.setToolTip(
            "0 = auto (pas de filtre). Filtre les points R > cette valeur sur le plot R-d\u03c6.")
        self.rmax_rdph_spin.setStyleSheet(
            "QDoubleSpinBox { background: #ffffff; color: #2e7d32; "
            "  border: 1px solid #aab5c8; border-radius: 3px; padding: 2px 6px; "
            "  font-weight: bold; }"
            "QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { "
            "  background: #e0e8f0; border: 1px solid #aab5c8; }"
        )
        self.rmax_rdph_spin.valueChanged.connect(self._on_rmax_rdph_changed)
        ctrl_layout.addWidget(self.rmax_rdph_spin)

        self.auto_rdph_check = QCheckBox("Auto")
        self.auto_rdph_check.setChecked(False)
        self.auto_rdph_check.setStyleSheet(
            "QCheckBox { color: #2c3e50; font-size: 10px; }"
            "QCheckBox::indicator { width: 14px; height: 14px; }"
        )
        self.auto_rdph_check.toggled.connect(self._on_auto_rdph_toggled)
        ctrl_layout.addWidget(self.auto_rdph_check)

        ctrl_layout.addStretch()

        layout.addLayout(ctrl_layout)
        layout.addWidget(self.canvas)

        # Appliquer les valeurs initiales
        self.canvas.rmax_display = 3000.0
        self.canvas.rmax_rtheta = 3000.0
        self.canvas.rmax_rdph = 3000.0

    def _on_rmax_changed(self, val):
        self.canvas.rmax_display = val
        self.canvas._refresh_all_curves()

    def _on_auto_toggled(self, checked):
        if checked:
            self.rmax_spin.setValue(0)
        else:
            self.rmax_spin.setValue(3000)

    def _on_rmax_rtheta_changed(self, val):
        self.canvas.rmax_rtheta = val
        self.canvas._refresh_all_curves()

    def _on_auto_rtheta_toggled(self, checked):
        if checked:
            self.rmax_rtheta_spin.setValue(0)
        else:
            self.rmax_rtheta_spin.setValue(3000)

    def _on_rmax_rdph_changed(self, val):
        self.canvas.rmax_rdph = val
        self.canvas._refresh_all_curves()

    def _on_auto_rdph_toggled(self, checked):
        if checked:
            self.rmax_rdph_spin.setValue(0)
        else:
            self.rmax_rdph_spin.setValue(3000)


class Plot3DWindow(QDialog):
    """Fenetre separee pour la vue 3D des trajectoires."""

    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LIONS - Vue 3D")
        self.resize(600, 450)
        self.canvas = canvas  # reference au PlotCanvas pour acceder aux donnees
        self.z_scale = 200.0
        self.rmax_display = 0.0
        self._3d_items = {}
        self._defl_3d_items = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        if not HAS_GL:
            lbl = QLabel("PyOpenGL non disponible.\n"
                         "Installez-le avec : pip install PyOpenGL")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: #c62828; font-size: 14px; font-weight: bold;")
            layout.addWidget(lbl)
            return

        # Controles
        ctrl = QHBoxLayout()
        ctrl.setContentsMargins(4, 0, 4, 0)

        lbl_z = QLabel("Z scale :")
        lbl_z.setStyleSheet("color: #2c3e50; font-weight: bold; font-size: 11px;")
        ctrl.addWidget(lbl_z)

        self.z_scale_spin = QSpinBox()
        self.z_scale_spin.setRange(1, 10000)
        self.z_scale_spin.setValue(200)
        self.z_scale_spin.setSingleStep(50)
        self.z_scale_spin.setSuffix("x")
        self.z_scale_spin.setToolTip(
            "Facteur d'amplification Z (Z est tres petit par rapport a X/Y)")
        self.z_scale_spin.setStyleSheet(
            "QSpinBox { background: #ffffff; color: #7b1fa2; "
            "  border: 1px solid #aab5c8; border-radius: 3px; "
            "  padding: 2px 6px; font-weight: bold; font-size: 11px; }"
            "QSpinBox::up-button, QSpinBox::down-button { "
            "  background: #e0e8f0; border: 1px solid #aab5c8; }"
        )
        self.z_scale_spin.valueChanged.connect(self._on_z_scale_changed)
        ctrl.addWidget(self.z_scale_spin)

        ctrl.addSpacing(20)

        btn_export = QPushButton("\u2913 Exporter")
        btn_export.setToolTip("Sauvegarder la vue 3D en image PNG")
        btn_export.setStyleSheet(
            "QPushButton { color: #1a1a2e; background: #f0f4fa; "
            "  border: 1px solid #aab5c8; border-radius: 3px; "
            "  padding: 3px 10px; font-weight: bold; font-size: 10px; }"
            "QPushButton:hover { background: #c0d0f0; }")
        btn_export.clicked.connect(self._on_export)
        ctrl.addWidget(btn_export)

        ctrl.addSpacing(20)

        _spin_style = (
            "QDoubleSpinBox { background: #ffffff; color: #1565C0; "
            "  border: 1px solid #aab5c8; border-radius: 3px; "
            "  padding: 2px 4px; font-weight: bold; font-size: 10px; "
            "  min-width: 60px; }"
            "QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { "
            "  background: #e0e8f0; border: 1px solid #aab5c8; }")

        lbl_rmin = QLabel("Rmin:")
        lbl_rmin.setStyleSheet("color: #2c3e50; font-weight: bold; font-size: 10px;")
        ctrl.addWidget(lbl_rmin)

        self.rmin_3d_spin = QDoubleSpinBox()
        self.rmin_3d_spin.setRange(0, 9999)
        self.rmin_3d_spin.setValue(0)
        self.rmin_3d_spin.setSingleStep(100)
        self.rmin_3d_spin.setSuffix(" mm")
        self.rmin_3d_spin.setToolTip("Rayon minimum affiche (0 = pas de limite)")
        self.rmin_3d_spin.setStyleSheet(_spin_style)
        self.rmin_3d_spin.valueChanged.connect(self._on_range_changed)
        ctrl.addWidget(self.rmin_3d_spin)

        lbl_rmax = QLabel("Rmax:")
        lbl_rmax.setStyleSheet("color: #2c3e50; font-weight: bold; font-size: 10px;")
        ctrl.addWidget(lbl_rmax)

        self.rmax_3d_spin = QDoubleSpinBox()
        self.rmax_3d_spin.setRange(0, 9999)
        self.rmax_3d_spin.setValue(0)
        self.rmax_3d_spin.setSingleStep(100)
        self.rmax_3d_spin.setSuffix(" mm")
        self.rmax_3d_spin.setToolTip("Rayon maximum affiche (0 = pas de limite)")
        self.rmax_3d_spin.setStyleSheet(_spin_style)
        self.rmax_3d_spin.valueChanged.connect(self._on_range_changed)
        ctrl.addWidget(self.rmax_3d_spin)

        ctrl.addStretch()
        layout.addLayout(ctrl)

        # Titre
        title = QLabel("Z = f(X, Y)")
        title.setAlignment(Qt.AlignCenter)
        title.setFixedHeight(22)
        title.setStyleSheet(
            "color: #1a1a2e; font-size: 12px; font-weight: bold; "
            "margin: 0px; padding: 0px;")
        layout.addWidget(title)

        # Vue 3D OpenGL
        self._gl_widget = gl.GLViewWidget()
        self._gl_widget.setBackgroundColor('#ffffff')
        self._gl_widget.opts['distance'] = 4000
        self._gl_widget.opts['elevation'] = 25
        self._gl_widget.opts['azimuth'] = -45

        # Grille au plan z=0
        grid = gl.GLGridItem()
        grid.setSize(4000, 4000, 0)
        grid.setSpacing(500, 500, 1)
        grid.setColor((200, 208, 220, 80))
        self._gl_widget.addItem(grid)

        # Axes X(rouge), Y(vert), Z(bleu)
        axis = gl.GLAxisItem()
        axis.setSize(2000, 2000, 1000)
        self._gl_widget.addItem(axis)

        # Labels d'axes
        lbl_x = gl.GLTextItem(pos=np.array([2100, 0, 0]),
                               text='X (mm)', color=(200, 0, 0, 255))
        lbl_x.setData(font=QFont('sans-serif', 10, QFont.Bold))
        self._gl_widget.addItem(lbl_x)

        lbl_y = gl.GLTextItem(pos=np.array([0, 2100, 0]),
                               text='Y (mm)', color=(0, 150, 0, 255))
        lbl_y.setData(font=QFont('sans-serif', 10, QFont.Bold))
        self._gl_widget.addItem(lbl_y)

        lbl_z = gl.GLTextItem(pos=np.array([0, 0, 1100]),
                               text='Z (mm)', color=(0, 0, 200, 255))
        lbl_z.setData(font=QFont('sans-serif', 10, QFont.Bold))
        self._gl_widget.addItem(lbl_z)

        layout.addWidget(self._gl_widget)

        # --- Zoom rectangulaire (clic droit) ---
        self._rect_start = None
        self._rubber_band = None
        self._gl_widget.installEventFilter(self)

    # ---- Event filter pour le zoom rectangulaire ----
    def eventFilter(self, obj, event):
        if obj is not self._gl_widget:
            return super().eventFilter(obj, event)

        etype = event.type()

        # Clic droit enfonce -> debut de la selection
        if etype == QEvent.MouseButtonPress and event.button() == Qt.RightButton:
            self._rect_start = event.pos()
            self._rubber_band = QRubberBand(QRubberBand.Rectangle, self._gl_widget)
            self._rubber_band.setGeometry(QRect(self._rect_start, QSize()))
            self._rubber_band.show()
            return True

        # Deplacement pendant la selection
        if etype == QEvent.MouseMove and self._rect_start is not None:
            self._rubber_band.setGeometry(
                QRect(self._rect_start, event.pos()).normalized())
            return True

        # Relachement du clic droit -> appliquer le zoom
        if (etype == QEvent.MouseButtonRelease
                and event.button() == Qt.RightButton
                and self._rect_start is not None):
            rect = QRect(self._rect_start, event.pos()).normalized()
            self._rubber_band.hide()
            self._rubber_band = None
            self._rect_start = None
            self._apply_rect_zoom(rect)
            return True

        # Double-clic droit -> reinitialiser la vue
        if (etype == QEvent.MouseButtonDblClick
                and event.button() == Qt.RightButton):
            self._reset_3d_view()
            return True

        return super().eventFilter(obj, event)

    def _apply_rect_zoom(self, rect):
        """Zoom la vue 3D sur la zone rectangulaire selectionnee."""
        if rect.width() < 10 or rect.height() < 10:
            return  # selection trop petite, on ignore

        w = self._gl_widget.width()
        h = self._gl_widget.height()

        # Facteur de zoom = taille widget / taille selection
        zoom_x = w / max(rect.width(), 1)
        zoom_y = h / max(rect.height(), 1)
        zoom = min(zoom_x, zoom_y)

        # Reduire la distance camera (= zoom avant)
        dist = self._gl_widget.opts['distance']
        new_dist = dist / zoom
        self._gl_widget.opts['distance'] = new_dist

        # Deplacer le centre de la camera vers le centre de la selection
        cx_offset = rect.center().x() - w / 2.0   # pixels depuis le centre
        cy_offset = rect.center().y() - h / 2.0

        fov = self._gl_widget.opts.get('fov', 60)
        px_scale = 2.0 * dist * np.tan(np.radians(fov / 2.0)) / h

        elev = np.radians(self._gl_widget.opts['elevation'])
        azim = np.radians(self._gl_widget.opts['azimuth'])

        # Vecteur "droite" dans l'espace monde
        rx = -np.sin(azim)
        ry = np.cos(azim)

        # Vecteur "haut" dans l'espace monde
        ux = -np.cos(azim) * np.sin(elev)
        uy = -np.sin(azim) * np.sin(elev)
        uz = np.cos(elev)

        dx = cx_offset * px_scale
        dy = -cy_offset * px_scale  # Y ecran inverse

        center = self._gl_widget.opts['center']
        self._gl_widget.opts['center'] = QVector3D(
            center.x() + dx * rx + dy * ux,
            center.y() + dx * ry + dy * uy,
            center.z() + dy * uz)

        self._gl_widget.update()

    def _reset_3d_view(self):
        """Reinitialise la vue 3D (double-clic droit)."""
        self._gl_widget.opts['distance'] = 4000
        self._gl_widget.opts['elevation'] = 25
        self._gl_widget.opts['azimuth'] = -45
        self._gl_widget.opts['center'] = QVector3D(0, 0, 0)
        self._gl_widget.update()

    def _on_z_scale_changed(self, val):
        self.z_scale = float(val)
        self.refresh_3d()

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter la vue 3D", "lions_3d.png",
            "PNG (*.png);;JPEG (*.jpg)")
        if path:
            pixmap = self._gl_widget.grabFramebuffer()
            pixmap.save(path)
            self.setWindowTitle(f"LIONS - Vue 3D  [Exporte: {path}]")

    def _on_range_changed(self, _=None):
        self.refresh_3d()

    def refresh_3d(self):
        """Rafraichit les courbes 3D a partir des donnees du PlotCanvas."""
        if not HAS_GL:
            return
        fam_data = self.canvas._fam_data

        # Limites de rayon depuis les spinboxes
        rmin_disp = self.rmin_3d_spin.value()
        rmax_disp = self.rmax_3d_spin.value()

        for k, fd in fam_data.items():
            if not fd['x'] or len(fd['x']) < 2:
                continue

            # Creer la courbe 3D si elle n'existe pas
            if k not in self._3d_items:
                color = FAMILY_COLORS[k % len(FAMILY_COLORS)]
                c = QColor(color)
                gl_color = (c.redF(), c.greenF(), c.blueF(), 1.0)
                line_3d = gl.GLLinePlotItem(
                    pos=np.zeros((1, 3)), color=gl_color,
                    width=1.5, antialias=True)
                self._gl_widget.addItem(line_3d)
                self._3d_items[k] = line_3d

            x_arr = np.array(fd['x'], dtype=np.float64)
            y_arr = np.array(fd['y'], dtype=np.float64)
            z_arr = np.array(fd['z'], dtype=np.float64)
            z_scaled = z_arr * self.z_scale
            pos = np.column_stack([x_arr, y_arr, z_scaled])

            # Filtrer par rayon (Rmin / Rmax)
            r2 = x_arr**2 + y_arr**2
            valid = np.ones(len(r2), dtype=bool)
            if rmin_disp > 0:
                valid &= r2 >= rmin_disp**2
            if rmax_disp > 0:
                valid &= r2 <= rmax_disp**2
            pos = pos[valid]

            if len(pos) > 1:
                self._3d_items[k].setData(pos=pos)
            elif k in self._3d_items:
                self._3d_items[k].setData(pos=np.zeros((1, 3)))

    def clear_3d(self):
        """Efface toutes les courbes 3D."""
        if not HAS_GL:
            return
        for k, item in self._3d_items.items():
            self._gl_widget.removeItem(item)
        self._3d_items.clear()

    def draw_deflectors_3d(self, defl_list):
        """Dessine les deflecteurs dans la vue 3D au plan z=0.

        defl_list : list of dicts (meme format que PlotCanvas.draw_deflectors)
        """
        if not HAS_GL:
            return
        # Supprimer les items precedents
        for item in self._defl_3d_items:
            self._gl_widget.removeItem(item)
        self._defl_3d_items.clear()

        if not defl_list:
            return

        defl_color = (0.9, 0.22, 0.21, 1.0)  # rouge #e53935

        for defl in defl_list:
            rdf_mm = defl['rdf_m'] * 1000.0
            xdfi_mm = defl['xdfi_m'] * 1000.0
            ydfi_mm = defl['ydfi_m'] * 1000.0
            xdfo_mm = defl['xdfo_m'] * 1000.0
            ydfo_mm = defl['ydfo_m'] * 1000.0
            tetdfi_deg = defl['tetdfi_deg']
            tetdfo_deg = defl['tetdfo_deg']

            a1 = tetdfi_deg % 360
            a2 = tetdfo_deg % 360
            if a2 <= a1:
                a2 += 360
            a1_rad = np.radians(a1)
            a2_rad = np.radians(a2)

            ext = rdf_mm * 0.15

            # Arc interieur a rdf
            angles = np.linspace(a1_rad, a2_rad, 100)
            arc_x = rdf_mm * np.cos(angles)
            arc_y = rdf_mm * np.sin(angles)
            arc_z = np.zeros_like(arc_x)
            pos_arc = np.column_stack([arc_x, arc_y, arc_z])
            item = gl.GLLinePlotItem(pos=pos_arc, color=defl_color,
                                     width=2.5, antialias=True)
            self._gl_widget.addItem(item)
            self._defl_3d_items.append(item)

            # Paroi d'entree
            cos_a1 = np.cos(a1_rad)
            sin_a1 = np.sin(a1_rad)
            b_in = xdfi_mm * cos_a1 + ydfi_mm * sin_a1
            c_in = xdfi_mm**2 + ydfi_mm**2 - rdf_mm**2
            disc_in = b_in**2 - c_in
            t_start_in = -b_in + np.sqrt(max(disc_in, 0)) if disc_in >= 0 else rdf_mm
            t_end_in = t_start_in + ext
            wall_in = np.array([
                [xdfi_mm + t_start_in * cos_a1, ydfi_mm + t_start_in * sin_a1, 0],
                [xdfi_mm + t_end_in * cos_a1, ydfi_mm + t_end_in * sin_a1, 0],
            ])
            item = gl.GLLinePlotItem(pos=wall_in, color=defl_color,
                                     width=2.5, antialias=True)
            self._gl_widget.addItem(item)
            self._defl_3d_items.append(item)

            # Paroi de sortie
            cos_a2 = np.cos(a2_rad)
            sin_a2 = np.sin(a2_rad)
            b_out = xdfo_mm * cos_a2 + ydfo_mm * sin_a2
            c_out = xdfo_mm**2 + ydfo_mm**2 - rdf_mm**2
            disc_out = b_out**2 - c_out
            t_start_out = -b_out + np.sqrt(max(disc_out, 0)) if disc_out >= 0 else rdf_mm
            t_end_out = t_start_out + ext
            wall_out = np.array([
                [xdfo_mm + t_start_out * cos_a2, ydfo_mm + t_start_out * sin_a2, 0],
                [xdfo_mm + t_end_out * cos_a2, ydfo_mm + t_end_out * sin_a2, 0],
            ])
            item = gl.GLLinePlotItem(pos=wall_out, color=defl_color,
                                     width=2.5, antialias=True)
            self._gl_widget.addItem(item)
            self._defl_3d_items.append(item)

            # Arc exterieur (pointille simule par segments)
            outer_x = (rdf_mm + ext) * np.cos(angles)
            outer_y = (rdf_mm + ext) * np.sin(angles)
            outer_z = np.zeros_like(outer_x)
            pos_outer = np.column_stack([outer_x, outer_y, outer_z])
            item = gl.GLLinePlotItem(
                pos=pos_outer,
                color=(0.9, 0.22, 0.21, 0.5),  # semi-transparent
                width=1.5, antialias=True)
            self._gl_widget.addItem(item)
            self._defl_3d_items.append(item)

