"""
lions_field_viewer.py - Visualiseur des champs magnetiques et electriques
Lit les fichiers de cartes de champ et affiche en 2D/3D.
"""

import os
import struct
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from mpl_toolkits.mplot3d import Axes3D
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QPushButton, QFileDialog, QComboBox, QLabel, QCheckBox,
    QLineEdit, QGroupBox, QMessageBox
)
from PyQt5.QtCore import Qt


# --- Utilitaires de lecture (repliques de lions.py) ---

def _fortran_float(s):
    return float(s.replace('d', 'e').replace('D', 'e'))


def _read_tokens(f, n, buffer):
    """Lit n tokens depuis un fichier texte, sur plusieurs lignes si necessaire."""
    while len(buffer) < n:
        line = f.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        buffer.extend(line.split())
    result = buffer[:n]
    del buffer[:n]
    return result


# --- Lecture des fichiers ---

def read_magnetic_field(filepath, swap='n'):
    """Lit une carte de champ magnetique et retourne les tableaux."""
    tbz = np.zeros((250, 721), dtype=np.float64)
    d2bz = np.zeros((250, 721), dtype=np.float64)
    dbzx = np.zeros((250, 721), dtype=np.float64)
    dbzy = np.zeros((250, 721), dtype=np.float64)
    dbzxlu = np.zeros((250, 91), dtype=np.float64)
    dbzylu = np.zeros((250, 91), dtype=np.float64)

    buf = []
    with open(filepath, 'r') as f:
        title = f.readline().strip()
        vals = f.readline().split()
        rmin = _fortran_float(vals[0])
        rmax = _fortran_float(vals[1])
        nr = int(vals[2])
        ntet = int(vals[3])

        if ntet != 91:
            # Carte complete
            for i in range(nr):
                tokens = _read_tokens(f, ntet, buf)
                for j in range(ntet):
                    tbz[i, j] = _fortran_float(tokens[j])
            for i in range(nr):
                tokens = _read_tokens(f, ntet, buf)
                for j in range(ntet):
                    d2bz[i, j] = _fortran_float(tokens[j])
            for i in range(nr):
                tokens = _read_tokens(f, ntet, buf)
                for j in range(ntet):
                    dbzx[i, j] = _fortran_float(tokens[j])
            for i in range(nr):
                tokens = _read_tokens(f, ntet, buf)
                for j in range(ntet):
                    dbzy[i, j] = _fortran_float(tokens[j])
            htet = 2.0 * np.pi / (ntet - 1.0)
            ntetall = ntet
        else:
            # Carte TOSCA 1/8 symetrie
            for i in range(nr):
                tokens = _read_tokens(f, ntet, buf)
                for j in range(ntet):
                    tbz[i, 91 - j] = _fortran_float(tokens[j])
            for i in range(nr):
                tokens = _read_tokens(f, ntet, buf)
                for j in range(ntet):
                    d2bz[i, 91 - j] = _fortran_float(tokens[j])
            try:
                for i in range(nr):
                    tokens = _read_tokens(f, ntet, buf)
                    for j in range(ntet):
                        dbzxlu[i, j] = _fortran_float(tokens[j])
                for i in range(nr):
                    tokens = _read_tokens(f, ntet, buf)
                    for j in range(ntet):
                        dbzylu[i, j] = _fortran_float(tokens[j])
            except Exception:
                dbzxlu[:] = 0
                dbzylu[:] = 0

            # Expansion des symetries
            tbz[:nr, 180:91:-1] = tbz[:nr, :89]
            tbz[:nr, 181:361] = tbz[:nr, 1:181]
            tbz[:nr, 361:721] = tbz[:nr, 1:361]
            d2bz[:nr, 180:91:-1] = d2bz[:nr, :89]
            d2bz[:nr, 181:361] = d2bz[:nr, 1:181]
            d2bz[:nr, 361:721] = d2bz[:nr, 1:361]

            r2 = np.sqrt(2.0) / 2.0
            dbzx[:nr, 90::-1] = r2 * (dbzxlu[:nr, :91] + dbzylu[:nr, :91])
            dbzy[:nr, 90::-1] = r2 * (dbzxlu[:nr, :91] - dbzylu[:nr, :91])
            dbzx[:nr, 180:91:-1] = dbzy[:nr, :89]
            dbzy[:nr, 180:91:-1] = dbzx[:nr, :89]
            dbzx[:nr, 181:361] = -dbzx[:nr, 179::-1]
            dbzy[:nr, 181:361] = dbzy[:nr, 179::-1]
            dbzx[:nr, 361:721] = dbzx[:nr, 359::-1]
            dbzy[:nr, 361:721] = -dbzy[:nr, 359::-1]
            htet = np.pi / 4.0 / (ntet - 1.0)
            ntetall = 721

    hr = (rmax - rmin) / (nr - 1.0)

    return {
        'title': title, 'rmin': rmin, 'rmax': rmax,
        'nr': nr, 'ntet': ntet, 'ntetall': ntetall,
        'hr': hr, 'htet': htet,
        'tbz': tbz[:nr, :ntetall],
        'd2bz': d2bz[:nr, :ntetall],
        'dbzx': dbzx[:nr, :ntetall],
        'dbzy': dbzy[:nr, :ntetall],
    }


