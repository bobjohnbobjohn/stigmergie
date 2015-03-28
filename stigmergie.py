#!/usr/bin/python
"""stigmergie by bobjohn
simulation d'un systeme multi-agent simple
des fourmis se deplacent dans un environnement avec ou sans nourriture
elles rapportent la nourriture a la fourmiliere
les autres fourmis utilisent les pheromones pour taper dans la meme reserve de nourriture

touche "escape" pour quitter
touche "backspace" pour quitter en creant une image PGM de la carte des pheromones
"""

import sys, time, random
from PyQt4 import QtGui as qg
from PyQt4 import QtCore as qc

#### PARAMETRES ####

# nombre de cases de l'environnement
LARGEUR = 250 # c = colones
HAUTEUR = 150 # l = lignes
MARGE = 50 # marge droite et gauche dans l'interface

# taille initiale : 1 px par fourmi, le zoom est un facteur grossissant pour le visuel
ZOOM = 3

# contenu de l'environnement
OBSTACLE_NOMBRE = 10 # les obstacles sont carres
OBSTACLE_TAILLE = 10 # taille maximale
NOURRITURE = 100 # nombre de points de nourriture

POPULATION = 100 # fourmis
FOURMILIERE = [HAUTEUR/2, LARGEUR/2] # position de la fourmiliere (ligne, colonne) au centre
ENTREE = 2 # nb cases autour de l'origine de la fourmiliere = entree plus grande

# seuil de saturation des pheromones,
# evite que les fourmis ne restent trop longtemps, et n'entretiennent, sur une piste devenue inutile
SATURATION = 100

# quantite de pheromone depose par une fourmi a chaque pas
DEPOT = 40

# perte d'intensite de pheromone a chaque cycle, par evaporation naturelle
DISSIPATION = 2

# nombre de cases autour de la fourmi, utilisees pour percevoir des odeurs
SENSIBILITE = 3

VITESSE = 50 # ms l'interface permet pas d'aller en dessous pour le moment XXX

# modes des fourmis
ECLAIREUR = 0 # cherche de la nourriture en explorant l'environnement : par defaut
RAPPORTEUR = 1 # eclaireur qui revient avec de la nourriture
PORTEUR = 2 # eclaireur qui a suit une piste pour devenir rapporteur

AUTOUR_INDEX = [0,1,2,3,4,5,6,7,8]
AUTOUR = [(-1, -1),
(-1, 0),
(-1, 1),
(0, -1),
(0, 0),
(0, 1),
(1, -1),
(1, 0),
(1, 1)]

nb_cases_sensibilite = 2 * SENSIBILITE**2 + SENSIBILITE # nb cases dans le champs de perception qui en contient le plus

# directions a privilegier en fonction de la direction precedente
# les espaces montrent que toutes les 3 valeurs on change de direction
dirs = [0,1,3,  0,1,2,  1,2,5,  0,3,6,  0,0,0,  2,5,8,  3,6,7,  6,7,8,  5,7,8]

znord = [(l,c) for l in range(-SENSIBILITE, 0) for c in range(-SENSIBILITE, SENSIBILITE+1)]
zsud = [(l,c) for l in range(1, SENSIBILITE+1) for c in range(-SENSIBILITE, SENSIBILITE+1)]
zest = [(l,c) for l in range(-SENSIBILITE, SENSIBILITE+1) for c in range(1, SENSIBILITE+1)]
zouest = [(l,c) for l in range(-SENSIBILITE, SENSIBILITE+1) for c in range(-SENSIBILITE, 0)]
znordest = [(l,c) for l in range(-SENSIBILITE, 1) for c in range(0, SENSIBILITE+1)]
znordouest = [(l,c) for l in range(-SENSIBILITE, 1) for c in range(-SENSIBILITE, 1)]
zsudest = [(l,c) for l in range(0, SENSIBILITE+1) for c in range(0, SENSIBILITE+1)]
zsudouest = [(l,c) for l in range(0, SENSIBILITE+1) for c in range(-SENSIBILITE, 1)]


