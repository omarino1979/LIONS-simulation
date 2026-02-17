"""
lions_worker.py - Worker QThread pour la simulation LIONS
Intercepte input() et print() pour les router vers la GUI.
"""

import sys
import io
import os
import queue
import builtins
import traceback
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal


class InputQueue:
    """Remplace builtins.input : fournit les reponses pre-chargees."""

    def __init__(self, answers):
        self.q = queue.Queue()
        for a in answers:
            self.q.put(a)
        self.fallback_signal = None  # pyqtSignal(str) pour inputs inattendus
        self.response_queue = queue.Queue()

    def __call__(self, prompt=''):
        try:
            answer = self.q.get_nowait()
            return answer
        except queue.Empty:
            if self.fallback_signal:
                self.fallback_signal.emit(prompt or "Entree requise :")
                try:
                    return self.response_queue.get(timeout=300)
                except queue.Empty:
                    raise RuntimeError("Timeout en attente de reponse utilisateur")
            raise RuntimeError(f"Input inattendu: {prompt}")


class OutputInterceptor(io.TextIOBase):
    """Intercepte sys.stdout pour emettre un signal Qt."""

    def __init__(self, signal):
        super().__init__()
        self.signal = signal
        self._original = sys.__stdout__

    def write(self, text):
        if text:
            self.signal.emit(text)
            if self._original:
                self._original.write(text)
        return len(text) if text else 0

    def flush(self):
        if self._original:
            self._original.flush()


