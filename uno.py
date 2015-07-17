import random
from collections import namedtuple, defaultdict
from datetime import datetime

COLORS = RED, YELLOW, BLUE, GREEN = ['R', 'Y', 'B', 'G']
BLACK = 'b'
SKIP   = 'S'
DRAW_2 = '+2'
COLOR_WISH = 'C'
DRAW_4 = '+4'
CHANGE_DIRECTION = 'CD'
ARBITRARY_KIND = '_'
CARDS_PER_PLAYER = 7
PUT = 'put'
DRAW = 'draw'

State = namedtuple("State", ["flipped_card", # The card that is currently flipped on the table
                             "history", # The cards that were flipped/put so far
                             "draw_counter", # counts how many cards the next user has to draw if he/she is not able to put a card.
                             "nr_of_players",
                             "player_index", # The index of the player whos turn it is
                             "p_has_drawn", # Is set to true if the player has applied the draw action. If true, the player can either put a card or do nothing without having to draw a card.
                             "color_wish",
                             "player_cards"] # array of integers in which each int stands for the amount of cards a player at an index has.
) 

Action = namedtuple("Action", ["type", "card", "color_wish"])

def generate_deck():
    "Generates a shuffled deck of uno cards"
    deck = []
    kinds = list(map(str, range(1, 10))) * 2 + ['0'] # Each number comes up twice per deck and color except 0
    kinds += [SKIP, DRAW_2, CHANGE_DIRECTION] * 2
    
    for c in COLORS:
        deck += map(lambda n: n + c, kinds)
    
    deck += [DRAW_4 + BLACK, COLOR_WISH + BLACK] * 4
    random.shuffle(deck)
    return deck

def deal_cards(nr_of_players, cards):
    """Deals the cards to the given nr_of_players and returns a list of hands
       as well as the remaining cards."""
    return ([cards[i:i+CARDS_PER_PLAYER] for i in range(nr_of_players)],
            cards[nr_of_players * CARDS_PER_PLAYER:])

def has_won(hand): return len(hand) == 0

def card_color(card): return card[-1]

def card_kind(card): return card[:-1]

def draw(action, state, hands, cards, strategies):
    "Applys the draw action and returns a tuple: (state, hands, cards, strategies)."
    hand = hands[state.player_index]
    
    if state.p_has_drawn:
        # Player has drawn cards and is still not able to put one
        flipped_card, history = state.flipped_card, list(state.history)
        if card_color(flipped_card) == BLACK:
            flipped_card = ARBITRARY_KIND + state.color_wish
            history += [state.flipped_card]
        
        state = State(flipped_card, history, state.draw_counter, state.nr_of_players, 
                      (state.player_index + 1) % state.nr_of_players, False, '', list(state.player_cards))
        return (state, hands, cards, strategies)
    
    # Player has to draw cards
    history = list(state.history)
    player_cards = list(state.player_cards)
    if len(cards) >= state.draw_counter:
        history = []
        cards += state.history
        random.shuffle(cards)

    hand += cards[:state.draw_counter] #TODO: sort for better caching?
    player_cards[state.player_index] = len(hand)
    cards = cards[state.draw_counter:]
    state = State(state.flipped_card, history, 1, state.nr_of_players, state.player_index,
                  True, state.color_wish, player_cards)
    return (state, hands, cards, strategies)

def put(action, state, hands, cards, strategies):
    "Applys the put action and returns a tuple: (state, cards, strategies)"
    history = state.history + ([state.flipped_card] if card_kind(state.flipped_card) != ARBITRARY_KIND
                                                      else [])
    hand = hands[state.player_index]
    flipped_card = action.card
    hand.remove(action.card)
    color_wish = ''
    player_index = (state.player_index + 1) % state.nr_of_players
    draw_counter = state.draw_counter
    player_cards = list(state.player_cards)
    player_cards[state.player_index] -= 1

    if card_color(action.card) == BLACK:
        draw_counter += 4 if card_kind(action.card) == DRAW_4 else 0
        color_wish = action.color_wish

    if card_kind(action.card) == DRAW_2:
        draw_counter += 2

    if card_kind(action.card) == SKIP:
        player_index = (state.player_index + 2) % state.nr_of_players

    if card_kind(action.card) == CHANGE_DIRECTION:
        strategies.reverse()
        hands.reverse()
        player_cards.reverse()

    if card_kind(action.card) in [DRAW_2, DRAW_4]:
        draw_counter -= state.draw_counter % 2 # Needed to make up for the 1 that is inside the counter by default

    state = State(flipped_card, history, draw_counter, state.nr_of_players, player_index,
                  False, color_wish, player_cards)

    return (state, hands, cards, strategies)

def apply_action(action, state, hands, cards, strategies):
    "Applys an action to a state and returns a tuple: (state, cards)"
    return (draw(action, state, hands, cards, strategies) if action.type == DRAW else
            put(action, state, hands, cards, strategies)) 