class Fenetre(qg.QMainWindow):

    def __init__(self):
        super(Fenetre, self).__init__()
        self.timer = qc.QBasicTimer()
        self.cycle = 0
        self.gui()
        
    def gui(self):

        self.fl = Fourmiland(self)
        self.cmd = Commandes(self)
        self.v = Visuel(self.fl)
        self.v.scale(ZOOM, ZOOM)
        
        sp = qg.QSplitter(qc.Qt.Vertical)
        sp.addWidget(self.v)
        sp.addWidget(self.cmd)
        self.setCentralWidget(sp)
        
        self.setGeometry(100, 100, LARGEUR*ZOOM + 2*MARGE, HAUTEUR*ZOOM + self.cmd.height() + 2*MARGE)
        self.setWindowTitle('Fourmiland')
        
        self.show()
        
    def keyPressEvent(self, e):
        if e.key() == qc.Qt.Key_Escape:
            sys.exit()
        elif e.key() == qc.Qt.Key_Backspace:
            env2pgm(self.fl.phero, self.cycle)
        elif e.key() == qc.Qt.Key_Space:
            self.cmd.start_stop.click()

    def timerEvent(self, event):
        self.fl.action()
        fourmis = Fourmiland_fourmis(self.fl.fourmis)
        nourriture = Fourmiland_nourriture(self.fl.nourriture)
        self.v.f.setPixmap(fourmis)
        self.v.n.setPixmap(nourriture)
        self.cycle += 1
##        env2pgm(self.fl.phero, self.cycle)
        self.statusBar().showMessage( "nb cycles : {}".format(self.cycle) )

    def change_vitesse(self, vitesse):
        if vitesse == 0:
            self.timer.stop()
        else:
            self.timer.start(cs2ms(vitesse), self)

