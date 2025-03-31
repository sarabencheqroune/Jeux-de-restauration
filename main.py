# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

import random
import numpy as np
import sys
from itertools import chain

import pygame

from pySpriteWorld.gameclass import Game, check_init_game_done
from pySpriteWorld.spritebuilder import SpriteBuilder
from pySpriteWorld.players import Player
from pySpriteWorld.sprite import MovingSprite
from pySpriteWorld.ontology import Ontology
import pySpriteWorld.glo

from search.grid2D import ProblemeGrid2D
from search import probleme

# ---- ---- ---- ---- ---- ----
# ---- Main                ----
# ---- ---- ---- ---- ---- ----

game = Game()

def init(_boardname=None):
    global player, game
    name = _boardname if _boardname is not None else 'restaurant-map2'
    game = Game('Cartes/' + name + '.json', SpriteBuilder)
    game.O = Ontology(True, 'SpriteSheet-32x32/tiny_spritesheet_ontology.csv')
    game.populate_sprite_names(game.O)
    game.fps = 5
    game.mainiteration()
    player = game.player

def legal_position(pos, players, coupe_files, pos_restaurants, lMin, lMax, cMin, cMax):
    row, col = pos
    return ((pos not in [p.get_rowcol() for p in players]) and
            (pos not in [c.get_rowcol() for c in coupe_files]) and
            (pos not in pos_restaurants) and
            lMin < row < lMax - 1 and
            cMin <= col < cMax)


# -------------------------------
# Définition des stratégies disponibles
# -------------------------------
    
# -------------------------------
# Stratégie Têtue
# -------------------------------

def strategie_tetue(player_id, pos_restaurants, choix_initial):
    return choix_initial[player_id]
 
# -------------------------------
# Stratégie stochastique
# -------------------------------

def strategie_stochastique(player_id, pos_player, pos_restaurants):
    distances = [abs(pos_player[0] - r[0]) + abs(pos_player[1] - r[1]) for r in pos_restaurants]
    inverses = [1 / (d + 1) for d in distances]
    total = sum(inverses)
    proba = [i / total for i in inverses]
    return random.choices(pos_restaurants, weights=proba, k=1)[0]

# -------------------------------
# Stratégie Greedy
# -------------------------------
    
def strategie_greedy(player_id, players, pos_restaurants, capacity, seuil):
    def nb_players_in_resto(r):
        return sum(1 for p in players if p.get_rowcol() == pos_restaurants[r])
    for r, pos in enumerate(pos_restaurants):
        if nb_players_in_resto(r) < capacity[r] * seuil:
            return pos
    return random.choice(pos_restaurants)

# -------------------------------
# Stratégie Fictitious Play 
# -------------------------------

def strategie_fictitious(player_id, resto_attendance_history, pos_restaurants):
    scores = resto_attendance_history[player_id]
    return pos_restaurants[np.argmin(scores)]

# -------------------------------
# Stratégie Regret-Matching
# -------------------------------

def strategie_regret_matching(player_id, regrets, pos_restaurants):
    total_regret = sum(max(0, r) for r in regrets[player_id])
    if total_regret == 0:
        return random.choice(pos_restaurants)
    probs = [max(0, r) / total_regret for r in regrets[player_id]]
    return random.choices(pos_restaurants, weights=probs, k=1)[0]

# -------------------------------
# Stratégie Collaborative
# -------------------------------

#Les joueurs partagent entre eux les restos les moins fréquentés, et chacun s’oriente vers celui qui semble le moins risqué pour éviter d’aller tous au même endroit. 
def strategie_collaborative(player_id, attendance_last_round, pos_restaurants):
    print("Affectation des restaurants (Stratégie Collaborative):")
    sorted_restos = sorted(range(len(pos_restaurants)), key=lambda r: attendance_last_round[r])
    resto_id = sorted_restos[player_id % len(pos_restaurants)]
    return pos_restaurants[resto_id]

# -------------------------------
# Stratégie de Triche
# -------------------------------

#Certains joueurs "espions" vont observer le resto avec le plus faible nombre de visiteurs à chaque tour précédent… puis s’y précipitent en toute discrétion.
def strategie_triche(player_id, attendance_last_round, pos_restaurants):
    print("Affectation des restaurants (Stratégie Triche):")
    min_r = np.argmin(attendance_last_round)
    return pos_restaurants[min_r]

# -------------------------------
# Stratégie Espionnage
# -------------------------------

def strategie_espionnage(player_id, previous_choix, pos_restaurants):
    count = [previous_choix.count(r) for r in pos_restaurants]
    return pos_restaurants[np.argmin(count)]

# -------------------------------
# Stratégie FOURBES : Influence
# -------------------------------

