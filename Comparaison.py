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

    strategie_A = 'greedy'
    strategie_B = 'fictitious'
    print(f"\n--- COMPARAISON STRATEGIE A ({strategie_A.upper()}) vs STRATEGIE B ({strategie_B.upper()}) ---")

    player_scores = [0] * nb_players
    resto_attendance_history = [[0]*len(pos_restaurants) for _ in range(nb_players)]
    regrets = [[0]*len(pos_restaurants) for _ in range(nb_players)]
    previous_choix = [random.choice(pos_restaurants) for _ in range(nb_players)]
    choix_resto_init = [random.choice(pos_restaurants) for _ in range(nb_players)]
    seuil = 1.0

    for day in range(num_days):
        print(f"\nJOUR {day+1}")
        choix_resto = []
        for p in range(nb_players):
            strat = strategie_A if p in [0, 1, 2, 3] else strategie_B

            if strat == 'tetue':
                choix = strategie_tetue(p, pos_restaurants, choix_resto_init)
            elif strat == 'greedy':
                choix = strategie_greedy(p, players, pos_restaurants, capacity, seuil)
            elif strat == 'stochastique':
                choix = strategie_stochastique(p, (x_init, y_init[p]), pos_restaurants)
            elif strat == 'fictitious':
                choix = strategie_fictitious(p, resto_attendance_history, pos_restaurants)
            elif strat == 'regret':
                choix = strategie_regret_matching(p, regrets, pos_restaurants)
            elif strat == 'espionnage':
                choix = strategie_espionnage(p, previous_choix, pos_restaurants)
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