class Commandes(qg.QWidget):

    def __init__(self, parent):
        super(Commandes, self).__init__(parent)
        self.vitesse = 0
        self.parent = parent
        self.gui()
        
    def gui(self):
        self.setFixedHeight(150)
        grid = qg.QGridLayout()
        self.setLayout(grid)
        
        # gestion de la vitesse
        self.vitesse_sld = qg.QSlider(qc.Qt.Horizontal, self)
        self.vitesse_sld.setRange(ms2cs(1000), ms2cs(20))
        self.vitesse_sld.setValue(ms2cs(VITESSE))
        self.connect(self.vitesse_sld, qc.SIGNAL("valueChanged(int)"), self.change_vitesse)
        vitesse_lbl = qg.QLabel("vitesse [cases/s] :", self)
        vitesse_v = qg.QLCDNumber()
        vitesse_v.display(ms2cs(VITESSE))
        vitesse_v.setSegmentStyle(qg.QLCDNumber.Flat)
        self.connect(self.vitesse_sld, qc.SIGNAL("valueChanged(int)"), vitesse_v.display)
        
        self.start_stop = qg.QPushButton("start", self)
        self.connect(self.start_stop, qc.SIGNAL("clicked()"), self.change_vitesse)
        
        # affichages statistiques
        nb_fourmi_lbl = qg.QLabel("population :", self)
        nb_eclaireur_lbl = qg.QLabel("eclaireur :", self)
        nb_rapporteur_lbl = qg.QLabel("rapporteur :", self)
        nb_porteur_lbl = qg.QLabel("porteur :", self)
        nb_nourriture_lbl = qg.QLabel("nourriture rapportee :", self)
        
        self.nb_fourmi_v = qg.QLabel()
        self.nb_eclaireur_v = qg.QLabel()
        self.nb_rapporteur_v = qg.QLabel()
        self.nb_porteur_v = qg.QLabel()
        self.nb_nourriture_v = qg.QLabel()
        
        # placement des widgets sur une grille
        grid.addWidget(self.start_stop, 0, 0)
        grid.addWidget(self.vitesse_sld, 0, 1)
        grid.addWidget(vitesse_lbl, 0, 2)
        grid.addWidget(vitesse_v, 0, 3)
        grid.addWidget(nb_fourmi_lbl, 0, 4)
        grid.addWidget(self.nb_fourmi_v, 0, 5)
        grid.addWidget(nb_eclaireur_lbl, 1, 4)
        grid.addWidget(self.nb_eclaireur_v, 1, 5)
        grid.addWidget(nb_rapporteur_lbl, 2, 4)
        grid.addWidget(self.nb_rapporteur_v, 2, 5)
        grid.addWidget(nb_porteur_lbl, 3, 4)
        grid.addWidget(self.nb_porteur_v, 3, 5)
        grid.addWidget(nb_nourriture_lbl, 4, 4)
        grid.addWidget(self.nb_nourriture_v, 4, 5)
        
    def change_vitesse(self, vitesse_consigne = -1):
        if vitesse_consigne < 0: # clic sur le bouton start_stop
            if self.vitesse == 0: # start
                self.vitesse = self.vitesse_sld.value()
                self.parent.change_vitesse(self.vitesse)
                self.start_stop.setText("stop")
            else: # stop
                self.vitesse = 0
                self.parent.change_vitesse(0)
                self.start_stop.setText("start")
        else: # changement avec le slider
            self.vitesse = vitesse_consigne
            self.parent.change_vitesse(self.vitesse) # start
            self.start_stop.setText("stop")

    def actualise_stats(self, nb_type, nb_nourriture):
        self.nb_fourmi_v.setText( str(sum(nb_type)) )
        self.nb_eclaireur_v.setText( str(nb_type[ECLAIREUR]) )
        self.nb_rapporteur_v.setText( str(nb_type[RAPPORTEUR]) )
        self.nb_porteur_v.setText( str(nb_type[PORTEUR]) )
        self.nb_nourriture_v.setText( str(nb_nourriture) )
        self.repaint()


class Visuel(qg.QGraphicsView):
    def __init__(self, fl):
        qg.QGraphicsView.__init__(self)
        
        decor = Fourmiland_decors(fl.obstacles)
        fourmis = Fourmiland_fourmis(fl.fourmis)
        nourriture = Fourmiland_nourriture(fl.nourriture)
        
        scene = qg.QGraphicsScene(self)
        scene.setSceneRect(0, 0, LARGEUR, HAUTEUR)
        scene.addPixmap(decor)
        self.n = scene.addPixmap(nourriture)
        self.f = scene.addPixmap(fourmis)
        self.setScene(scene)


class Fourmiland_decors(qg.QPixmap):
    def __init__(self, obstacles):
        super(Fourmiland_decors, self).__init__(LARGEUR, HAUTEUR)
        self.fill(qg.QColor(255, 255, 255))
        self.dessiner(obstacles)
    
    def dessiner(self, obstacles):
        qp = qg.QPainter()
        qp.begin(self)
        qp.setPen( qg.QPen(qg.QColor(150, 150, 150), 1) )
        for lc, taille in obstacles.iteritems():
                qp.drawPoint(lc[1], lc[0]) # lc[0], lc[1] = l, c = y, x
                
        qp.setPen( qg.QPen(qg.QColor(qc.Qt.green), 1) )
        for lc in [(l,c) for l in range(-ENTREE, ENTREE+1) for c in range(-ENTREE, ENTREE+1)]:
            qp.drawPoint(FOURMILIERE[1]+lc[1], FOURMILIERE[0]+lc[0]) # lc[0], lc[1] = l, c = y, x
        
        qp.end()