def _try_read_pot_central(filepath, fdtype, idtype):
    """Tente de lire le header du potentiel central avec un endianness donne."""
    with open(filepath, 'rb') as f:
        f.read(4)  # record marker
        header_floats = np.frombuffer(f.read(32), dtype=fdtype)
        header_ints = np.frombuffer(f.read(8), dtype=idtype)
        xmin = float(header_floats[0]) / 1000.0
        xmax = float(header_floats[1]) / 1000.0
        ymin = float(header_floats[2]) / 1000.0
        ymax = float(header_floats[3]) / 1000.0
        nx = int(header_ints[0])
        ny = int(header_ints[1])
    return xmin, xmax, ymin, ymax, nx, ny


def read_potential_central(filepath, swap='n'):
    """Lit le fichier de potentiel electrique central (binaire Fortran)."""
    if swap == 'y':
        fdtype = np.dtype(np.float64).newbyteorder('>')
        idtype = np.dtype(np.int32).newbyteorder('>')
    else:
        fdtype = np.float64
        idtype = np.int32

    # Lire le header et verifier les dimensions
    xmin, xmax, ymin, ymax, nx, ny = _try_read_pot_central(filepath, fdtype, idtype)

    # Si les dimensions sont aberrantes, essayer l'autre endianness
    if nx <= 0 or ny <= 0 or nx > 10000 or ny > 10000:
        if swap == 'y':
            fdtype2 = np.float64
            idtype2 = np.int32
        else:
            fdtype2 = np.dtype(np.float64).newbyteorder('>')
            idtype2 = np.dtype(np.int32).newbyteorder('>')
        xmin2, xmax2, ymin2, ymax2, nx2, ny2 = _try_read_pot_central(filepath, fdtype2, idtype2)
        if 0 < nx2 <= 10000 and 0 < ny2 <= 10000:
            fdtype, idtype = fdtype2, idtype2
            xmin, xmax, ymin, ymax, nx, ny = xmin2, xmax2, ymin2, ymax2, nx2, ny2

    if nx <= 0 or ny <= 0 or nx > 10000 or ny > 10000:
        raise ValueError(
            f"Dimensions invalides dans le header : nx={nx}, ny={ny}. "
            f"Verifiez le format du fichier et le parametre byte-swap.")

    with open(filepath, 'rb') as f:
        f.read(4 + 32 + 8 + 4)  # skip header record

        pot = np.zeros((nx, ny), dtype=np.float64)
        d2pot = np.zeros((nx, ny), dtype=np.float64)

        for i in range(nx):
            f.read(4)
            row = np.frombuffer(f.read(ny * 8), dtype=fdtype)
            pot[i, :] = row
            f.read(4)
        try:
            for i in range(nx):
                f.read(4)
                row = np.frombuffer(f.read(ny * 8), dtype=fdtype)
                d2pot[i, :] = row
                f.read(4)
        except Exception:
            d2pot[:] = 0.0

    return {
        'xmin': xmin, 'xmax': xmax, 'ymin': ymin, 'ymax': ymax,
        'nx': nx, 'ny': ny,
        'pot': pot, 'd2pot': d2pot,
    }