class SimulationWorker(QThread):
    """Thread qui execute la simulation LIONS avec hooks pour la GUI."""

    progress = pyqtSignal(int, int)          # (iteration, total)
    iteration_data = pyqtSignal(dict)        # donnees pour les plots
    console_output = pyqtSignal(str)         # texte de sortie
    simulation_finished = pyqtSignal()       # fin normale
    simulation_error = pyqtSignal(str)       # erreur
    input_needed = pyqtSignal(str)           # input inattendu

    def __init__(self, input_answers, work_dir=None):
        super().__init__()
        self.input_answers = input_answers
        self.work_dir = work_dir
        self.stop_flag = False
        self._input_queue = None

    def provide_input(self, answer):
        """Appele par la GUI quand un input inattendu est necessaire."""
        if self._input_queue:
            self._input_queue.response_queue.put(answer)

    def run(self):
        # Importer lions ici (dans le thread) pour eviter les problemes
        # de modules charges au mauvais moment
        original_input = builtins.input
        original_stdout = sys.stdout
        original_dir = os.getcwd()

        try:
            # Changer de repertoire vers le fichier de donnees
            if self.work_dir:
                os.chdir(self.work_dir)

            # Installer les intercepteurs I/O
            self._input_queue = InputQueue(self.input_answers)
            self._input_queue.fallback_signal = self.input_needed
            interceptor = OutputInterceptor(self.console_output)
            builtins.input = self._input_queue
            sys.stdout = interceptor

            # Import du moteur de simulation
            import lions
            from lion_m import LionData

            # Reset etat global
            lions.files_dict = {}

            d = LionData()

            # === Phase 1 : Banniere ===
            print('----------------------------------------------------')
            print('LIONS       : Python (converti de Fortran 90)')
            print('auteur      : Patrick Bertrand - GANIL')
            print('version  1  : decembre 1998...decembre 2004')
            print('version  2  : mars 2017, modif seed, swap etc...')
            print('conversion Python : 2026')
            print('----------------------------------------------------')
            print()
            print('modif swap de mars 2017 :')
            print('on swap les octets ? (y/n)')

            # === Phase 2 : Setup (via input queue) ===
            d.repswap = input().strip()
            d.idebug = 0

            lions.init(d)

            # === Phase 3 : Trieur vertical ===
            print('--------------------')
            print('test trieur vertical :')
            print('--------------------')
            print('rmin_ver rmax_ver teta1_ver teta2_ver :')
            print('1000 2000 0 0 si pas de tri vertical ...')
            vals = lions.parse_floats(input())
            d.rmin_ver = vals[0]
            d.rmax_ver = vals[1]
            d.teta1_ver = vals[2] * d.pi / 180.0
            d.teta2_ver = vals[3] * d.pi / 180.0
            print(d.teta1_ver, d.teta2_ver)
            print('pot_ver,h_ver,phi_ver anuz coupnuz dpotspot :')
            print('0 0 0 0 0 0 si pas de tri vertical...')
            vals = lions.parse_floats(input())
            d.pot_ver = vals[0]
            d.h_ver = vals[1]
            d.phi_ver = vals[2] * d.pi / 180.0
            d.anuz = vals[3]
            d.coupnuz = vals[4]
            d.dpotspot = vals[5]
            print('-------------------')

            # === Phase 4 : Bidim ===
            bidim = lions.BidimManager()
            lions.initgra(d, bidim)

            # === Phase 5 : Pas initial ===
            d.ite = 0
            lions.boite(d)
            lions.calcbe(d)
            iprinf_holder = [1]
            lions.info(d, iprinf_holder)

            # Emettre donnees initiales
            self._emit_data(d)
            self.progress.emit(0, d.nbdt)

            # === Phase 6 : Boucle principale ===
            # Throttle progress : emettre au max toutes les N iterations
            prog_step = max(1, d.nbdt // 200)

            for ite in range(1, d.nbdt + 1):
                if self.stop_flag:
                    print(f'\n--- Simulation arretee a l iteration {ite} ---')
                    break

                d.ite = ite
                lions.piege(d)
                lions.boite(d)
                lions.calcbe(d)
                lions.pousse(d)
                d.t = ite * d.dt + d.t0
                lions.info(d, iprinf_holder)

                if d.numbid != 0 and (ite % d.ifreb == 0 or ite == 1):
                    lions.bid(d, bidim)

                # Hooks GUI (throttle pour ne pas noyer la boucle d'evenements)
                if ite % prog_step == 0 or ite == 1 or ite == d.nbdt:
                    self.progress.emit(ite, d.nbdt)

                # Emettre donnees de plot selon la frequence d'info
                if (d.ifreq > 0 and
                    (ite % d.ifreq == 0 or ite == 1 or ite == d.nbdt)):
                    self._emit_data(d)

            # === Phase 7 : Nettoyage ===
            if d.numbid != 0:
                bidim.clobid()
            for unit_num in [15, 16, 17, 18, 19]:
                if unit_num in lions.files_dict:
                    lions.files_dict[unit_num].close()
            for kg in range(10):
                if (70 + kg + 1) in lions.files_dict:
                    lions.files_dict[70 + kg + 1].close()

            # === Phase 8 : Post-simulation (pieges) ===
            if d.nbrpie != 0:
                nreste = np.count_nonzero(d.ok)
                print(f'nombre de particules non piegees : {nreste}')
                print('ecriture fichier des numero particules piegees ? (o/n)')
                reponse = input().strip()
                if reponse == 'o':
                    print('choisissez nom du fichier : ')
                    ficpie = input().strip()
                    with open(ficpie, 'w') as f60:
                        npi = 0
                        for k in range(d.n):
                            if not d.ok[k]:
                                npi += 1
                                f60.write(f' {npi:5d} {k+1:5d}\n')

            if not self.stop_flag:
                print('\n=== Simulation terminee ===')

            self.simulation_finished.emit()

        except (Exception, SystemExit) as e:
            err_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.simulation_error.emit(err_msg)

        finally:
            builtins.input = original_input
            sys.stdout = original_stdout
            os.chdir(original_dir)

    def _emit_data(self, d):
        """Extrait les donnees de la simulation pour les plots (par famille)."""
        try:
            nbrfam = getattr(d, 'nbrfam', 1)
            for k in range(nbrfam):
                i1 = d.index[k]
                rr = np.sqrt(d.x[i1]**2 + d.y[i1]**2)
                wmevpa = d.am0c2[i1] * (d.ga[i1] - 1.0) / 1.60217733e-13 / d.a[k]
                ppp = np.sqrt(d.px[i1]**2 + d.py[i1]**2 + d.pz[i1]**2)
                tpz = 0.0
                if ppp > 0:
                    tpz = np.arcsin(np.clip(d.pz[i1] / ppp, -1.0, 1.0)) * 1000.0

                # Calculer theta pour cette famille (comme info() le fait pour fam 0)
                if rr > 0:
                    tetnew_k = np.arccos(np.clip(d.x[i1] / rr, -1.0, 1.0))
                    if d.y[i1] < 0.0:
                        tetnew_k = 2.0 * np.pi - tetnew_k
                    tetnew_k = 180.0 / np.pi * tetnew_k
                else:
                    tetnew_k = 0.0

                # Calculer dphi (dephasage HF)
                phihf = 180.0 / d.pi * d.omhf * d.t
                tetall_k = tetnew_k + 360.0 * (d.numtou - 1)
                dph = phihf - d.harm * tetall_k - 90.0

                data = {
                    'family': k,
                    'nbrfam': nbrfam,
                    'ite': d.ite,
                    'numtou': d.numtou,
                    'x0_mm': float(d.x[i1] * 1000.0),
                    'y0_mm': float(d.y[i1] * 1000.0),
                    'r0_mm': float(rr * 1000.0),
                    'tetnew': float(tetnew_k),
                    'z0_mm': float(d.z[i1] * 1000.0),
                    'tpz': float(tpz),
                    'bz0': float(d.bz[i1]),
                    'wmevpa': float(wmevpa),
                    'dph': float(dph),
                }
                self.iteration_data.emit(data)
        except Exception:
            pass  # Ne pas bloquer la simulation pour un probleme de plot