class Fourmiland_fourmis(qg.QPixmap):
    def __init__(self, fourmis):
        super(Fourmiland_fourmis, self).__init__(LARGEUR, HAUTEUR)
        self.fill(qg.QColor(255, 255, 255, 0))
        self.dessiner(fourmis)
        
    def dessiner(self, fourmis):
        qp = qg.QPainter()
        qp.begin(self)
        qp.setPen( qg.QPen(qg.QColor(qc.Qt.red), 1) )
        for lc in fourmis:
            qp.drawPoint(lc[1], lc[0]) # lc[0], lc[1] = l, c = y, x
        qp.end()


class Fourmiland_nourriture(qg.QPixmap):
    def __init__(self, nourriture):
        super(Fourmiland_nourriture, self).__init__(LARGEUR, HAUTEUR)
        self.fill(qg.QColor(255, 255, 255, 0))
        self.dessiner(nourriture)
        
    def dessiner(self, nourriture):
        qp = qg.QPainter()
        qp.begin(self)
        qp.setPen( qg.QPen(qg.QColor(qc.Qt.blue), 1) )
        for lc, n in nourriture.iteritems(): # XXX rajouter degrade couleur avec n
            qp.drawPoint(lc[1], lc[0]) # lc[0], lc[1] = l, c = y, x
        qp.end()


class Fourmiland(qg.QWidget):
    
    nb_nourriture = 0
    
    def __init__(self, parent):
        super(Fourmiland, self).__init__(parent)
        self.parent = parent
        self.phero, self.nourriture, self.obstacles = genese(LARGEUR, HAUTEUR, OBSTACLE_NOMBRE, OBSTACLE_TAILLE)
        self.fourmis = {} # contient les objets fourmis : (l, c) = Fourmi
        self.nb_type = [0,0,0] # nombre de chaque type de fourmi
        
    def action(self):
        """mise a jour de l'environnement"""
        
        if len(self.fourmis) < POPULATION:
            f = Fourmi(self.fourmis)
            self.fourmis[ tuple(f.lc) ] = f
            self.nb_type[f.type] += 1
        
        for f in self.fourmis.values():
            self.nb_type[f.type] -= 1 # tient a jour le nombre de fourmis de chaque type
            f.move(self.phero, self.nourriture, self.obstacles, self.fourmis)
            self.nb_type[f.type] += 1
            
            # rajoute des pheromones avant de se deplacer si elle a trouve a manger
            if f.type == RAPPORTEUR and self.phero [ f.lc_prev[0] ] [ f.lc_prev[1] ] < SATURATION: # seuil de saturation
    #            # pas de depot a proximite de la fourmiliere, sinon les fourmis stagnent a l'entree
    #            if abs( (f.lc[0] - FOURMILIERE[0]+ENTREE)**2 - (f.lc[1] - FOURMILIERE[1]+ENTREE)**2 )**0.5 > 5: # distance euclidienne
                self.phero [ f.lc_prev[0] ] [ f.lc_prev[1] ] += DEPOT
            
            # met a jour sa nouvelle position
            self.fourmis.pop( (f.lc_prev[0], f.lc_prev[1]) ) #XXX probleme ici
            self.fourmis[(f.lc[0], f.lc[1])] = f
        
        # dissipation naturelle des pheromones
        self.phero = [map(lambda x : x-DISSIPATION if x>0 else x, l) for l in self.phero]
        
        self.parent.cmd.actualise_stats(self.nb_type, Fourmiland.nb_nourriture)