def read_potential_peripheral(filepath):
    """Lit le fichier de potentiel electrique peripherique (texte)."""
    buf = []
    with open(filepath, 'r') as f:
        vals = _read_tokens(f, 6, buf)
        xmin = _fortran_float(vals[0])
        xmax = _fortran_float(vals[1])
        ymin = _fortran_float(vals[2])
        ymax = _fortran_float(vals[3])
        nx = int(_fortran_float(vals[4]))
        ny = int(_fortran_float(vals[5]))

        if nx <= 0 or ny <= 0 or nx > 10000 or ny > 10000:
            raise ValueError(
                f"Dimensions invalides : nx={nx}, ny={ny}. "
                f"Verifiez le format du fichier (texte attendu).")

        pot = np.zeros((nx, ny), dtype=np.float64)
        d2pot = np.zeros((nx, ny), dtype=np.float64)

        for i in range(nx):
            tokens = _read_tokens(f, ny, buf)
            for j in range(ny):
                pot[i, j] = _fortran_float(tokens[j])
        for i in range(nx):
            tokens = _read_tokens(f, ny, buf)
            for j in range(ny):
                d2pot[i, j] = _fortran_float(tokens[j])

    return {
        'xmin': xmin, 'xmax': xmax, 'ymin': ymin, 'ymax': ymax,
        'nx': nx, 'ny': ny,
        'pot': pot, 'd2pot': d2pot,
    }


# --- Widget de visualisation ---