#Certains joueurs sont influençables et copient le choix d’un "mentor" (un joueur modèle). on suppose les 2 premiers joueurs sont mentors, les autres les suiven
def strategie_mentorat(player_id, choix_resto_current, pos_restaurants, mentors, resto_attendance_history):
    print("Affectation des restaurants (Stratégie Mentorat):")
    if player_id in mentors:
            return strategie_fictitious(player_id, resto_attendance_history, pos_restaurants)
    mentor_id = random.choice(mentors)
    return choix_resto_current[mentor_id]

# -------------------------------
# Stratégie FOURBES : Bluff / Fake signals
# -------------------------------    

#le joueur fait croire qu’il va à un resto en changeant d’avis tard, ou laisse des traces.
def strategie_bluff(player_id, pos_player, choix_fictif, choix_reel, g):
    print("Affectation des restaurants (Stratégie Bluff):")
    # Le joueur commence à aller vers le choix fictif
    fake_path = probleme.astar(ProblemeGrid2D(pos_player, choix_fictif, g, 'manhattan'), verbose=False)
    # Puis bifurque vers le vrai resto (mi-chemin)
    real_path = probleme.astar(ProblemeGrid2D(choix_fictif, choix_reel, g, 'manhattan'), verbose=False)
    return fake_path[:len(fake_path)//2] + real_path

# -------------------------------
# Stratégie Répartition Planifiée
# -------------------------------
     
#les joueurs se répartissent équitablement les restos pour éviter toute collision.
def strategie_repartition_planifiee(player_id, pos_restaurants):
    print("Affectation des restaurants (Stratégie Répartition Planifiée):")
    resto_id = player_id % len(pos_restaurants)
    return pos_restaurants[resto_id]

# -------------------------------
# Stratégie complexe 1 : Fictitious Play + Triche
# -------------------------------

def strategie_combo1(player_id, resto_attendance_history, attendance_last_round, pos_restaurants):
    print("Affectation des restaurants (Stratégie Combo1 - Fictitious + Triche):")
    fake_fict = strategie_fictitious(player_id, resto_attendance_history, pos_restaurants)
    sneaky_r = pos_restaurants[np.argmin(attendance_last_round)]
    if random.random() < 0.7:
        return sneaky_r
    else:
        return fake_fict
    
def main():
    global lMin, lMax, cMin, cMax
    iterations = 40 # nb de pas max par episode
    num_days = 20 # nombre de journées dans la partie
    if len(sys.argv) == 2:
        iterations = int(sys.argv[1])
        print("Iterations: ", iterations)

    init()
     
    # -------------------------------
    # Initialisation
    # -------------------------------
 
    nb_lignes = game.spriteBuilder.rowsize
    nb_cols = game.spriteBuilder.colsize
    assert nb_lignes == nb_cols  # a priori on souhaite un plateau carre
    lMin = 2  # limites du plateau de jeu
    lMax = nb_lignes - 2
    cMin = 2
    cMax = nb_cols - 2


    players = [o for o in game.layers['joueur']]
    nb_players = len(players)
    pos_restaurants = [(3, 4), (3, 7), (3, 10), (3, 13), (3, 16)]  # 5 restaurants positionnés
    capacity = [1] * len(pos_restaurants) # capacité de service de chaque resto

    coupe_files = [o for o in game.layers["ramassable"]]  # objets "coupe-file"
    nb_coupe_files = len(coupe_files)

    # -------------------------------
    # Fonctions permettant de récupérer les listes des coordonnées
    # d'un ensemble d'objets ou de joueurs
    # -------------------------------

    def item_states(items):
        return [o.get_rowcol() for o in items]

    def player_states(players):
        return [p.get_rowcol() for p in players]

    # -------------------------------
    # ce qui se trouve sur la carte
    # -------------------------------
    print("lecture carte")
    print("-------------------------------------------")
    print('joueurs:', nb_players)
    print("restaurants:", len(pos_restaurants))
    print("lignes:", nb_lignes)
    print("colonnes:", nb_cols)
    print("coup_files:", nb_coupe_files)
    print("-------------------------------------------")

    # -------------------------------
    # Carte demo
    # 8 joueurs
    # 5 restos
    # -------------------------------
     
    # -------------------------------
    # Fonctions definissant les positions legales et placement aléatoire
    # -------------------------------

    def is_legal_position(pos):
        row, col = pos
        return ((pos not in item_states(coupe_files)) and
               (pos not in player_states(players)) and
               (pos not in pos_restaurants) and
               row > lMin and row < lMax - 1 and col >= cMin and col < cMax)

    def draw_random_location():
        # tire au hasard un couple de positions permettant de placer un item
        while True:
            random_loc = (random.randint(lMin, lMax), random.randint(cMin, cMax))
            if is_legal_position(random_loc):
                return random_loc


    def players_in_resto(r, players, pos_restaurants):
        """
        :param r: id of the resto
        :return: id of players in resto
        """
        are_here = []
        pos = pos_restaurants[r]
        for i in range(0, nb_players):
            if players[i].get_rowcol() == pos:
                are_here.append(i)
        return are_here

    def nb_players_in_resto(r, players, pos_restaurants):
        """
       :param r: id of resto
       :return: int number of players currently here
       """
        return len(players_in_resto(r, players, pos_restaurants))
    
    # -------------------------------
    # On place tous les coupe_files du bord au hasard
    # -------------------------------

    for o in coupe_files:
        (x1, y1) = draw_random_location()
        o.set_rowcol(x1, y1)
        game.mainiteration()
    
    # -------------------------------
    # On place tous les joueurs au hasard sur la ligne du bas
    # -------------------------------

    y_init = [3, 5, 7, 9, 11, 13, 15, 17]
    x_init = 18
    random.shuffle(y_init)

    for o in coupe_files:
        while True:
            loc = (random.randint(lMin, lMax), random.randint(cMin, cMax))
            if legal_position(loc, players, coupe_files, pos_restaurants, lMin, lMax, cMin, cMax):
                o.set_rowcol(*loc)
                break
        game.mainiteration()

    for i, p in enumerate(players):
        p.set_rowcol(x_init, y_init[i])
        game.mainiteration()
   
    # -------------------------------
    # Affectation des stratégies aux joueurs
    # -------------------------------

    strategie_utilisee = 'tetue' # change ici : 'greedy', 'espionnage', etc.
    print(f"\n--- STRATEGIE : {strategie_utilisee.upper()} ---")

    player_scores = [0] * nb_players
    resto_attendance_history = [[0]*len(pos_restaurants) for _ in range(nb_players)]
    regrets = [[0]*len(pos_restaurants) for _ in range(nb_players)]
    previous_choix = [random.choice(pos_restaurants) for _ in range(nb_players)]
    # Chaque joueur choisit un restaurant au hasard au début du jeu
    choix_resto_init = [random.choice(pos_restaurants) for _ in range(nb_players)]
    seuil = 1.0

    # -------------------------------
    # Boucle principale par journée
    # -------------------------------

    for day in range(num_days):
        print(f"\nJOUR {day+1}")
        choix_resto = []
        for p in range(nb_players):
            if strategie_utilisee == 'tetue':
                choix = strategie_tetue(p, pos_restaurants, choix_resto_init)
            elif strategie_utilisee == 'greedy':
                choix = strategie_greedy(p, players, pos_restaurants, capacity, seuil)
            elif strategie_utilisee == 'stochastique':
                choix = strategie_stochastique(p, (x_init, y_init[p]), pos_restaurants)
            elif strategie_utilisee == 'fictitious':
                choix = strategie_fictitious(p, resto_attendance_history, pos_restaurants)
            elif strategie_utilisee == 'regret':
                choix = strategie_regret_matching(p, regrets, pos_restaurants)
            elif strategie_utilisee == 'espionnage':
                choix = strategie_espionnage(p, previous_choix, pos_restaurants)
            elif strategie_utilisee == 'combo1':
                choix = strategie_combo1(p, resto_attendance_history, [previous_choix.count(r) for r in pos_restaurants], pos_restaurants)
            elif strategie_utilisee == 'bluff':
                choix_fictif = random.choice(pos_restaurants)
                choix_reel = random.choice(pos_restaurants)
                path[p] = strategie_bluff(p, (x_init, y_init[p]), choix_fictif, choix_reel, g)
                choix = choix_reel
            
            else:
                choix = random.choice(pos_restaurants)
            choix_resto.append(choix)
            print(f"  Joueur {p} cible le restaurant : {choix}")

        path = [None]*nb_players
        for p in range(nb_players):
            g = np.ones((nb_lignes, nb_cols), dtype=bool)
            g[0:2, :] = g[-2:, :] = g[:, 0:2] = g[:, -2:] = False
            prob = ProblemeGrid2D((x_init, y_init[p]), choix_resto[p], g, 'manhattan')
            path[p] = probleme.astar(prob, verbose=False)

        for i in range(iterations):
            for j in range(nb_players):
                if i < len(path[j]):
                    players[j].set_rowcol(*path[j][i])
            game.mainiteration()

        attendance = [0]*len(pos_restaurants)
        for r, pos in enumerate(pos_restaurants):
            present = [i for i in range(nb_players) if players[i].get_rowcol() == pos]
            attendance[r] = len(present)
            if present:
                served = random.sample(present, min(capacity[r], len(present)))
                for pid in served:
                    player_scores[pid] += 1
            for p in range(nb_players):
                if choix_resto[p] == pos:
                    resto_attendance_history[p][r] += 1
                    regrets[p][r] += 1 if p not in present else 0

        previous_choix = choix_resto[:]

    print("\n--- SCORES FINAUX ---")
    for i, score in enumerate(player_scores):
        print(f"Joueur {i} : {score} points")

    pygame.quit()

if __name__ == '__main__':
    main()