class Fourmi:
    """individu qui se deplace avec stigmergie a la recherche de nourriture"""

    def __init__(self, fourmis):
        
        self.id = len(fourmis)
        self.type = ECLAIREUR
        
        # position actuelle l=ligne, c=colonne
        self.lc = [0,0]
        self.lc_prev = [0,0]
        
        # ne pas prendre la place d'une fourmi existante
        d = 0 # augmente a chaque tour pour sortir plus loin de l'entree en cas de saturation
        while True:
            self.lc[0] = FOURMILIERE[0] + random.choice([-ENTREE-1, ENTREE+1]) + d
            self.lc[1] = FOURMILIERE[1] + random.choice([-ENTREE-1, ENTREE+1]) + d
            if tuple(self.lc) not in fourmis:
                break
            d += 1
        
        self.lc_prev[0] = self.lc[0]
        self.lc_prev[1] = self.lc[1]

        # position precedente aleatoire pour l'etat initial
        self.dir_prev = random.choice([0,1,2,3,5,6,7,8]) # 4 ne doit pas etre choisi a ce moment


    def retour_fourmiliere(self):
        if self.type == RAPPORTEUR:
            Fourmiland.nb_nourriture += 1
            self.type = PORTEUR

    def soustrait_nourriture(self, phero, nourriture, index):
        """prend une unite de nourriture et depose des pheromones autour
        cela permet de guider les autres fourmis vers ce point precis
        quand elles sont a proximite
        """
        # coordonnees de la case ou se trouve la nourriture
        ln = self.lc[0] + (index/3 - 1)
        cn = self.lc[1] + (index%3 - 1)
        
        if nourriture[(ln, cn)] > 1:
            nourriture[(ln, cn)] -= 1
        else:
            nourriture.pop((ln, cn))
            
        phero[ln][cn] += DEPOT
        # depot de pheromones tout autour de la nourriture pour augmenter l'interet de la zone
        for l, c in AUTOUR:
            if phero[ln+l][cn+c] == 0:
                phero[ln+l][cn+c] += DEPOT

    def analyser_alentours(self, phero, nourriture, obstacles, fourmis):
        exclusion = []
        alentours = [(self.lc[0]+l, self.lc[1]+c) for l, c in AUTOUR]
        for i in AUTOUR_INDEX: # plus rapide que range(9)
            if alentours[i] in nourriture:
                exclusion.append(i)
                if not self.type == RAPPORTEUR:
                    self.type = RAPPORTEUR
                    self.soustrait_nourriture(phero, nourriture, i)
            if alentours[i] in obstacles or alentours[i] in fourmis: # XXX essayer de combiner
                exclusion.append(i)
        return exclusion

    def cherche_odeurs(self, phero):
        # cherche des odeurs dans toutes les directions XXX performance douteuse
        # szn = sum zone nord
        szn = sum([phero[self.lc[0]+l][self.lc[1]+c] for l,c in znord if 0<self.lc[0]+l<HAUTEUR-1 and 0<self.lc[1]+c<LARGEUR-1])
        szs = sum([phero[self.lc[0]+l][self.lc[1]+c] for l,c in zsud if 0<self.lc[0]+l<HAUTEUR-1 and 0<self.lc[1]+c<LARGEUR-1])
        sze = sum([phero[self.lc[0]+l][self.lc[1]+c] for l,c in zest if 0<self.lc[0]+l<HAUTEUR-1 and 0<self.lc[1]+c<LARGEUR-1])
        szo = sum([phero[self.lc[0]+l][self.lc[1]+c] for l,c in zouest if 0<self.lc[0]+l<HAUTEUR-1 and 0<self.lc[1]+c<LARGEUR-1])
        szne = sum([phero[self.lc[0]+l][self.lc[1]+c] for l,c in znordest if 0<self.lc[0]+l<HAUTEUR-1 and 0<self.lc[1]+c<LARGEUR-1])
        szno = sum([phero[self.lc[0]+l][self.lc[1]+c] for l,c in znordouest if 0<self.lc[0]+l<HAUTEUR-1 and 0<self.lc[1]+c<LARGEUR-1])
        szse = sum([phero[self.lc[0]+l][self.lc[1]+c] for l,c in zsudest if 0<self.lc[0]+l<HAUTEUR-1 and 0<self.lc[1]+c<LARGEUR-1])
        szso = sum([phero[self.lc[0]+l][self.lc[1]+c] for l,c in zsudouest if 0<self.lc[0]+l<HAUTEUR-1 and 0<self.lc[1]+c<LARGEUR-1])
        
        # rajoute 1 pour avoir une probabilite minimale >0, sinon blocage
        # meme ordre que exclusion dans analyser_alentours
        # virer ce 1 il devrait y avoir 0
        return [szno, szn, szne, szo, 0, sze, szso, szs, szse]


    def move(self, phero, nourriture, obstacles, fourmis):
        """deplacement de la fourmi, pseudo aleatoire
        sans revenir sur sa position precedente, en evitant les obstacles
        """
        # XXX degueu
        # les calcul de la distance euclidienne est moins rapide
        # par contre (-x)**2 est bien plus rapide que abs(-x)
        if abs(FOURMILIERE[0] - self.lc[0]) <= ENTREE+1 and abs(FOURMILIERE[1] - self.lc[1]) <= ENTREE+1 and self.type != ECLAIREUR:
            self.retour_fourmiliere()

        exclusion = self.analyser_alentours(phero, nourriture, obstacles, fourmis)
        
        # ne pas revenir en arriere, sauf si elle est coincee ou qu'elle a trouve de la nourriture
        if len(exclusion) == 9 and not self.type == RAPPORTEUR:
            exclusion.append(self.dir_prev)

        # si coincee complet, elle attend
        if len(exclusion) == 9:
            return
        
        odeurs = self.cherche_odeurs(phero)
        
        # devient porteur si elle sent quelque chose
        if sum(odeurs) > 0 and self.type == ECLAIREUR:
            self.type = PORTEUR

        # redevient eclaireur si elle perd une piste : atteint un minimum de 1 par case percue
        if max(odeurs) <= nb_cases_sensibilite and self.type == PORTEUR:
            self.type = ECLAIREUR
        
        if self.type == RAPPORTEUR:
            d = self.move_rapporteur(exclusion)
        elif self.type == PORTEUR:
            d = self.move_porteur(exclusion, odeurs)
        elif self.type == ECLAIREUR:
            d = self.move_eclaireur(exclusion)

        try: # ne fait rien si d n'est pas defini
            self.dir_prev = d
            self.lc_prev = self.lc[:]
            self.lc[0] += (d/3 - 1)
            self.lc[1] += (d%3 - 1)
        except:
            pass

    def move_eclaireur(self, exclusion):
        # si possible, probabilite 2/3 de continuer dans la meme direction
        if self.dir_prev == 4:
            choix = [v for v in dir_cases(AUTOUR_INDEX) if v not in exclusion]
        else:
            choix = [v for v in dir_cases([self.dir_prev]) if v not in exclusion]
        if choix:
            return random.choice(choix)
        else:
            return 4

    def move_porteur(self, exclusion, odeurs):
        # choix de la piste les 2 plus odorantes possibles
        choix = [i for i,v in sorted(enumerate(odeurs), key=lambda x : x[1], reverse=True) if i not in exclusion][0:3]
        if choix:
            return random.choice(choix)
        else:
            return 4

    def move_rapporteur(self, exclusion): # XXX l'attroupement le long de x et y doit venir de la
        """deplacement dans une des 3 cases qui correspond a la direction
        le choix depend du quadran dans lequel se trouve la fourmi
        le point d'origine du repere est la fourmiliere
        """
        if self.lc[0] >= FOURMILIERE[0] and self.lc[1] > FOURMILIERE[1]:
            choix = [d for d in dir_cases([0,1,3]) if d not in exclusion] # directions 0,1,3
            if choix:
                return random.choice(choix)
            else:
                return 4
        elif self.lc[0] > FOURMILIERE[0] and self.lc[1] <= FOURMILIERE[1]:
            choix = [d for d in dir_cases([1,2,5]) if d not in exclusion] # directions 1,2,5
            if choix:
                return random.choice(choix)
            else:
                return 4
        elif self.lc[0] <= FOURMILIERE[0] and self.lc[1] < FOURMILIERE[1]:
            choix = [d for d in dir_cases([5,7,8]) if d not in exclusion] # directions 5,7,8
            if choix:
                return random.choice(choix)
            else:
                return 4
        elif self.lc[0] < FOURMILIERE[0] and self.lc[1] >= FOURMILIERE[1]:
            choix = [d for d in dir_cases([3,6,7]) if d not in exclusion] # directions 3,6,7
            if choix:
                return random.choice(choix)
            else:
                return 4