class FieldTab(QWidget):
    """Onglet avec un canvas matplotlib et des controles."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.fig.set_facecolor('#f0f2f5')
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)


class FieldViewerDialog(QDialog):
    """Dialogue pour visualiser les champs magnetiques et electriques."""

    def __init__(self, parent=None, ficb='', ficv1='', ficv2='', swap='n'):
        super().__init__(parent)
        self.setWindowTitle("LIONS - Visualiseur des Champs")
        self.setMinimumSize(1000, 700)
        self.mag_data = None
        self.pot1_data = None
        self.pot2_data = None
        self.swap = swap

        layout = QVBoxLayout(self)

        # --- Barre de fichiers ---
        files_group = QGroupBox("Fichiers de champs")
        files_layout = QVBoxLayout(files_group)

        # Champ B
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Champ B :"))
        self.ficb_edit = QLineEdit(ficb)
        row1.addWidget(self.ficb_edit)
        btn_b = QPushButton("...")
        btn_b.setMaximumWidth(30)
        btn_b.clicked.connect(lambda: self._browse(self.ficb_edit, "Carte magnetique (*)"))
        row1.addWidget(btn_b)
        btn_load_b = QPushButton("Charger")
        btn_load_b.clicked.connect(self._load_magnetic)
        row1.addWidget(btn_load_b)
        files_layout.addLayout(row1)

        # Pot central
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Pot. central :"))
        self.ficv1_edit = QLineEdit(ficv1)
        row2.addWidget(self.ficv1_edit)
        btn_v1 = QPushButton("...")
        btn_v1.setMaximumWidth(30)
        btn_v1.clicked.connect(lambda: self._browse(self.ficv1_edit, "Potentiel (*.dat *.bin *)"))
        row2.addWidget(btn_v1)
        btn_load_v1 = QPushButton("Charger")
        btn_load_v1.clicked.connect(self._load_pot_central)
        row2.addWidget(btn_load_v1)
        files_layout.addLayout(row2)

        # Pot peripherique
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Pot. periph. :"))
        self.ficv2_edit = QLineEdit(ficv2)
        row3.addWidget(self.ficv2_edit)
        btn_v2 = QPushButton("...")
        btn_v2.setMaximumWidth(30)
        btn_v2.clicked.connect(lambda: self._browse(self.ficv2_edit, "Potentiel (*.dat *)"))
        row3.addWidget(btn_v2)
        btn_load_v2 = QPushButton("Charger")
        btn_load_v2.clicked.connect(self._load_pot_peripheral)
        row3.addWidget(btn_load_v2)
        files_layout.addLayout(row3)

        layout.addWidget(files_group)

        # --- Controles ---
        ctrl_layout = QHBoxLayout()

        ctrl_layout.addWidget(QLabel("Donnee :"))
        self.field_combo = QComboBox()
        self.field_combo.addItems(['Bz', 'd2Bz', 'dBz/dx', 'dBz/dy',
                                    'Pot. central', 'Pot. periph.',
                                    'd2Pot central', 'd2Pot periph.'])
        self.field_combo.currentIndexChanged.connect(self._replot)
        ctrl_layout.addWidget(self.field_combo)

        ctrl_layout.addWidget(QLabel("Colormap :"))
        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems(['coolwarm', 'viridis', 'jet', 'hot', 'RdBu_r', 'seismic'])
        self.cmap_combo.currentIndexChanged.connect(self._replot)
        ctrl_layout.addWidget(self.cmap_combo)

        self.check_3d = QCheckBox("3D")
        self.check_3d.toggled.connect(self._replot)
        ctrl_layout.addWidget(self.check_3d)

        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        # --- Canvas ---
        self.field_tab = FieldTab(self)
        layout.addWidget(self.field_tab)

    def _browse(self, line_edit, filter_str):
        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir fichier", "", filter_str)
        if path:
            line_edit.setText(path)

    def _load_magnetic(self):
        path = self.ficb_edit.text().strip()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "Erreur", "Fichier champ B introuvable.")
            return
        try:
            self.mag_data = read_magnetic_field(path, self.swap)
            self.field_combo.setCurrentIndex(0)
            self._replot()
        except Exception as e:
            QMessageBox.critical(self, "Erreur lecture", str(e))

    def _load_pot_central(self):
        path = self.ficv1_edit.text().strip()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "Erreur", "Fichier pot. central introuvable.")
            return
        try:
            self.pot1_data = read_potential_central(path, self.swap)
            self.field_combo.setCurrentIndex(4)
            self._replot()
        except Exception as e:
            QMessageBox.critical(self, "Erreur lecture", str(e))

    def _load_pot_peripheral(self):
        path = self.ficv2_edit.text().strip()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "Erreur", "Fichier pot. periph. introuvable.")
            return
        try:
            self.pot2_data = read_potential_peripheral(path)
            self.field_combo.setCurrentIndex(5)
            self._replot()
        except Exception as e:
            QMessageBox.critical(self, "Erreur lecture", str(e))

    def _replot(self):
        fig = self.field_tab.fig
        fig.clear()
        cmap = self.cmap_combo.currentText()
        is_3d = self.check_3d.isChecked()
        idx = self.field_combo.currentIndex()

        if idx <= 3:
            self._plot_magnetic(fig, idx, cmap, is_3d)
        elif idx <= 5:
            self._plot_potential(fig, idx - 4, cmap, is_3d)
        else:
            self._plot_potential_d2(fig, idx - 6, cmap, is_3d)

        self.field_tab.canvas.draw()

    def _plot_magnetic(self, fig, field_idx, cmap, is_3d):
        if self.mag_data is None:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, "Chargez un fichier de champ B",
                    ha='center', va='center', fontsize=14, color='#888')
            return

        d = self.mag_data
        fields = [d['tbz'], d['d2bz'], d['dbzx'], d['dbzy']]
        names = ['Bz (T)', 'd\u00b2Bz/dr\u00b2', 'dBz/dx', 'dBz/dy']
        data = fields[field_idx]

        # Creer grille (r, theta) -> (x, y) en mm
        r_arr = np.linspace(d['rmin'], d['rmax'], d['nr']) * 1000.0
        theta_arr = np.linspace(0, 2 * np.pi, d['ntetall'])
        R, Theta = np.meshgrid(r_arr, theta_arr, indexing='ij')
        X = R * np.cos(Theta)
        Y = R * np.sin(Theta)

        if is_3d:
            ax = fig.add_subplot(111, projection='3d')
            # Sous-echantillonner pour la 3D
            step_r = max(1, d['nr'] // 80)
            step_t = max(1, d['ntetall'] // 180)
            ax.plot_surface(X[::step_r, ::step_t], Y[::step_r, ::step_t],
                           data[::step_r, ::step_t],
                           cmap=cmap, alpha=0.9, linewidth=0,
                           antialiased=True)
            ax.set_xlabel('X (mm)')
            ax.set_ylabel('Y (mm)')
            ax.set_zlabel(names[field_idx])
        else:
            ax = fig.add_subplot(111)
            im = ax.pcolormesh(X, Y, data, cmap=cmap, shading='auto')
            fig.colorbar(im, ax=ax, label=names[field_idx])
            ax.set_xlabel('X (mm)')
            ax.set_ylabel('Y (mm)')
            ax.set_aspect('equal')

        ax.set_title(f"{d['title']} - {names[field_idx]}\n"
                     f"r: [{d['rmin']*1000:.0f}, {d['rmax']*1000:.0f}] mm, "
                     f"nr={d['nr']}, ntet={d['ntet']}")

    def _plot_potential(self, fig, pot_idx, cmap, is_3d):
        data_dict = self.pot1_data if pot_idx == 0 else self.pot2_data
        name = "Potentiel central" if pot_idx == 0 else "Potentiel peripherique"

        if data_dict is None:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, f"Chargez le fichier {name.lower()}",
                    ha='center', va='center', fontsize=14, color='#888')
            return

        d = data_dict
        x_arr = np.linspace(d['xmin'], d['xmax'], d['nx']) * 1000.0
        y_arr = np.linspace(d['ymin'], d['ymax'], d['ny']) * 1000.0
        X, Y = np.meshgrid(x_arr, y_arr, indexing='ij')
        data = d['pot']

        if is_3d:
            ax = fig.add_subplot(111, projection='3d')
            step_x = max(1, d['nx'] // 80)
            step_y = max(1, d['ny'] // 80)
            ax.plot_surface(X[::step_x, ::step_y], Y[::step_x, ::step_y],
                           data[::step_x, ::step_y],
                           cmap=cmap, alpha=0.9, linewidth=0,
                           antialiased=True)
            ax.set_xlabel('X (mm)')
            ax.set_ylabel('Y (mm)')
            ax.set_zlabel('V')
        else:
            ax = fig.add_subplot(111)
            im = ax.pcolormesh(X, Y, data, cmap=cmap, shading='auto')
            fig.colorbar(im, ax=ax, label='V')
            ax.set_xlabel('X (mm)')
            ax.set_ylabel('Y (mm)')
            ax.set_aspect('equal')

        ax.set_title(f"{name}\n"
                     f"x: [{d['xmin']*1000:.0f}, {d['xmax']*1000:.0f}], "
                     f"y: [{d['ymin']*1000:.0f}, {d['ymax']*1000:.0f}] mm, "
                     f"{d['nx']}x{d['ny']}")

    def _plot_potential_d2(self, fig, pot_idx, cmap, is_3d):
        data_dict = self.pot1_data if pot_idx == 0 else self.pot2_data
        name = "d\u00b2V central" if pot_idx == 0 else "d\u00b2V peripherique"

        if data_dict is None:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, "Chargez le fichier potentiel correspondant",
                    ha='center', va='center', fontsize=14, color='#888')
            return

        d = data_dict
        x_arr = np.linspace(d['xmin'], d['xmax'], d['nx']) * 1000.0
        y_arr = np.linspace(d['ymin'], d['ymax'], d['ny']) * 1000.0
        X, Y = np.meshgrid(x_arr, y_arr, indexing='ij')
        data = d['d2pot']

        if is_3d:
            ax = fig.add_subplot(111, projection='3d')
            step_x = max(1, d['nx'] // 80)
            step_y = max(1, d['ny'] // 80)
            ax.plot_surface(X[::step_x, ::step_y], Y[::step_x, ::step_y],
                           data[::step_x, ::step_y],
                           cmap=cmap, alpha=0.9, linewidth=0,
                           antialiased=True)
            ax.set_xlabel('X (mm)')
            ax.set_ylabel('Y (mm)')
            ax.set_zlabel(name)
        else:
            ax = fig.add_subplot(111)
            im = ax.pcolormesh(X, Y, data, cmap=cmap, shading='auto')
            fig.colorbar(im, ax=ax, label=name)
            ax.set_xlabel('X (mm)')
            ax.set_ylabel('Y (mm)')
            ax.set_aspect('equal')

        ax.set_title(f"{name}\n{d['nx']}x{d['ny']}")


# --- Standalone ---
if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    dlg = FieldViewerDialog()
    dlg.show()
    sys.exit(app.exec_())