def whatever_works(state, hand):
    "A strategy that that takes the first action of the possible ones that it finds"
    if state.draw_counter > 1:
        return Action(DRAW, '', '')
    for card in hand:
        if card_color(card) == BLACK:
            hand_colors = list(map(card_color, hand))
            return Action(PUT, card, max(COLORS, key = lambda c: hand_colors.count(c)))
        if card_color(card) == state.color_wish:
            return Action(PUT, card, '')

        action = Action(PUT, card, '')
        if valid_action(action, state, hand):
            return action
    return Action(DRAW, '', '')

def save_blacks_increase_counter(state, hand):
    "A strategy that tries to save the black cards but increases the draw counter if possible"
    hand_kinds = list(map(card_kind, hand))
    hand_colors = list(map(card_color, hand))
    color_wish = max(COLORS, key = lambda c: hand_colors.count(c))
    
    if state.draw_counter > 1 and card_kind(state.flipped_card) in hand_kinds:
        # put +2/+4 on already put +2/+4
        card = hand[hand_kinds.index(card_kind(state.flipped_card))]
        return Action(PUT, card, color_wish if card_color(card) == BLACK else '')

    for card in filter(lambda c: card_color(c) != BLACK, hand):
        # hold black cards back if possible
        action = Action(PUT, card, '')
        if valid_action(action, state, hand):
            return action

    if BLACK in hand_colors and state.draw_counter == 1:
        return Action(PUT, hand[hand_colors.index(BLACK)], max(COLORS, key = lambda c: hand_colors.count(c)))

    return Action(DRAW, '', '')

def valid_action(action, state, hand):
    """Returns boolean whether an action is valid or not."""
    
    if action.color_wish == BLACK:
        return False
    if action.type == PUT and action.card not in hand:
        return False
    if action.type == PUT and state.draw_counter > 1 and card_kind(action.card) != card_kind(state.flipped_card):
        # The player is trying to put a card even though he has to draw
        return False
    if action.type == PUT and card_color(action.card) == BLACK and not action.color_wish:
        # The player did not specify a color wish
        return False
    if (action.type == PUT and card_color(action.card) != BLACK and
        state.color_wish and state.color_wish != card_color(action.card)):
        # The previous player has wished for a certain color and the player is not delivering...
        return False
    if (action.type == PUT and card_color(action.card) != BLACK and 
        card_kind(action.card) != card_kind(state.flipped_card) and
        card_color(action.card) != card_color(state.flipped_card) and
        card_color(action.card) != state.color_wish):
       # The player wants to put a card that's neither in the same color nor the same nr as the flipped card
       return False

    return True

def uno(*strategies, verbose=False):
    "Plays a game of uno between 2 - 10 strategies."
    assert len(strategies) >=  2 and len(strategies) <= 10, "Uno is a game for 2 - 10 players"
    cards = generate_deck()
    strategies = list(strategies)
    hands, cards = deal_cards(len(strategies), cards)

    first_card = cards.pop()
    color_wish = random.choice(COLORS) if card_color(first_card) == BLACK else ''

    state = State(flipped_card = first_card, history = [],
                  draw_counter = 1, nr_of_players = len(strategies),
                  player_index = 0, p_has_drawn = False, color_wish = color_wish,
                  player_cards = list(map(len, hands)))
    
    while not any(map(lambda h: has_won(h), hands)):
        
        next_action = strategies[state.player_index](state, hands[state.player_index])

        if not valid_action(next_action, state, hands[state.player_index]):
            print("\n\n\nINVALID ACTION by --- {2} --- \nSTATE={0}\nACTION={1}\n\n\n".format(state,
                                                                                             next_action,
                                                                                             strategies[state.player_index].__name__))
            break

        if verbose:
            print("\nHANDS:")
            for i in range(state.nr_of_players):
                print("{2}: {0} ---- {1} cards".format(hands[i], len(hands[i]), strategies[i].__name__))

        new_state, hands, cards, strategies = apply_action(next_action, state, hands, cards, strategies)
        
        if verbose:
            print("\nSTATE:\n{0}\nACTION by --- {2} ---:\n{1}\n\nCARDS: {3}\n\n".format(state, next_action, strategies[state.player_index].__name__, cards))
            input("Press enter to continue...")
        state = new_state

    return strategies[hands.index([])]

def compare_strategies(*strategies, n=1000):
    "Simulates n games and prints out how often each strategy won."
    scoreboard = defaultdict(int)
    for k in range(n):
        scoreboard[uno(*strategies)] += 1
    for (strategy, win_counter) in sorted(scoreboard.items(), key=lambda t: t[1], reverse=True):
        print("{0} won {1}%".format(strategy.__name__, (win_counter / float(n)) * 100))


compare_strategies(whatever_works, save_blacks_increase_counter)