def dir_cases(dd):
    """donne les 3 cases qui vont dans la direction choisie"""
    l = []
    for d in dd:
        l.extend(dirs[ 3*d : 3*d+3 ])
    return l


def genese(largeur, hauteur, obstacle_nombre, obstacle_taille):
    """creation de l'environnement dans lequel evoluent les fourmis"""

    # liste qui contient le poids des pheromones
    phero = [ [l]*largeur for l in [0]*hauteur ]

    obstacles = generer_obstacles(largeur, hauteur, obstacle_taille, obstacle_nombre)
    
    # bord haut et bas
    for lc in [(l, c) for l in range(hauteur) for c in [0,largeur-1]]:
        obstacles[lc] = 1
    
    # bord droite et gauche
    for lc in [(l, c) for c in range(largeur) for l in [0,hauteur-1]]:
        obstacles[lc] = 1
    
    nourriture = generer_nourriture(largeur, hauteur)
    
    return phero, nourriture, obstacles


def generer_obstacles(largeur, hauteur, obstacle_taille, obstacle_nombre):
    """obstacles carres de taille et position aleatoire"""
    obstacles = {}
    for i in range(obstacle_nombre):
        taille = random.randint(1, obstacle_taille)
        # ligne et colonne du point en haut a gauche de l'obstacle
        lref = random.randint(1, hauteur - taille - 1)        
        cref = random.randint(1, largeur - taille - 1)
        for (l, c) in [ (lref+lt, cref+ct) for lt in range(taille) for ct in range(taille) ]:
            obstacles[(l, c)] = 1
        
    # l'entree de la fourmiliere est vue comme un obstacle pour eviter de la saturer
    for lc in [(l,c) for l in range(-ENTREE, ENTREE+1) for c in range(-ENTREE, ENTREE+1)]:
        obstacles[ (FOURMILIERE[0]+lc[0], FOURMILIERE[1]+lc[1]) ] = 1
        
    return obstacles


