# LIONS - Documentation Technique Complete

**Programme de Simulation de Dynamique d'Ions dans un Cyclotron**

---

## Table des matieres

1. [Presentation generale](#1-presentation-generale)
2. [Prerequis](#2-prerequis)
3. [Structure du programme](#3-structure-du-programme)
4. [Entrees](#4-entrees)
5. [Variables principales](#5-variables-principales)
6. [Fonctions et methodes](#6-fonctions-et-methodes)
7. [Classes](#7-classes)
8. [Logique de fonctionnement](#8-logique-de-fonctionnement)
9. [Sorties](#9-sorties)
10. [Gestion des erreurs](#10-gestion-des-erreurs)
11. [Exemple complet d'execution](#11-exemple-complet-dexecution)
12. [Ameliorations possibles](#12-ameliorations-possibles)

---

## 1. Presentation generale

### Nom
**LIONS** - **L**ancement d'**I**ons (Simulation de dynamique d'ions dans un cyclotron)

### Objectif
LIONS est un programme de simulation numerique qui calcule les trajectoires d'ions dans un cyclotron a secteurs separes. Il resout les equations relativistes du mouvement (equation de Lorentz) en utilisant un schema d'integration de type Leap-Frog (Boris pusher) pour suivre l'evolution des particules chargees dans les champs magnetiques et electriques du cyclotron.

### Description
Le programme simule le trajet complet des ions depuis leur injection en region centrale du cyclotron jusqu'a leur extraction en peripherie. Il prend en compte :

- **Le champ magnetique** : lu depuis une carte de champ (calculee par TOSCA ou mesuree), avec interpolation bilineaire en coordonnees polaires (r, theta) et expansion de Taylor en z pour le mouvement hors plan median.
- **Le champ electrique** : calcule a partir de cartes de potentiel electrique pour deux regions distinctes :
  - **Region centrale** : potentiel 3D stocke en coordonnees cartesiennes (x, y), incluant la composante Ez via d2V/dz2.
  - **Region peripherique** : potentiel normalise (0 a 1V) dans un repere tourne de l'angle d'ouverture du dee, pour un gap unique ("single gap").
- **L'extraction** : deflecteurs electrostatiques, dipoles magnetiques et grilles d'extraction.
- **Les correlations** : distribution de particules dans l'espace de phase 6D (r, pr, z, pz, phi, dp/p) via decomposition de Cholesky.
- **Le trieur vertical** : champ electrique oscillant pour la focalisation verticale.
- **Les pieges a ions** : obstacles geometriques (piliers, lignes) definis dans un fichier de reperes.

### Historique
- **Auteur original** : Patrick Bertrand, GANIL (Grand Accelerateur National d'Ions Lourds)
- **Version Fortran 90** : Decembre 1998 - Decembre 2004
- **Version 2** : Mars 2017, modifications seed aleatoire, swap octets
- **Conversion Python** : 2026, avec ajout d'une interface graphique PyQt5

### Cas d'utilisation
1. **Conception de cyclotron** : Verifier que les parametres d'une machine permettent l'acceleration et l'extraction d'un faisceau donne.
2. **Optimisation de faisceau** : Ajuster les parametres HF, le champ magnetique (dB/B, facteur B), les phases et potentiels pour optimiser la qualite du faisceau (emittances, transmission).
3. **Etude de l'extraction** : Dimensionner les deflecteurs electrostatiques, les dipoles magnetiques et les grilles d'extraction.
4. **Analyse en espace de phase** : Etudier l'evolution des correlations (r-pr, z-pz, phi-dW/W) au cours de l'acceleration.
5. **Etude du trieur vertical** : Simuler l'effet d'un champ electrique oscillant sur le mouvement vertical.

---

## 2. Prerequis

### Version Python
- **Python 3.8+** (teste avec Python 3.10+)

### Dependances

| Bibliotheque | Version minimale | Utilisation |
|---|---|---|
| `numpy` | 1.20+ | Calculs numeriques, tableaux, algebre lineaire |
| `PyQt5` | 5.15+ | Interface graphique |
| `matplotlib` | 3.5+ | Visualisation bidim (backend Qt5Agg) |
| `pyqtgraph` | 0.13+ | Plots 2D temps reel dans la GUI |
| `pyqtgraph.opengl` | (inclus) | Vue 3D des trajectoires (optionnel) |
| `OpenGL` (PyOpenGL) | 3.1+ | Requis par pyqtgraph.opengl (optionnel) |

### Installation

```bash
pip install numpy PyQt5 matplot
lib pyqtgraph PyOpenGL
```

### Systeme d'exploitation
- **Windows** (teste principalement)
- Linux/macOS (compatible, potentiellement des ajustements de chemins)

### Fichiers requis pour une simulation
1. **Fichier de donnees** (ex: `don.120.ref_phi10_mars_2017`) : parametres physiques
2. **Carte de champ magnetique** (ex: `cime700rec.1804.pbob1.lio.dat`) : Bz, d2Bz/dr2, dBz/dx, dBz/dy
3. **Potentiel region centrale** (ex: `pot3d.impair.30pilbleu30.620.dat`) : fichier binaire Fortran
4. **Potentiel region peripherique** (ex: `newgap612.dat`) : fichier texte, potentiel normalise 0-1V
5. **(Optionnel)** Fichier de correlations sigma
6. **(Optionnel)** Fichier de reperes (piliers, lignes) pour les bidims

---

## 3. Structure du programme

### Arborescence des fichiers

```
a compiler/
|-- lions_gui.py            # Fenetre principale (QMainWindow)
|-- lions_input_form.py     # Formulaire de parametres (QWidget, 16 sections)
|-- lions_worker.py         # QThread d'execution de la simulation
|-- lions.py                # Moteur de simulation (calcul physique)
|-- lion_m.py               # Module de donnees (classe LionData)
|-- lions_plots.py          # Widgets de plots 2D et 3D
|-- lions_field_viewer.py   # Visualiseur de champs (dialog)
|-- lions_bidim_viewer.py   # Visualiseur de fichiers bidim .bid (dialog)
|-- lions.bat               # Script de lancement Windows
|-- don.120.ref_phi10_mars_2017  # Fichier de donnees exemple
```

### Architecture

```
                    +-------------------+
                    |   lions_gui.py    |  <-- Fenetre principale (QMainWindow)
                    +-------------------+
                    |                   |
          +---------+       +----------+---------+
          |                 |                    |
+---------v------+  +-------v--------+  +-------v--------+
| lions_input_   |  | lions_plots.py |  | lions_worker.py|
| form.py        |  | (PlotWidget,   |  | (QThread)      |
| (InputForm     |  |  PlotCanvas,   |  |                |
|  Panel)        |  |  Plot3DWindow) |  |   Intercepte   |
|                |  +----------------+  |   input/print  |
| load/write     |                      |                |
| data file      |                      +-------+--------+
+----------------+                              |
                                                v
                                    +-----------+-----------+
                                    |      lions.py         |
                                    | (moteur simulation)   |
                                    |  init(), calcbe(),    |
                                    |  pousse(), info()     |
                                    +-----------+-----------+
                                                |
                                                v
                                    +-----------+-----------+
                                    |     lion_m.py         |
                                    | (LionData : donnees)  |
                                    +-----------------------+
```

### Description des modules

| Module | Lignes | Role |
|---|---|---|
| `lion_m.py` | 505 | Module de donnees : classe `LionData` avec ~400 attributs (scalaires, tableaux, cartes de champ). Equivalent du module Fortran `lion_m.f90`. |
| `lions.py` | ~2100 | Moteur de simulation : lecture des donnees, interpolation des champs, Boris pusher, calcul des correlations, gestion des bidims. |
| `lions_gui.py` | 493 | Interface graphique principale : toolbar, panneaux, console, gestion du worker. |
| `lions_input_form.py` | ~1500 | Formulaire de parametres avec 16 sections repliables, chargement/ecriture du fichier de donnees. |
| `lions_worker.py` | 274 | Thread de simulation avec interception de `input()` et `print()` pour la GUI. |
| `lions_plots.py` | ~900 | Plots 2D (pyqtgraph avec zoom/pan) et vue 3D OpenGL des trajectoires. |
| `lions_field_viewer.py` | ~500 | Dialogue de visualisation des cartes de champ magnetique et potentiel electrique. |
| `lions_bidim_viewer.py` | 286 | Dialogue de visualisation des fichiers bidim (.bid) avec matplotlib. |

---

## 4. Entrees

### 4.1 Fichier de donnees

Le fichier de donnees est un fichier texte lu par `init()` en mode "list-directed" (emulation Fortran). Les valeurs numeriques utilisent la notation Fortran (`1.50d0` = `1.50e0`).

#### Format detaille (ordre de lecture)

| Ligne | Parametre(s) | Type | Description | Valeurs possibles | Exemple |
|---|---|---|---|---|---|
| 1 | `corps` | string | Titre de la simulation | Texte libre | `"don.forw.H3 i700 posbmax"` |
| 2 | `npaspt` | int | Nombre de pas par tour | > 0 (typique: 360-1080) | `1080` |
| 3 | `r1th`, `ntours` | float, int | Rayon final/extraction (m), nombre de tours | r1th > 0, ntours > 0 | `1.50d0 250` |
| 4 | `fhf`, `pothf`, `teta1`, `harm`, `dbsb` | 5 floats | Frequence HF (Hz), potentiel HF (V), demi-ouverture dee (deg), harmonique, correction dB/B | fhf > 0, harm > 0 | `14400000.d0 -51890.d0 20.d0 3.d0 +1.0d-4` |
| 5 | `dphid`, `dphig` | 2 floats | Decalage phase dee droit/gauche (deg) | Quelconque | `0 0` |
| 6 | `pothfd`, `pothfg` | 2 floats | Potentiel dee droit/gauche (V, positif) | > 0 | `51890.d0 51890.d0` |
| 7 | `ncoh[0]` | int | Nombre de corrections harmonique canal 0 | 0 = desactive | `0` |
| (7b) | coefficients coh | floats | Coefficients correctifs (si ncoh[0] != 0) | | |
| (7c) | `phihar[0]` | float | Phase harmonique canal 0 (deg) | | |
| 8 | `ncoh[1]` | int | Nombre de corrections harmonique canal 1 | 0 = desactive | `0` |
| 9 | `zmin`, `zmax`, `rmax1` | 3 floats | Limites verticales (m), rayon limite centre/peripherie (m) | zmin < zmax | `-.5d0 .5d0 .164d0` |
| 10 | `rex`, `tet1ex`, `tet2ex`, `eex` | 4 floats | Parametres extraction | rex < 0 = extraction active | `-1. -1. -1. -1.` |
| (10b) | `ndf` | int | Nombre de deflecteurs (si rex < 0) | 0-10 | `1` |
| (10c) | deflecteurs | 8 floats/ligne | rdf edf xdfi ydfi xdfo ydfo tetdfi tetdfo | Par deflecteur | |
| (10d) | `ndm` | int | Nombre de dipoles magnetiques (si rex < 0) | 0-10 | `0` |
| (10e) | grilles | | Grilles d'extraction (si tet2ex > 0) | | |
| 11 | `nbrfam` | int | Nombre de familles d'ions | 1-10 (NF max = 100) | `1` |
| (11b) | `n` | int | N total particules (si nbrfam > 1) | | |
| 12 | `nbrion`, `amat`, `a_mass`, `qn` | int + 3 floats | Par famille : nb ions, masse atomique (uma), nombre de masse, charge | | `1 100.36496d0 100.36496d0 22.d0` |
| 13 | `r0`, `teta0`, `z0`, `pr0`, `pz0`, `w0mev`, `phi0` | 7 floats | Conditions initiales : rayon (m), angle (deg), z (m), pr (mrad), pz (mrad), energie (MeV/A), phase HF (deg) | | `0.033 266.9 0.d0 426.28 0.d0 5.665d-3 -250.d0` |
| 14 | `iflcor` | int | Flag correlations | 0 = desactive | `0` |
| (14b) | fichiers correl | strings | ficsig, espace, ficcor, ficmat, ficdc (si iflcor != 0) | | |
| 15 | `nbdt`, `ifreq` | 2 ints | Nombre de pas de temps, frequence d'affichage | nbdt > 0, ifreq > 0 | `350000 30` |
| 16 | `ficz` | string | Fichier sortie z ("no" = desactive) | | `exp.for.z.ref_phi10_mars_2017` |
| 17 | `ficxy` | string | Fichier sortie xy ("no" = desactive) | | `exp.for.ref_phi10_mars_2017` |
| 18 | `ficb` | string (quote) | Carte de champ magnetique | | `'cime700rec.1804.pbob1.lio.dat'` |
| 19 | `ficv1` | string (quote) | Potentiel region centrale | | `'pot3d.impair.30pilbleu30.620.dat'` |
| 20 | `ficv2` | string (quote) | Potentiel region peripherique | | `'newgap612.dat'` |
| 21 | `b_factor` | float | Facteur B en Tesla (optionnel, defaut 1.0) | | `1.56d0` |

### 4.2 Carte de champ magnetique

Fichier texte contenant les composantes du champ magnetique en coordonnees polaires :

```
Ligne 1 : titre
Ligne 2 : rmin  rmax  nr  ntet
Bloc 1  : Bz(r, theta)        [nr lignes de ntet valeurs]
Bloc 2  : d2Bz/dr2(r, theta)  [nr lignes de ntet valeurs]
Bloc 3  : dBz/dx(r, theta)    [nr lignes de ntet valeurs] (pour Bx = z * dBz/dx)
Bloc 4  : dBz/dy(r, theta)    [nr lignes de ntet valeurs] (pour By = z * dBz/dy)
```

Deux formats sont geres :
- **Carte complete** (`ntet != 91`) : 360 degres complets
- **Carte 1/8eme** (`ntet == 91`) : 0 a 45 degres, etendue par symetrie a 360 degres

La carte est normalisee a 1 a la lecture, puis multipliee par `b_factor` (Tesla), puis corrigee par `(1 + dB/B)`.

### 4.3 Potentiel region centrale (ficv1)

Fichier **binaire** au format enregistrements Fortran :
- Record 1 : xmin, xmax, ymin, ymax (mm, float64), nx, ny (int32)
- Records 2 a nx+1 : pot1(i, 0:ny-1) (float64)
- Records nx+2 a 2*nx+1 : d2pot1(i, 0:ny-1) (float64, optionnel pour Ez)

L'option "byte swap" (`repswap='y'`) inverse l'ordre des octets (big-endian vs little-endian).

### 4.4 Potentiel region peripherique (ficv2)

Fichier **texte** au format Fortran list-directed :
```
xmin  xmax  ymin  ymax  nx  ny
pot2(0,0) pot2(0,1) ... pot2(0,ny-1)
...
pot2(nx-1,0) ... pot2(nx-1,ny-1)
d2pot2(0,0) ... d2pot2(0,ny-1)
...
d2pot2(nx-1,0) ... d2pot2(nx-1,ny-1)
```

Le potentiel est normalise entre 0 et 1V et est multiplie par le potentiel HF effectif au moment du calcul (cos(omega_HF * t + dphase)).

### 4.5 Entrees interactives (runtime)

Lors de l'execution, le programme pose des questions via `input()`. Dans la GUI, ces reponses sont pre-chargees depuis le formulaire :

| Question | Parametre GUI | Exemple |
|---|---|---|
| `on swap les octets ? (y/n)` | Byte swap (combo y/n) | `y` |
| `fichier_de_donnees de depart :` | Fichier donnees (chemin) | `don.120.ref_phi10_mars_2017` |
| `rmin_ver rmax_ver teta1_ver teta2_ver :` | Section Trieur Vertical | `1000 2000 0 0` |
| `pot_ver,h_ver,phi_ver anuz coupnuz dpotspot :` | Section Trieur Vertical | `0 0 0 0 0 0` |
| `numero premier bidim :` | Section Bidim | `0` (aucun bidim) |
| Parametres bidim si numbid != 0 | Section Bidim/Diagnostics | |

---

## 5. Variables principales

### 5.1 Constantes de dimensionnement (lion_m.py)

| Constante | Valeur | Role |
|---|---|---|
| `NF` | 100 | Nombre maximum de familles d'ions |
| `LX1` | 500 | Dimension X de la carte de potentiel centre |
| `LY1` | 300 | Dimension Y de la carte de potentiel centre |
| `LX2` | 50 | Dimension X de la carte de potentiel peripherie |
| `LY2` | 1000 | Dimension Y de la carte de potentiel peripherie |
| `NDFM` | 10 | Nombre maximum de deflecteurs electrostatiques |
| `NDMM` | 10 | Nombre maximum de dipoles magnetiques |

### 5.2 Variables physiques scalaires

| Variable | Type | Unite | Description |
|---|---|---|---|
| `fhf` | float64 | Hz | Frequence HF |
| `omhf` | float64 | rad/s | Pulsation HF (2*pi*fhf) |
| `omr` | float64 | rad/s | Pulsation de revolution (omhf/harm) |
| `harm` | float64 | - | Harmonique |
| `pothf` | float64 | V | Potentiel HF |
| `pothfd` | float64 | V | Potentiel dee droit (signe inverse a la lecture) |
| `pothfg` | float64 | V | Potentiel dee gauche (signe inverse a la lecture) |
| `teta1` | float64 | rad | Demi-ouverture du dee |
| `dbsb` | float64 | - | Correction relative de champ dB/B |
| `b_factor` | float64 | T | Facteur multiplicatif du champ magnetique normalise |
| `dt` | float64 | s | Pas de temps (harm / fhf / npaspt) |
| `cdt` | float64 | m | c * dt |
| `clum` | float64 | m/s | Vitesse de la lumiere (299792458) |
| `pi` | float64 | rad | Pi |
| `r1th` | float64 | m | Rayon final/extraction theorique |
| `ntours` | int | - | Nombre de tours prevu |
| `nbdt` | int | - | Nombre total de pas de temps |
| `npaspt` | int | - | Nombre de pas par tour |
| `ite` | int | - | Iteration courante |
| `numtou` | int | - | Numero de tour courant |
| `ifreq` | int | - | Frequence d'affichage des informations |
| `rex` | float64 | m | Rayon d'extraction (< 0 = extraction active) |
| `ndf` | int | - | Nombre de deflecteurs electrostatiques |
| `ndm` | int | - | Nombre de dipoles magnetiques |
| `ngex` | int | - | Nombre de grilles d'extraction |
| `nbrfam` | int | - | Nombre de familles d'ions |
| `n` | int | - | Nombre total de particules |
| `np_` | int | - | Nombre de particules actives |
| `nbox` | int | - | Particules dans la boite |
| `nbox1` | int | - | Particules en zone centrale |
| `nbox2` | int | - | Particules en zone peripherique |
| `iflcor` | int | - | Flag correlations (0 = desactive) |
| `iflpie` | int | - | Flag mode pieges (0 = reste scotchee, 1 = confondue avec particule centrale) |
| `heps` | float64 | - | Signe de symetrie pour harmonique paire/impaire (+1 ou -1) |

### 5.3 Tableaux par particule (alloues par `allo()`)

| Variable | Dimensions | Type | Description |
|---|---|---|---|
| `x`, `y`, `z` | (n,) | float64 | Position (m) |
| `px`, `py`, `pz` | (n,) | float64 | Impulsion normalisee (p / m0c) |
| `ga` | (n,) | float64 | Facteur de Lorentz gamma |
| `p` | (n,) | float64 | Module de l'impulsion |
| `r` | (n,) | float64 | Rayon (m) |
| `teta` | (n,) | float64 | Angle polaire (rad) |
| `bx`, `by`, `bz` | (n,) | float64 | Champ magnetique (T) |
| `ex`, `ey`, `ez` | (n,) | float64 | Champ electrique (V/m) |
| `am0` | (n,) | float64 | Masse au repos (kg) |
| `am0c`, `am0c2` | (n,) | float64 | m0*c, m0*c^2 |
| `q` | (n,) | float64 | Charge (C) |
| `qdts2m0` | (n,) | float64 | q*dt/2/m0 (precalcule pour le Boris pusher) |
| `qdtsm0c` | (n,) | float64 | q*dt/(m0*c) |
| `box` | (n,) | bool | Particule dans la boite de simulation |
| `centre` | (n,) | bool | Particule en zone centrale |
| `periph` | (n,) | bool | Particule en zone peripherique |
| `extra` | (n,) | bool | Particule dans un element d'extraction |
| `sortant` | (n,) | bool | Particule en cours d'extraction |
| `ok` | (n,) | bool | Particule vivante (non piegee) |
| `dxs` | (6, n) | float64 | Coordonnees espace de phase (dr, dpr, dz, dpz, ds, dp) |
| `dxd` | (6, n) | float64 | Coordonnees decalees (intermediaire) |

### 5.4 Cartes de champ (taille fixe)

| Variable | Dimensions | Description |
|---|---|---|
| `tbz` | (250, 721) | Composante Bz(r, theta) |
| `d2bz` | (250, 721) | Derivee seconde d2Bz/dr2 |
| `dbzx` | (250, 721) | dBz/dx (pour Bx = z * dBz/dx) |
| `dbzy` | (250, 721) | dBz/dy (pour By = z * dBz/dy) |
| `pot1` | (500, 300) | Potentiel region centrale |
| `d2pot1` | (500, 300) | d2V/dz2 region centrale |
| `pot2` | (50, 1000) | Potentiel region peripherique (normalise 0-1V) |
| `d2pot2` | (50, 1000) | d2V/dz2 region peripherique |

### 5.5 Variables par famille (taille NF=100)

| Variable | Description |
|---|---|
| `nbrion[k]` | Nombre d'ions famille k |
| `index[k]` | Index de debut dans les tableaux particules |
| `amat[k]` | Masse atomique (uma) |
| `a[k]` | Nombre de masse |
| `qn[k]` | Charge (en unites de e) |
| `r0[k]`, `teta0[k]`, `z0[k]` | Position initiale |
| `pr0[k]`, `pz0[k]` | Impulsion radiale/verticale initiale (rad) |
| `w0[k]` | Energie initiale (J) |
| `phi0[k]` | Phase HF initiale (deg) |

---

## 6. Fonctions et methodes

### 6.1 Fonctions utilitaires (lions.py)

#### `fortran_float(s)`
Convertit un nombre en notation Fortran en float Python.
- **Parametre** : `s` (str) - chaine contenant un nombre Fortran (ex: "1.50d0", "3.14D-4")
- **Retour** : `float`
- **Exemple** : `fortran_float("1.50d0")` -> `1.5`

#### `parse_floats(s)`
Parse une chaine en liste de floats avec support de la notation Fortran.
- **Parametre** : `s` (str) - chaine avec nombres separes par des espaces
- **Retour** : `list[float]`
- **Exemple** : `parse_floats("1.0d0 2.5d-3")` -> `[1.0, 0.0025]`

#### `parse_ints(s)`
Parse une chaine en liste d'entiers (via conversion float intermediaire).
- **Parametre** : `s` (str)
- **Retour** : `list[int]`

#### `read_input(prompt='')`
Lit une ligne d'entree utilisateur (wrappeur autour de `input()`).
- **Parametre** : `prompt` (str) - texte affiche avant la lecture
- **Retour** : `str`

### 6.2 Fonctions de simulation (lions.py)

#### `init(d)`
**Fonction d'initialisation principale.** Lit le fichier de donnees, les cartes de champ magnetique et electrique, initialise les particules.

- **Parametre** : `d` (LionData) - objet contenant toutes les donnees de simulation
- **Retour** : aucun (modifie `d` en place)
- **Actions** :
  1. Lit le fichier de donnees (`ficin`) avec `FortranFile`
  2. Calcule les parametres derives (dt, omhf, omr, cdt, heps)
  3. Alloue les tableaux dynamiques (`d.allo()`)
  4. Initialise les positions et impulsions des particules
  5. Lit la carte magnetique (`ficb`) et applique les symetries si carte 1/8eme
  6. Ajoute les harmoniques si `ncoh != 0` (appel a `addh()`)
  7. Normalise la carte magnetique a 1, puis applique `b_factor` et `dB/B`
  8. Lit le potentiel central (`ficv1`, binaire Fortran) et peripherique (`ficv2`, texte)
  9. Si `iflcor != 0` : genere la distribution en espace de phase via Cholesky
  10. Ouvre les fichiers de sortie (ficz, ficxy)
- **Exceptions** : `SystemExit` si n != np_ (nombre de particules incoherent)

#### `calcbe(d)`
**Calcul complet des champs B et E pour toutes les particules.**

- **Parametre** : `d` (LionData)
- **Retour** : aucun (modifie d.bx, d.by, d.bz, d.ex, d.ey, d.ez)

**Etape 1 : Conversion en coordonnees polaires**

```
r = sqrt(x^2 + y^2)
theta = arccos(x / r)         si y >= 0
theta = 2*pi - arccos(x / r)  si y < 0
```

**Etape 2 : Champ magnetique - interpolation bilineaire en (r, theta)**

Indices de grille et poids bilineaires :
```
i = floor((r - rmin) / hr)        j = floor(theta / h_theta)
a = r - rmin - i*hr               b = theta - j*h_theta
d1 = a - hr                       d2 = b - h_theta
```

Composante verticale Bz avec correction hors plan median (Taylor en z) :
```
Bz(r,theta,z) = [d1*d2*(Bz[i,j] - z^2/2 * d2Bz[i,j])
               - a*d2 *(Bz[i+1,j] - z^2/2 * d2Bz[i+1,j])
               + a*b  *(Bz[i+1,j+1] - z^2/2 * d2Bz[i+1,j+1])
               - d1*b *(Bz[i,j+1] - z^2/2 * d2Bz[i,j+1])] / (hr * h_theta)
```

Composantes horizontales (equations de Maxwell, div B = 0) :
```
Bx(r,theta,z) = z * [d1*d2*dBzx[i,j] - a*d2*dBzx[i+1,j]
                    + a*b*dBzx[i+1,j+1] - d1*b*dBzx[i,j+1]] / (hr * h_theta)

By(r,theta,z) = z * [d1*d2*dBzy[i,j] - a*d2*dBzy[i+1,j]
                    + a*b*dBzy[i+1,j+1] - d1*b*dBzy[i,j+1]] / (hr * h_theta)
```

**Etape 3 : Champ electrique en zone centrale (pot1)**

Indices de grille cartesienne et poids :
```
i = floor((x - xmin1) / hx1)      j = floor((y - ymin1) / hy1)
p1 = (a-hx1)(b-hy1)    p2 = -a(b-hy1)    p3 = a*b    p4 = -(a-hx1)*b
```

Ex par differences finies centrees aux 4 coins :
```
Ex_coin = [-(V[i+1,j] - V[i-1,j]) + z^2/2*(d2V[i+1,j] - d2V[i-1,j])] / (2*hx1)
```

Phase HF et potentiel effectif :
```
V_HF(t) = pothfd * cos(omega_hf*t + dphid)     (x >= 0, dee droit)
V_HF(t) = pothfg * cos(omega_hf*t + dphig)     (x < 0, dee gauche)
```

Champs finaux (interpolation bilineaire * V_HF) :
```
Ex = V_HF * (Ex1*p1 + Ex2*p2 + Ex3*p3 + Ex4*p4) / (hx1 * hy1)
Ey = V_HF * (Ey1*p1 + Ey2*p2 + Ey3*p3 + Ey4*p4) / (hx1 * hy1)
Ez = z * V_HF * (d2V1*p1 + d2V2*p2 + d2V3*p3 + d2V4*p4) / (hx1 * hy1)
```

**Etape 4 : Champ electrique en zone peripherique (pot2)**

Rotation des coordonnees dans le repere du gap :
```
x' = |x|*cos(teta1) + (|y| - y_omega)*sin(teta1)
y' = -|x|*sin(teta1) + (|y| - y_omega)*cos(teta1)
```

Interpolation du potentiel normalise (0-1V) et champ dans le repere tourne :
```
Ex_rot = -V_HF / (hx2*hy2) * [d2*(V[i,j]-V[i+1,j]) + b*(V[i+1,j+1]-V[i,j+1])]
Ey_rot = -V_HF / (hx2*hy2) * [d1*(V[i,j]-V[i,j+1]) - a*(V[i+1,j]-V[i+1,j+1])]
```

Rotation inverse vers le repere laboratoire :
```
Ex_lab = Ex_rot * cos(teta1) - Ey_rot * sin(teta1)
Ey_lab = Ex_rot * sin(teta1) + Ey_rot * cos(teta1)
```

Symetries selon les quadrants (heps = +1 si harm impaire, -1 si paire) :
```
Quadrant II  (x<0, y>0) : Ex *= heps,  Ey *= -heps
Quadrant IV  (x>0, y<0) : Ey *= -1
Quadrant III (x<0, y<0) : Ex *= heps,  Ey *= heps
Pour x < 0 :              Ez *= -heps
```

**Etape 5 : Trieur vertical** (`_calcbe_vertical`)

Champ Ez oscillant a deux bandes laterales :
```
Ez -= (V_ver*(1-dpotspot)) / (2*h_ver) * cos(2*omega_hf*t*(1 + nuz/(2*h)) + 2*phi_ver - pi/2)
Ez -= (V_ver*(1+dpotspot)) / (2*h_ver) * cos(2*omega_hf*t*(1 - nuz/(2*h)) + 2*phi_ver - pi/2)
```
Condition : rmin_ver <= r <= rmax_ver et teta1_ver <= theta <= teta2_ver

**Etape 6 : Extraction** (`_calcbe_extraction`)

Deflecteur electrostatique (champ perpendiculaire a l'impulsion) :
```
|p_xy| = sqrt(px^2 + py^2)
Ex = E_df * py / |p_xy|
Ey = -E_df * px / |p_xy|
```

Dipole magnetique (gradient lineaire) :
```
d = sqrt((x-x_dm)^2 + (y-y_dm)^2)
Bz += (d - r_dm) * B_dm
Bx += z * B_dm * (x-x_dm) / d
By += z * B_dm * (y-y_dm) / d
```

#### `pousse(d)`
**Boris pusher - avance les particules d'un pas de temps.**

- **Parametre** : `d` (LionData)
- **Retour** : aucun (modifie d.x, d.y, d.z, d.px, d.py, d.pz, d.ga)

Constantes precalculees :
```
qdts2m0 = q*dt / (2*m0)          (demi charge-sur-masse * dt)
qdtsm0c = q*dt / (m0*c)          (charge-sur-masse * dt / c)
cdt = c * dt                     (vitesse lumiere * pas de temps)
```

**Etape 1 : Vecteur t de Boris (demi-rotation magnetique)**
```
t = (q*dt) / (2*m0*gamma) * B

t_x = qdts2m0 / gamma * Bx
t_y = qdts2m0 / gamma * By
t_z = qdts2m0 / gamma * Bz
```

**Etape 2 : Facteur de normalisation**
```
s = 1 / (1 + t_x^2 + t_y^2 + t_z^2)
```

**Etape 3 : Elements de la matrice de rotation de Boris**
```
s12 = t_x*t_y + t_z       s21 = t_x*t_y - t_z
s13 = t_x*t_z - t_y       s31 = t_x*t_z + t_y
s23 = t_y*t_z + t_x       s32 = t_y*t_z - t_x
```

Matrice M (hors diagonale) :
```
        | -(t_y^2+t_z^2)    s12              s13          |
M_off = |  s21             -(t_x^2+t_z^2)   s23          |
        |  s31              s32             -(t_x^2+t_y^2)|
```

**Etape 4 : Impulsion electrique totale (les deux demi-kicks combines)**
```
f = (q*dt) / (m0*c) * E

fx = qdtsm0c * Ex,    fy = qdtsm0c * Ey,    fz = qdtsm0c * Ez
```

**Etape 5 : Vecteur intermediaire (demi-kick E + 2*p)**
```
v4 = s * (fx + 2*px)
v5 = s * (fy + 2*py)
v6 = s * (fz + 2*pz)
```

**Etape 6 : Mise a jour de l'impulsion (rotation + 2eme demi-kick E)**
```
px_new = px - (t_y^2+t_z^2)*v4 + s12*v5 + s13*v6 + fx
py_new = py + s21*v4 - (t_x^2+t_z^2)*v5 + s23*v6 + fy
pz_new = pz + s31*v4 + s32*v5 - (t_x^2+t_y^2)*v6 + fz
```

Sous forme matricielle : `p^{n+1} = p^n + M * v + f`

**Etape 7 : Mise a jour du facteur de Lorentz**
```
gamma = sqrt(1 + px^2 + py^2 + pz^2)
```

**Etape 8 : Avance en position (Leap-Frog)**
```
x_new = x + (c*dt / gamma) * px
y_new = y + (c*dt / gamma) * py
z_new = z + (c*dt / gamma) * pz
```

Note : l'impulsion p est normalisee par m0*c, donc v = c*p/gamma.

#### `boite(d)`
Verifie quelles particules sont dans la boite de simulation.
- **Criteres** : `rmin < r < rmax-0.02`, `zmin < z < zmax`, `ok == True`
- **Modifie** : `d.box`, `d.nbox`

#### `box1(d)`
Verifie les particules dans la zone centrale.
- **Critere** : `r < rmax1` et `|y| < ymax1 - hy1`
- **Modifie** : `d.centre`, `d.nbox1`

#### `box2(d)`
Verifie les particules dans la zone peripherique (en coordonnees tournees).
- **Modifie** : `d.periph`, `d.nbox2`

#### `boxdf(d, i)`
Verifie les particules dans le deflecteur electrostatique i (0-based).
- **Modifie** : `d.extra`, `d.sortant`, `d.nextra`

Test de demi-plan (produit vectoriel) :
```
Entree :  (x - x_dfi) * sin(theta_dfi) - (y - y_dfi) * cos(theta_dfi) <= 0
Sortie :  (x - x_dfo) * sin(theta_dfo) - (y - y_dfo) * cos(theta_dfo) >= 0
```

Condition d'activation du 1er deflecteur :
```
r > r_df[0]        (si iteext == 0)
ite >= iteext       (si iteext > 0)
```

#### `boxdm(d, i)`
Verifie les particules dans le dipole magnetique i.
- **Modifie** : `d.extra`, `d.nextra`

Meme test de demi-plan que pour les deflecteurs :
```
Entree :  (x - x_dm) * sin(theta_dmi) - (y - y_dm) * cos(theta_dmi) <= 0
Sortie :  (x - x_dm) * sin(theta_dmo) - (y - y_dm) * cos(theta_dmo) >= 0
```

#### `boxgex(d, i)`
Verifie les particules franchissant la grille d'extraction i.
- **Modifie** : `d.franchi`, `d.indgex`

Test de franchissement (produit vectoriel avec le vecteur normal a la grille) :
```
dr_gex = sqrt((x_gex - x_gexc)^2 + (y_gex - y_gexc)^2)
ux = (x_gex - x_gexc) / dr_gex       (vecteur unitaire normal)
uy = (y_gex - y_gexc) / dr_gex
franchi = (x - x_gex) * uy - (y - y_gex) * ux <= 0
```

#### `piege(d)`
Gere le piegeage des ions dans les obstacles.
- **Modifie** : `d.ok`, `d.nbrok`

Condition de perte verticale :
```
perdue = (z < zmin) OU (z > zmax)
```

Collision avec les pieges circulaires (piliers) :
```
Pour chaque obstacle k de centre (xp[k], yp[k]) et rayon rp[k] :
  piegee = (x - xp[k])^2 + (y - yp[k])^2 <= rp[k]^2
```

Si `iflpie == 1` : les particules piegees sont replacees sur la particule centrale (memes x, y, z, px, py, pz).

#### `info(d, iprinf_holder)`
Affiche et enregistre les informations de suivi.
- **Parametres** :
  - `d` (LionData) : donnees de simulation
  - `iprinf_holder` (list[int]) : `[1]` au premier appel, puis `[0]`

**Premier appel - grandeurs theoriques :**
```
v0th = c * sqrt((gamma0-1)(gamma0+1)) / gamma0        (vitesse relativiste)
r0th = v0th / omega_r                                  (rayon d'equilibre)
B0th = -v0th * m0 * gamma0 / (q * r0th)               (champ magnetique)
gamma1th = 1 / sqrt(1 - (gamma0^2-1)*r1th^2 / (gamma0^2*r0th^2))   (gamma a l'extraction)
W1th = m0*c^2 * (gamma1th - 1)                        (energie a l'extraction)
B1th = B0th * gamma1th / gamma0                        (champ isochrone)
pot_th = m0*c^2*(gamma1th - gamma0) / (4*N_tours*q)   (tension dee estimee)
```

**Chaque appel - suivi :**
```
r = sqrt(x[0]^2 + y[0]^2)                             (rayon)
tetnew = arccos(x[0]/r), ajuste a [0, 360] deg        (angle polaire)
phi_hf = (180/pi) * omega_hf * t                      (phase HF)
dphi = phi_hf - h * (tetnew + 360*(numtou-1)) - 90    (dephasage)
wmevpa = m0*c^2*(gamma-1) / (1.602e-13 * A)           (energie MeV/A)
```

Composantes de l'impulsion et divergences :
```
p_perp = sqrt(px^2 + py^2)                            (impulsion transverse)
pr = (x*px + y*py) / r                                (impulsion radiale)
tpr = arcsin(pr / |p|) * 1000                         (divergence radiale, mrad)
tpz = arcsin(pz / |p|) * 1000                         (divergence verticale, mrad)
```

Centre de courbure (centre guidant) :
```
xc = x + py / (q * Bz / (m0*c))           (en m, puis *1000 pour mm)
yc = y - px / (q * Bz / (m0*c))
```

Composantes tangentielle et radiale du champ E :
```
Es = (Ex*px + Ey*py) / p_perp / 1e5       (kV/cm, tangentiel)
Er = (Ex*py - Ey*px) / p_perp / 1e5       (kV/cm, radial)
```

Frequence verticale :
```
nuz_c = (-1/(m0*gamma)) * (h/omega_hf)^2 / z * q * (Ez + c/gamma * (px*By - py*Bx))
nu_z = sqrt(|nuz_c|)
```

**Correlations (si iflcor != 0) :**

Rayon de courbure :
```
rc = -m0*c * |p| / (q * Bz)
```

Coordonnees curvilignes par rotation de l'angle (theta - alpha) :
```
alpha = arcsin(pr / |p|)
dx_rot =  dx*cos(theta-alpha) + dy*sin(theta-alpha)
dy_rot = -dx*sin(theta-alpha) + dy*cos(theta-alpha)
```

Arc le long de l'orbite de reference :
```
ds = rc * arctan(dy_rot / (rc + dx_rot))
```

Ecart radial en coordonnees curvilignes :
```
v = sin(ds / (2*rc))^2
dr = (dx_rot + 2*rc*v) / (1 - 2*v)
```

Matrice sigma (moments d'ordre 2) :
```
sigma[i,j] = (1/N) * SUM_k( dxs[i,k] * dxs[j,k] )
```

Emittances (4-RMS geometriques, pi.mm.mrad) :
```
eps_r = 8 * sqrt(|sigma_rr * sigma_pp - sigma_rp^2|) * 1e6 / |p|
eps_z = 8 * sqrt(|sigma_zz * sigma_pzpz - sigma_zpz^2|) * 1e6 / |p|
```

Dispersion en energie relative :
```
dW/W = dp * |p| / (gamma * (gamma - 1))
```

Dispersion en phase (degres) :
```
dphi = ds * omega_hf / (c * |p|) * (180/pi) * gamma
```

#### `addh(rmin, rmax, nr, ntet, tbz, d2bz, dbzx, dbzy, ncoh, coh, phihar)`
Ajoute des harmoniques analytiques a la carte de champ magnetique.
- **Parametres** : cartes de champ en entree/sortie, coefficients harmoniques
- **Retour** : aucun (modifie les cartes en place)

Harmonique 1 (dipolaire) - fonction generatrice lineaire tournee :
```
s = x*cos(-phi1) - y*sin(-phi1)

Bz_add = SUM_{k=0}^{ncoh-1} coh[k] * (x^2+y^2)^k * s

dBz/dx = coh[0]*cos(-phi1) + SUM_{k>=1} coh[k]*(x^2+y^2)^{k-1} * (2*x*k*s + (x^2+y^2)*cos(-phi1))
dBz/dy = -coh[0]*sin(-phi1) + SUM_{k>=1} coh[k]*(x^2+y^2)^{k-1} * (2*y*k*s - (x^2+y^2)*sin(-phi1))
Laplacien = SUM_{k>=1} coh[k]*(x^2+y^2)^{k-1} * 4*s*k*(k+1)
```

Harmonique 2 (quadrupolaire) - fonction generatrice quadratique tournee :
```
s = (x^2 - y^2)*cos(-phi2) - 2*x*y*sin(-phi2)

Bz_add = SUM_{k=0}^{ncoh-1} coh[k] * (x^2+y^2)^k * s

Laplacien = SUM_{k>=1} coh[k]*(x^2+y^2)^{k-1} * 4*s*k*(k+2)
```

#### `choles(m, a)`
Decomposition de Cholesky d'une matrice symetrique definie positive A = R^T * R.
- **Parametres** : `m` (int) dimension, `a` (ndarray m x m) matrice
- **Retour** : `r` (ndarray m x m) triangulaire superieure

```
R[0,0] = sqrt(A[0,0])
R[0,j] = A[0,j] / R[0,0]                                         pour j = 1..m-1

R[i,i] = sqrt(A[i,i] - SUM_{k=0}^{i-1} R[k,i]^2)                pour i = 1..m-1
R[i,j] = (A[i,j] - SUM_{k=0}^{i-1} R[k,i]*R[k,j]) / R[i,i]     pour j = i+1..m-1
```

#### `remp(m, n_part)`
Genere une distribution aleatoire uniforme normalisee dans l'hyper-sphere de dimension m.
- **Parametres** : `m` (int) dimension espace de phase, `n_part` (int) nombre de particules
- **Retour** : `ps` (ndarray m x n_part) matrice decorrellee
- **Note** : Utilise `seed(42)` pour la reproductibilite

```
1. Echantillonnage par rejet dans l'hyper-sphere unite :
   Generer vtab[j] = 2*rand()-1 pour chaque dimension
   Accepter si SUM_j(vtab[j]^2) <= 1

2. Matrice de correlation echantillon :
   C[i,j] = (1/N) * SUM_k( ps[i,k] * ps[j,k] )

3. Decorrelation par Cholesky (substitution avant) :
   R = choles(m, C),  T = R^T
   ps[0] = ps[0] / T[0,0]
   ps[i] = (ps[i] - SUM_{k<i} T[i,k]*ps[k]) / T[i,i]
```

#### `caldxs(d)`
Calcule les coordonnees dans l'espace de phase 6D (dr, dpr, dz, dpz, ds, dp).

Rotation dans le repere mobile de la particule centrale :
```
cos_rot = cos(theta_ref - alpha_ref)
sin_rot = sin(theta_ref - alpha_ref)
dx_rot  =  (x-x_ref)*cos_rot + (y-y_ref)*sin_rot
dy_rot  = -(x-x_ref)*sin_rot + (y-y_ref)*cos_rot
```

Coordonnees curvilignes :
```
dxs[4] = rc * arctan(dy_rot / (rc + dx_rot))          (arc le long de l'orbite)
v = sin(dxs[4] / (2*rc))^2
dxs[0] = (dx_rot + 2*rc*v) / (1 - 2*v)               (ecart radial)
dxs[2] = z - z_ref                                     (ecart vertical)
dxs[3] = pz - pz_ref                                   (ecart impulsion verticale)
dxs[1] = dpx_rot*cos(ds/rc) + dpy_rot*sin(ds/rc)      (ecart impulsion radiale)
dxs[5] = sqrt((p_ref+dp_tang)^2 + dpr^2 + dpz^2) - p_ref  (ecart impulsion totale)
```

#### `calgri(d)` / `calgric(d)`
Calcul des coordonnees au passage des grilles d'extraction.
- `calgri` : intersection trajectoire-grille
- `calgric` : version pour les correlations

#### `calcb(d)`
Version simplifiee du calcul de B (sans champ E), utilisee pendant l'initialisation pour les correlations.

Meme interpolation bilineaire que `calcbe()` mais uniquement pour B :
```
Bz(r,theta,z) = interp_bilineaire(tbz) - z^2/2 * interp_bilineaire(d2bz)
Bx = z * interp_bilineaire(dBzx)
By = z * interp_bilineaire(dBzy)
```

Cas limites :
```
Si r <= rmin : Bz = tbz[0,0], Bx = By = 0    (champ central constant)
Si Bz == 0 :  Bz = -0.00001                   (evite la division par zero)
```

#### `initgra(d, bidim)`
Initialise les diagnostics graphiques (bidims).
- **Actions** :
  - Demande les parametres bidim (numero, frequence, boite, correlations)
  - Lit le fichier de reperes (lignes, cercles, pieges)
  - Configure les pieges a ions si definis dans les reperes
  - Ouvre les fichiers bidim

#### `bid(d, bidim)`
Enregistre les donnees dans les histogrammes 2D (bidims).
- **Bidims enregistres** :
  - Trajectoire ion central (x, y)
  - Centres de courbure ou barycentres
  - Trajectoires tous ions (si n > 1)
  - Correlations dphi-dW/W, dr-dpr/p0, dz-dpz/p0 (si n > 1)

### 6.3 Methodes de la GUI

#### `InputFormPanel.load_data_file(path)`
Parse le fichier de donnees et remplit tous les champs du formulaire.
- **Parametre** : `path` (str) - chemin du fichier de donnees
- **Logique** : Meme structure que `init()`, gere toutes les branches conditionnelles

#### `InputFormPanel.write_data_file(path)`
Ecrit les valeurs GUI dans un fichier de donnees au format Fortran.
- **Parametre** : `path` (str) - chemin de sortie
- **Retour** : `str` - chemin du fichier ecrit
- **Format** : Notation Fortran (d0), structure identique a celle lue par `init()`

#### `InputFormPanel.get_input_sequence()`
Construit la sequence de reponses pour le monkey-patching de `input()`.
- **Retour** : `list[str]` - reponses dans l'ordre attendu par le programme
- **Actions** : Ecrit un fichier temporaire `_lions_gui_temp.dat` avec les valeurs GUI

#### `InputFormPanel.get_post_answers()`
Retourne les reponses pour la phase post-simulation (pieges).

#### `InputFormPanel.get_deflector_geometry()`
Retourne la geometrie des deflecteurs pour l'affichage sur les plots.
- **Retour** : `list[dict]` avec cles rdf_m, xdfi_m, ydfi_m, xdfo_m, ydfo_m, tetdfi_deg, tetdfo_deg

#### `SimulationWorker._emit_data(d)`
Extrait les donnees de la simulation pour les plots GUI.
- **Donnees emises** (par famille) : x0_mm, y0_mm, r0_mm, tetnew, z0_mm, tpz, bz0, wmevpa, dph

---

## 7. Classes

### 7.1 LionData (lion_m.py)

**Classe contenant toutes les donnees du module de simulation.**

Equivalent Python du module Fortran `lion_m.f90`. Contient environ 400 attributs : scalaires, tableaux de taille fixe et tableaux dynamiques.

#### Attributs cles
- **Scalaires** : Voir section 5.2
- **Tableaux fixes** : cartes de champ (tbz, pot1, pot2...), deflecteurs (rdf, edf...), dipoles (rdm, bdm...)
- **Tableaux dynamiques** : alloues par `allo()` en fonction du nombre de particules

#### Methodes
| Methode | Description |
|---|---|
| `__init__()` | Initialise tous les attributs a zero/None |
| `allo()` | Alloue les tableaux dynamiques de taille `self.n` (position, impulsion, champs, flags...) |

#### Exemple d'utilisation
```python
from lion_m import LionData
d = LionData()
d.n = 100
d.allo()  # Alloue x[100], y[100], px[100], ...
```

### 7.2 FortranFile (lions.py)

**Emulateur de lecture Fortran list-directed (`read(unit, *)`).**

Gere la lecture de fichiers texte au format Fortran : saut des lignes vides, lecture multi-lignes, chaines entre quotes.

#### Methodes
| Methode | Description |
|---|---|
| `__init__(f)` | Initialise avec un fichier ouvert |
| `readline()` | Lit la prochaine ligne non vide |
| `read_tokens(n)` | Lit exactement n tokens, continuant sur les lignes suivantes si necessaire |
| `_tokenize(line)` | Decoupe une ligne en tokens, gerant les chaines quotees |

#### Exemple
```python
with open('donnees.dat', 'r') as f:
    ff = FortranFile(f)
    titre = ff.readline().strip()
    vals = ff.read_tokens(5)  # Lit 5 valeurs (potentiellement sur plusieurs lignes)
```

### 7.3 BidimManager (lions.py)

**Gestionnaire des histogrammes 2D (bidims) au format binaire GANIL.**

Ecrit des fichiers `.bid` compatibles avec les outils GANIL.

#### Attributs
| Attribut | Type | Description |
|---|---|---|
| `nbrbid` | int | Nombre de bidims ouverts |
| `n1bid`, `n2bid` | int | Numero premier/dernier bidim |
| `ibubid` | ndarray (4096, 50) | Buffer d'ecriture (4096 points par bloc) |
| `files` | dict | Fichiers ouverts (cle = numero d'unite) |

#### Methodes
| Methode | Description |
|---|---|
| `openbi(nbr, n1, nbx, nby, titre, labelx, labely, bornes)` | Ouvre les fichiers bidim, ecrit les en-tetes |
| `incbid(n, ix, iy)` | Incremente le bidim n au point (ix, iy) |
| `clobid()` | Ferme tous les bidims (ecrit le marqueur de fin) |
| `_wribid(iu, num)` | Ecrit le buffer sur disque |

#### Format du fichier .bid
- En-tete (320 octets) : num, type, date, titre, labels, bornes
- Blocs de donnees : 4096 int32 par bloc, chaque valeur = ix * 65536 + iy
- Marqueur de fin : 9999 * 65536 + 9999

### 7.4 LionsMainWindow (lions_gui.py)

**Fenetre principale de l'interface graphique.**

#### Attributs
| Attribut | Type | Description |
|---|---|---|
| `worker` | SimulationWorker | Thread de simulation |
| `input_panel` | InputFormPanel | Formulaire de parametres |
| `plot_widget` | PlotWidget | Zone de plots 2D |
| `console` | QTextEdit | Console de sortie texte |
| `progress_bar` | QProgressBar | Barre de progression |
| `_3d_window` | Plot3DWindow | Vue 3D (optionnel) |

#### Actions de la toolbar
| Action | Description |
|---|---|
| Run | Lance la simulation |
| Stop | Arrete la simulation en cours |
| Reset | Reinitialise les plots et la console |
| Unzoom | Reinitialise le zoom sur tous les plots |
| Exporter | Sauvegarde les plots en PNG/PDF/SVG |
| Bidims | Ouvre le visualiseur de fichiers .bid |
| Champs | Ouvre le visualiseur de cartes de champ |
| 3D | Ouvre la vue 3D des trajectoires |

#### Fonctionnement
Le rafraichissement des plots et de la console est gere par un timer a 10 FPS (`_flush_all()`). Les donnees de la simulation arrivent via des signaux Qt emis par le worker.

### 7.5 InputFormPanel (lions_input_form.py)

**Formulaire de parametres avec 16 sections repliables.**

#### Sections
1. General (swap, fichier donnees)
2. Description (titre)
3. HF / Cyclotron (npaspt, fhf, pothf, teta1, harm, dbsb)
4. Rayon / Tours (r1th, ntours)
5. Dees (dphid, dphig, pothfd, pothfg)
6. Harmoniques (ncoh, coefficients, phases)
7. Geometrie Z (zmin, zmax, rmax1)
8. Extraction (rex, deflecteurs, dipoles, grilles)
9. Ion(s) (familles, conditions initiales)
10. Correlations (iflcor, fichiers sigma)
11. Simulation (nbdt, ifreq)
12. Fichiers Sortie (ficz, ficxy)
13. Fichiers Champs (ficb, ficv1, ficv2, b_factor)
14. Trieur Vertical
15. Bidim / Diagnostics
16. Post-Simulation

#### Signaux
| Signal | Description |
|---|---|
| `params_changed` | Emis quand un parametre est modifie |
| `file_loaded(str)` | Emis quand un fichier de donnees est charge avec succes |

### 7.6 SimulationWorker (lions_worker.py)

**QThread executant la simulation LIONS avec hooks pour la GUI.**

#### Signaux
| Signal | Parametres | Description |
|---|---|---|
| `progress` | (int, int) | Iteration courante, total |
| `iteration_data` | dict | Donnees pour les plots (par famille) |
| `console_output` | str | Texte de sortie |
| `simulation_finished` | - | Fin normale |
| `simulation_error` | str | Message d'erreur |
| `input_needed` | str | Input inattendu (prompt) |

#### Fonctionnement
1. Installe `InputQueue` pour remplacer `builtins.input` (reponses pre-chargees)
2. Installe `OutputInterceptor` pour capturer `sys.stdout`
3. Execute la simulation dans un thread separe
4. Change le repertoire de travail vers le repertoire du fichier de donnees
5. Restaure l'etat original (input, stdout, cwd) dans le bloc `finally`

### 7.7 CollapsibleSection (lions_input_form.py)

**Widget Qt de section repliable avec titre cliquable.**

#### Parametres du constructeur
- `title` (str) : titre affiche
- `collapsed` (bool) : etat initial (replie ou deplie)

#### Methodes
- `add_row(label, widget)` : ajoute une ligne label + widget
- `_toggle()` : bascule l'etat replie/deplie

### 7.8 BidimViewerWidget / BidimViewerDialog (lions_bidim_viewer.py)

**Widget Qt pour la visualisation des fichiers bidim (.bid).**

#### Fonctionnalites
- Lecture des fichiers `.bid` avec `read_bidim(filepath)`
- Affichage en histogramme 2D (matplotlib) avec echelle logarithmique
- Selection du colormap (hot, viridis, plasma, jet, gray)
- Selection du nombre de bins (128, 256, 512, 1024)
- Liste des fichiers avec selection

---

## 8. Logique de fonctionnement

### 8.1 Diagramme de flux global

```
DEMARRAGE
    |
    v
[lions_gui.py] Lancement de l'interface PyQt5
    |
    v
Utilisateur configure les parametres (16 sections)
    |
    v
Utilisateur clique "Run"
    |
    v
[lions_gui.py] on_run()
    |-- Valide les champs obligatoires (ficin, ficb, ficv2)
    |-- Ecrit _lions_gui_temp.dat (write_data_file)
    |-- Construit la sequence de reponses (get_input_sequence)
    |-- Cree SimulationWorker(answers, work_dir)
    |-- Demarre le timer de rafraichissement (10 FPS)
    |-- worker.start()
    |
    v
[lions_worker.py] SimulationWorker.run()  [THREAD SEPARE]
    |
    |-- Phase 1 : Banniere + swap
    |
    |-- Phase 2 : init(d)
    |   |-- Lecture fichier de donnees
    |   |-- Lecture carte magnetique
    |   |   |-- Normalisation a 1
    |   |   |-- Multiplication par b_factor
    |   |   |-- Correction dB/B
    |   |   |-- Ajout harmoniques si ncoh != 0
    |   |-- Lecture potentiel central (binaire)
    |   |-- Lecture potentiel peripherique (texte)
    |   |-- Initialisation des particules
    |   |-- Distribution en espace de phase (si iflcor != 0)
    |   |   |-- Decomposition de Cholesky
    |   |   |-- Generation aleatoire (remp)
    |   |   |-- Application de la matrice de correlation
    |   |-- Ouverture fichiers de sortie
    |
    |-- Phase 3 : Trieur vertical (parametres)
    |
    |-- Phase 4 : Bidims (initgra)
    |   |-- Configuration des histogrammes 2D
    |   |-- Lecture fichier de reperes (pieges)
    |
    |-- Phase 5 : Pas initial
    |   |-- boite(d) -> calcbe(d) -> info(d)
    |   |-- Emission donnees initiales vers GUI
    |
    |-- Phase 6 : BOUCLE PRINCIPALE (ite = 1 a nbdt)
    |   |
    |   |-- piege(d)     : Gestion des pieges
    |   |-- boite(d)     : Verification boite de simulation
    |   |-- calcbe(d)    : Calcul champs B et E
    |   |   |-- Interpolation Bz, Bx, By
    |   |   |-- Calcul E centre (pot1)
    |   |   |-- Calcul E peripherie (pot2, rotation/symetrie)
    |   |   |-- Trieur vertical (Ez oscillant)
    |   |   |-- Extraction (deflecteurs, dipoles, grilles)
    |   |-- pousse(d)    : Boris pusher (avance particules)
    |   |   |-- Demi-E -> Rotation B -> Demi-E -> Avance position
    |   |-- t = ite * dt + t0
    |   |-- info(d)      : Suivi + ecriture fichiers
    |   |   |-- Comptage des tours
    |   |   |-- Ecriture ficz, ficxy (tous les ifreq pas)
    |   |   |-- Calcul correlations (si iflcor)
    |   |-- bid(d, bidim) : Enregistrement bidims
    |   |-- Emission progress/data vers GUI (throttle)
    |   |
    |   |-- Verification stop_flag
    |
    |-- Phase 7 : Nettoyage
    |   |-- Fermeture bidims
    |   |-- Fermeture fichiers
    |
    |-- Phase 8 : Post-simulation
    |   |-- Ecriture fichier pieges (si demande)
    |
    v
[lions_gui.py] on_finished()
    |-- Arret du timer
    |-- Flush final des plots et console
    |-- Mise a jour de l'interface
```

### 8.2 Schema d'integration Leap-Frog (Boris pusher)

Le Boris pusher est un schema symplectique de second ordre pour les equations du mouvement relativistes :

```
dp/dt = q(E + v x B)
dx/dt = c * p / gamma

ou gamma = sqrt(1 + |p|^2)  (p normalise par m0*c)
```

A chaque pas de temps dt :

```
1. Demi-acceleration electrique :
   p- = p_n + (q*dt)/(2*m0*c) * E

2. Rotation magnetique (matrice de Boris) :
   t = (q*dt)/(2*m0) * B / gamma(p-)
   s = 2*t / (1 + |t|^2)
   p+ = p- + (p- + p- x t) x s

3. Demi-acceleration electrique :
   p_{n+1} = p+ + (q*dt)/(2*m0*c) * E

4. Mise a jour de gamma :
   gamma_{n+1} = sqrt(1 + |p_{n+1}|^2)

5. Avance en position :
   x_{n+1} = x_n + c*dt/gamma_{n+1} * p_{n+1}
```

### 8.3 Interpolation des champs

#### Champ magnetique
Interpolation bilineaire en coordonnees polaires (r, theta) sur la grille (nr x ntet) :

```
i = int((r - rmin) / hr)
j = int(theta / htet)
a = r - rmin - i*hr         (distance fractionnaire en r)
b = theta - j*htet          (distance fractionnaire en theta)

Bz(r,theta,z) = [(hr-a)(htet-b)*Bz[i,j] + a*(htet-b)*Bz[i+1,j]
                + a*b*Bz[i+1,j+1] + (hr-a)*b*Bz[i,j+1]] / (hr*htet)
               - z^2/2 * [meme interpolation pour d2Bz]

Bx = z * [interpolation de dBz/dx]
By = z * [interpolation de dBz/dy]
```

#### Champ electrique (region centrale)
Interpolation bilineaire en (x, y) + derivees pour Ex et Ey :

```
Ex = V_HF(t) * interpolation(dV/dx)
Ey = V_HF(t) * interpolation(dV/dy)
Ez = z * V_HF(t) * interpolation(d2V/dz2)

V_HF(t) = pothf_d * cos(omhf*t + dphid)  (pour x >= 0)
         = pothf_g * cos(omhf*t + dphig)  (pour x < 0)
```

#### Champ electrique (region peripherique)
1. Rotation des coordonnees dans le repere du gap : `(x', y') = Rot(teta1) * (|x|, |y| - yomega)`
2. Interpolation bilineaire du potentiel normalise (0-1V)
3. Multiplication par V_HF(t)
4. Rotation inverse du champ electrique
5. Application des symetries selon le quadrant et la parite de l'harmonique

### 8.4 Systeme d'extraction

Lorsque `rex < 0`, le systeme d'extraction est actif :

1. **Deflecteurs electrostatiques** (`ndf` deflecteurs) :
   - Definis par un point d'entree (xdfi, ydfi) et un point de sortie (xdfo, ydfo) avec des angles (tetdfi, tetdfo)
   - Le champ electrique dans le deflecteur est perpendiculaire a la vitesse : `E = edf * (py/|pxy|, -px/|pxy|)`
   - Le premier deflecteur determine le debut de l'extraction (r > rdf ou ite >= iteext)

2. **Dipoles magnetiques** (`ndm` dipoles) :
   - Definis par un centre (xdm, ydm), un rayon rdm et un champ bdm
   - Ajoutent un champ magnetique local : `dBz = (r_local - rdm) * bdm`

3. **Grilles d'extraction** (`ngex` grilles, si tet2ex > 0) :
   - Definis par des points et des centres (en mm dans le fichier)
   - Les particules franchissant une grille sont enregistrees dans un fichier de suivi

---

## 9. Sorties

### 9.1 Fichier z (ficz)

Fichier texte contenant les informations verticales a chaque `ifreq` pas.

**En-tete** :
```
Programme LIONS
informations selon z
```

**Colonnes** :
| Colonne | Variable | Unite | Description |
|---|---|---|---|
| ite | iteration | - | Numero d'iteration |
| tr | numtou | - | Numero de tour |
| teta | tetnew | deg | Angle polaire |
| x | xmm | mm | Position X |
| y | ymm | mm | Position Y |
| z | zmm | mm | Position Z |
| r | rmm | mm | Rayon |
| Bx | bx[0] | T | Champ Bx |
| By | by[0] | T | Champ By |
| Bz | bz[0] | T | Champ Bz |
| Ez | ezkvcm | kV/cm | Champ Ez |
| tpz | tpz | mrad | Angle vertical |
| nuz | anuz_cyclo | - | Frequence verticale |
| Vver | pot_ver_vrai | V | Potentiel trieur vertical |

### 9.2 Fichier xy (ficxy)

Fichier texte contenant les informations dans le plan median.

**En-tete** :
```
Programme LIONS
<titre simulation>
masse atomique, A, q, r0, teta0, z0, pr0, pz0, w0, phi0
fhf, harm, pot_d, pot_g, db/b, B_factor
nb part, nb iter, nb i/t, dt(ns)
```

**Colonnes** :
| Colonne | Variable | Unite | Description |
|---|---|---|---|
| ite | iteration | - | Numero d'iteration |
| tr | numtou | - | Numero de tour |
| teta | tetnew | deg | Angle polaire |
| x | xmm | mm | Position X |
| y | ymm | mm | Position Y |
| xc | xc1mm | mm | Centre de courbure X |
| yc | yc1mm | mm | Centre de courbure Y |
| Bz | bz[0] | T | Champ magnetique |
| Es | eskvcm | kV/cm | Champ E tangentiel |
| Er | erkvcm | kV/cm | Champ E radial |
| r | rmm | mm | Rayon |
| tpr | tpr | mrad | Angle radial |
| W | wmevpa | MeV/A | Energie par nucleon |
| dphi | dph | deg | Dephasage HF |

**Fin de fichier** (dernier pas) :
```
info pour le mouvement inverse...
info pour continuer le mouvement...
info utile pour DEDUCE_SIGMA...
```

### 9.3 Fichiers de correlations (ficcor, ficmat, ficdc)

Si `iflcor != 0` :

**ficcor** : emittances et dispersions par tour
```
tr  r  teta  dr  ds  dphi  epsr  dwsw  wmpa  dw  dwdphi  dz  epsz
```

**ficmat** : matrice de correlation 6x6 complete

**ficdc** : correlations dans le repere decouple

### 9.4 Fichiers bidim (.bid)

Fichiers binaires au format GANIL contenant des histogrammes 2D :
- Trajectoire de l'ion central (x, y)
- Centres de courbure ou barycentres
- Trajectoires de tous les ions (si n > 1)
- Correlations dphi-dW/W, dr-dpr/p0, dz-dpz/p0

Peuvent etre visualises avec le `BidimViewerDialog` integre.

### 9.5 Fichiers de grilles d'extraction

Si des grilles d'extraction sont actives, un fichier par grille est cree (`ficdebgex.1`, `.2`, ...) contenant les coordonnees des particules franchissant la grille :
```
i  ite  x  y  z  px  py  pz  Bz
```

### 9.6 Sortie console (GUI)

La console de la GUI affiche en temps reel :
- La banniere du programme
- Les messages d'initialisation (lecture fichiers, normalisations)
- Les informations de suivi (position, energie, phase)
- Les messages d'erreur
- Le message de fin de simulation

### 9.7 Plots temps reel (GUI)

La GUI affiche 5 plots mis a jour en temps reel (10 FPS) :
1. **X vs Y** (mm) : trajectoire dans le plan median + deflecteurs
2. **Energie vs Tour** (MeV/A vs tour) : energie par nucleon au cours de l'acceleration
3. **R vs theta** (mm vs deg) : rayon en fonction de l'angle polaire
4. **Z vs Pz** (mm vs mrad) : espace de phase vertical
5. **R vs dphi** (mm vs deg) : dephasage HF en fonction du rayon, ou dphi = phi_HF - h*theta_total - 90

La **vue 3D** (optionnelle) affiche la trajectoire (X, Y, Z) en 3 dimensions avec zoom rectangulaire.

---

## 10. Gestion des erreurs

### 10.1 Erreurs d'initialisation

| Situation | Comportement |
|---|---|
| Fichier de donnees introuvable | Exception `FileNotFoundError`, capturee par le worker |
| Fichier carte magnetique introuvable | Exception `FileNotFoundError` |
| Nombre de particules incoherent (`n != np_`) | `sys.exit(1)` avec message "changer n ou np..." |
| Fichier potentiel central incomplet (pas de d2pot1) | Avertissement, `d2pot1 = 0` (Ez sera nul) |
| Carte magnetique incomplete (pas de dBz/dx, dBz/dy) | Avertissement, Bx=By=0 (plan median uniquement) |
| Erreur bidim openbi (nombre incorrect, bits incorrects) | Code retour non nul + message |

### 10.2 Erreurs de simulation

| Situation | Comportement |
|---|---|
| Particule hors boite (r > rmax) | Masquee par `box = False`, pas de calcul de champ |
| `x/r` hors [-1, 1] pour arccos | `clip(-1, 1)` avec comptage `nbiz` |
| Division par zero (Bz = 0) | Bz mis a `-0.00001` pour eviter la division par zero |
| Particule piegee dans un obstacle | `ok = False`, particule ignoree dans les calculs |

### 10.3 Gestion dans la GUI

| Situation | Comportement |
|---|---|
| Fichier ficin vide | QMessageBox.warning, simulation non lancee |
| Fichiers ficb ou ficv2 manquants | QMessageBox.warning, simulation non lancee |
| Exception dans le worker | Signal `simulation_error` -> QMessageBox.critical |
| Input inattendu | Signal `input_needed` -> QInputDialog avec valeur par defaut |
| Simulation arretee par l'utilisateur | `stop_flag = True`, boucle s'arrete au prochain pas |
| Erreur de chargement fichier donnees | QMessageBox.warning avec le message d'erreur |

### 10.4 Protection des donnees

- Les parametres GUI sont sauvegardables/chargeables en JSON (`save_params` / `load_params`)
- Le fichier temporaire `_lions_gui_temp.dat` est ecrit dans le repertoire du fichier source
- Le worker restaure toujours l'etat original (input, stdout, cwd) dans le bloc `finally`

---

## 11. Exemple complet d'execution

### 11.1 Fichier de donnees d'entree

Fichier `don.120.ref_phi10_mars_2017` :
```
 "don.forw.H3 i700 posbmax "
1080
1.50d0 250
14400000.d0 -51890.d0 20.d0 3.d0 +1.0d-4
0 0
51890.d0 51890.d0
0
0
-.5d0 .5d0 .164d0
-1.  -1. -1.  -1.
1
1.513  6990000 0 0 0 0 250 267
0
1
1 100.36496d0 100.36496d0 22.d0
0.03316181934576   266.8973516728 0.d0   426.2811141832   0.d0 5.6650d-3   -250.00d0
0
350000 30
exp.for.z.ref_phi10_mars_2017
exp.for.ref_phi10_mars_2017
'cime700rec.1804.pbob1.lio.dat'
'pot3d.impair.30pilbleu30.620.dat'
'newgap612.dat'
```

### 11.2 Interpretation des parametres

- **Simulation** : 100Mo22+ (Molybdene 100, charge 22+) dans CIME (GANIL)
- **1080 pas par tour**, harmonique 3, frequence 14.4 MHz
- **Potentiel HF** : 51890 V
- **Ouverture dee** : 20 degres
- **Correction dB/B** : +1.0e-4
- **Rayon initial** : 33.16 mm, angle 266.9 deg
- **Energie initiale** : 5.665e-3 MeV/A
- **Phase HF initiale** : -250 deg
- **350000 pas de temps** (~324 tours)
- **1 seul ion** (pas de correlations)
- **Extraction active** (rex = -1), mais sans deflecteurs ni grilles specifiques

### 11.3 Execution via la GUI

1. Lancer : `python lions_gui.py` (ou double-cliquer `lions.bat`)
2. Le fichier `don.120.ref_phi10_mars_2017` est pre-renseigne dans le formulaire
3. Cliquer "Charger fichier donnees" -> tous les champs se remplissent
4. Verifier/ajuster les parametres si necessaire
5. Cliquer "Run"

### 11.4 Sortie console attendue

```
----------------------------------------------------
LIONS       : Python (converti de Fortran 90)
auteur      : Patrick Bertrand - GANIL
version  1  : decembre 1998...decembre 2004
version  2  : mars 2017, modif seed, swap etc...
conversion Python : 2026
----------------------------------------------------

modif swap de mars 2017 :
on swap les octets ? (y/n)
allocations effectuees...
nombre de particules : 1
extraction : le paquet sera entier
carte tosca.small (1/8eme) ...
carte magnetique normalisee : Bmax_lu = 1.560000e+00 T
facteur B applique : 1.560000 T
[lecture potentiel centre : 164 x 300 points]
[lecture potentiel peripherie : 50 x 1000 points]
--------------------
test trieur vertical :
--------------------
```

### 11.5 Resultats attendus

Les plots GUI montrent :
- **X vs Y** : spirale de l'injection (~33 mm) jusqu'a l'extraction (~1500 mm)
- **R vs theta** : croissance du rayon par marches d'escalier (gain d'energie a chaque passage dans le gap)
- **W vs theta** : croissance quasi-lineaire de l'energie de 5.665e-3 a ~24 MeV/A
- **Bz vs theta** : variation du champ magnetique vu par l'ion (decroissance avec le rayon)

---

## 12. Ameliorations possibles

### 12.1 Performance

1. **Vectorisation complete de calcbe()** : Les boucles `for k in range(np_)` dans `calcbe()` sont le goulot d'etranglement principal. Elles pourraient etre remplacees par des operations numpy vectorisees utilisant des "fancy indexing" (gather/scatter).

2. **Compilation JIT avec Numba** : Les fonctions `calcbe()`, `pousse()`, `calcb()` et `addh()` sont de bonnes candidates pour `@numba.njit`, ce qui pourrait apporter un facteur 10-100x d'acceleration.

3. **Parallelisation GPU** : Pour les simulations multi-particules (n >> 1), les calculs vectoriels (interpolation, Boris pusher) pourraient etre portes sur GPU via CuPy ou CUDA.

4. **Precalcul des indices** : Les indices de grille `(ivec, jvec)` sont recalcules a chaque pas. Ils pourraient etre caches si les particules ne se deplacent pas trop.

### 12.2 Fonctionnalites physiques

5. **Charge d'espace** : Ajouter l'interaction coulombienne entre les particules pour les simulations haute intensite.

6. **Champ magnetique 3D** : Supporter des cartes de champ 3D completes (pas seulement l'expansion mediane en z).

7. **Collisions** : Ajouter les pertes par stripping/charge exchange pour les ions multi-charges.

8. **Multi-gap** : Supporter des geometries avec plus de 2 gaps (cyclotrons a 3 ou 4 dees).

### 12.3 Interface graphique

9. **Visualisation temps reel amélioree** : Ajouter des histogrammes 2D en temps reel dans la GUI (remplacement des bidims fichier).

10. **Profils de faisceau** : Ajouter des plots de profils transverses (x, y, z) et de l'espace de phase (x-px, y-py, z-pz).

11. **Sauvegarde/restauration d'etat** : Permettre de sauvegarder et reprendre une simulation en cours (checkpoint/restart).

12. **Mode batch** : Ajouter un mode ligne de commande (sans GUI) pour les scans parametriques automatises.

### 12.4 Qualite du code

13. **Tests unitaires** : Ajouter des tests pour les fonctions critiques (fortran_float, FortranFile, choles, remp, boite, calcb).

14. **Validation** : Comparer les resultats Python avec la version Fortran originale sur des cas de reference.

15. **Documentation inline** : Ajouter des docstrings detaillees aux fonctions de simulation (calcbe, info).

16. **Separation des I/O** : Decouplage complet des `input()`/`print()` du moteur de simulation pour faciliter les tests et l'utilisation en bibliotheque.

### 12.5 Formats de donnees

17. **Format HDF5** : Supporter les cartes de champ et les resultats en HDF5 pour de meilleures performances et portabilite.

18. **Export des resultats** : Ajouter l'export des trajectoires en CSV/HDF5 pour post-traitement avec d'autres outils.

19. **Import TOSCA** : Lecture directe des fichiers TOSCA 3D sans pre-traitement.

---

## Annexe A : Systemes de coordonnees

### Coordonnees principales
- **(X, Y)** : Axes principaux du cyclotron (plan median)
- **(r, theta)** : Coordonnees polaires dans le plan median
- **z** : Coordonnee verticale (perpendiculaire au plan median)

### Region peripherique (gap)
- **(x', y')** : Repere tourne de l'angle d'ouverture du dee (teta1)
- Transformation : `x' = |X|*cos(teta1) + (|Y| - yomega)*sin(teta1)`
- Rotation inverse pour le champ electrique

### Espace de phase
- **(dr, dpr, dz, dpz, ds, dp)** : Coordonnees curvilignes par rapport a la particule centrale
  - dr : ecart radial
  - dpr : ecart d'impulsion radiale
  - dz : ecart vertical
  - dpz : ecart d'impulsion verticale
  - ds : ecart le long de l'orbite
  - dp : ecart d'impulsion totale

## Annexe B : Constantes physiques

| Constante | Valeur | Unite |
|---|---|---|
| Vitesse de la lumiere (c) | 299 792 458 | m/s |
| Charge elementaire (e) | 1.60217733e-19 | C |
| Unite de masse atomique (uma) | 1.6605402e-27 | kg |
| Masse de l'electron (me) | 0.0005486 | uma |
| Conversion MeV -> J | 1.60217733e-13 | J/MeV |

## Annexe C : Formules physiques cles

### Energie cinetique relativiste
```
W = m0*c^2 * (gamma - 1)
gamma = 1 / sqrt(1 - v^2/c^2) = sqrt(1 + |p|^2)
```

### Rayon de courbure
```
r_c = -m0*c * |p| / (q * Bz)
```

### Frequence cyclotron
```
f_cyclo = q * B / (2*pi * m0 * gamma)
f_HF = harm * f_cyclo
```

### Masse effective de l'ion
```
m0 = uma * (A_atomique - 0.0005486 * Q)
```
(Correction de la masse des electrons manquants)

### Pas de temps
```
dt = harm / (fhf * npaspt)
```

---

*Document genere le 13 fevrier 2026*
*Programme LIONS - Auteur original : Patrick Bertrand, GANIL*
*Conversion Python et interface graphique : 2026*
