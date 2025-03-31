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

def strategie_tetue(player_id, pos_restaurants, choix_initial):
    return choix_initial[player_id]

def strategie_stochastique(player_id, pos_player, pos_restaurants):
    distances = [abs(pos_player[0] - r[0]) + abs(pos_player[1] - r[1]) for r in pos_restaurants]
    inverses = [1 / (d + 1) for d in distances]
    total = sum(inverses)
    proba = [i / total for i in inverses]
    return random.choices(pos_restaurants, weights=proba, k=1)[0]

def strategie_greedy(player_id, players, pos_restaurants, capacity, seuil):
    def nb_players_in_resto(r):
        return sum(1 for p in players if p.get_rowcol() == pos_restaurants[r])
    for r, pos in enumerate(pos_restaurants):
        if nb_players_in_resto(r) < capacity[r] * seuil:
            return pos
    return random.choice(pos_restaurants)

def strategie_fictitious(player_id, resto_attendance_history, pos_restaurants):
    scores = resto_attendance_history[player_id]
    return pos_restaurants[np.argmin(scores)]

def strategie_regret_matching(player_id, regrets, pos_restaurants):
    total_regret = sum(max(0, r) for r in regrets[player_id])
    if total_regret == 0:
        return random.choice(pos_restaurants)
    probs = [max(0, r) / total_regret for r in regrets[player_id]]
    return random.choices(pos_restaurants, weights=probs, k=1)[0]

def strategie_espionnage(player_id, previous_choix, pos_restaurants):
    count = [previous_choix.count(r) for r in pos_restaurants]
    return pos_restaurants[np.argmin(count)]

def main():
    global lMin, lMax, cMin, cMax
    iterations = 40
    num_days = 5
    if len(sys.argv) == 2:
        iterations = int(sys.argv[1])
        print("Iterations: ", iterations)

    init()

    nb_lignes = game.spriteBuilder.rowsize
    nb_cols = game.spriteBuilder.colsize
    assert nb_lignes == nb_cols
    lMin = 2
    lMax = nb_lignes - 2
    cMin = 2
    cMax = nb_cols - 2

    players = [o for o in game.layers['joueur']]
    nb_players = len(players)
    pos_restaurants = [(3, 4), (3, 7), (3, 10), (3, 13), (3, 16)]
    capacity = [1] * len(pos_restaurants)
    coupe_files = [o for o in game.layers["ramassable"]]

    def item_states(items):
        return [o.get_rowcol() for o in items]

    def player_states(players):
        return [p.get_rowcol() for p in players]

    print("lecture carte")
    print("-------------------------------------------")
    print('joueurs:', nb_players)
    print("restaurants:", len(pos_restaurants))
    print("lignes:", nb_lignes)
    print("colonnes:", nb_cols)
    print("coup_files:", len(coupe_files))
    print("-------------------------------------------")

    def is_legal_position(pos):
        row, col = pos
        return ((pos not in item_states(coupe_files)) and
               (pos not in player_states(players)) and
               (pos not in pos_restaurants) and
               row > lMin and row < lMax - 1 and col >= cMin and col < cMax)

    def draw_random_location():
        while True:
            random_loc = (random.randint(lMin, lMax), random.randint(cMin, cMax))
            if is_legal_position(random_loc):
                return random_loc

    def players_in_resto(r, players, pos_restaurants):
        are_here = []
        pos = pos_restaurants[r]
        for i in range(0, nb_players):
            if players[i].get_rowcol() == pos:
                are_here.append(i)
        return are_here

    def nb_players_in_resto(r, players, pos_restaurants):
        return len(players_in_resto(r, players, pos_restaurants))

    for o in coupe_files:
        (x1, y1) = draw_random_location()
        o.set_rowcol(x1, y1)
        game.mainiteration()

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


    # Liste des stratégies à comparer
    strategies_list = ['regret', 'fictitious', 'stochastique']
    strategy_functions = {
        'regret': strategie_regret_matching,
        'fictitious': strategie_fictitious,
        'stochastique': strategie_stochastique,
    }

    # Paramètres
    nb_strategies = len(strategies_list)
    nb_players = 6  # pair, divisible by 2
    num_days = 5
    capacity = [1] * 5  # chaque resto a 1 place
    pos_restaurants = [(3, 4), (3, 7), (3, 10), (3, 13), (3, 16)]

    # Matrice des résultats
    M = [[0 for _ in range(nb_strategies)] for _ in range(nb_strategies)]

    # Simulation
    for i in range(nb_strategies):
        for j in range(nb_strategies):
            scores = [0] * nb_players
            for day in range(num_days):
                choix = []
                for p in range(nb_players):
                    strat = strategies_list[i] if p < nb_players // 2 else strategies_list[j]
                    strat_fn = strategy_functions[strat]
                    choix.append(strat_fn(p, pos_restaurants))

                attendance = [0] * len(pos_restaurants)
                for r, pos in enumerate(pos_restaurants):
                    present = [idx for idx, c in enumerate(choix) if c == r]
                    served = random.sample(present, min(capacity[r], len(present)))
                    for pid in served:
                        scores[pid] += 1

            # Moyenne des scores pour la stratégie i (sur les joueurs i)
            moyenne_i = sum(scores[:nb_players // 2]) / (nb_players // 2)
            M[i][j] = round(moyenne_i, 2)

    # Affichage de la matrice
    print("\nMatrice des scores (M[i][j] = score moyen de la stratégie i contre j):\n")
    for row in M:
       print(row)    