def generer_nourriture(largeur, hauteur):
    nourriture = {}
    for n in range(NOURRITURE):
        l = random.randint(1, hauteur - 2)
        c = random.randint(1, largeur - 2)
        nourriture[(l, c)] = random.randint(1, 10)
    return nourriture


def env2pgm(phero, cycle):
    fic = open("carte_pheromones_{0:03d}.pgm".format(cycle),"w")
    fic.write("P2\n") # format PGM
    fic.write( ( ("%i %i\n") % (LARGEUR, HAUTEUR) ) ) # largeur, hauteur de l'image
    fic.write("50\n")
    for l in phero:
        for c in l:
            fic.write(str(c))
            fic.write(" ")
        fic.write("\n")
    fic.flush()
    fic.close()

def ms2cs(ms):
    """conversion de millisecondes en cases par seconde
    pour afficher la vitesse de deplacement des fourmis"""
    try:
        return int( 1 / ( float(ms) / 1000.0 ) )
    except: # si ms = 0: division par 0
        return 0

def cs2ms(cs):
    """inverse de ms2cs"""
    return int( 1000 * ( 1 / float(cs) ) )

def main():
    """point d'entree de la simulation"""
    app = qg.QApplication(sys.argv)
    f = Fenetre()
    sys.exit(app.exec_())

if __name__ == "__main__":
    sys.exit(main())
