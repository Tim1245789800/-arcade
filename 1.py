import arcade
import random

# === Настройки ===
SCREEN_WIDTH, SCREEN_HEIGHT = 1250, 750
SIDE_PANEL_WIDTH = 250
PLAY_AREA_CENTER_X = (SCREEN_WIDTH - SIDE_PANEL_WIDTH) // 2
CARD_WIDTH, CARD_HEIGHT = 75, 110
LERP_SPEED = 0.12

BG_COLOR = (43, 84, 36)
PANEL_COLOR = (20, 25, 20, 230)
GOLD_COLOR = (255, 215, 0)
HIGHLIGHT_COLOR = (0, 255, 0)
BARREL_COLOR = (200, 100, 50)

SUITS_ORDER = ['♠', '♥', '♣', '♦']
SUIT_COLORS = {'♠': (0, 0, 0), '♣': (0, 0, 0), '♥': (255, 0, 0), '♦': (255, 0, 0)}
CARD_POINTS = {'9': 0, 'J': 2, 'Q': 3, 'K': 4, '10': 10, 'A': 11}
MARRIAGE_POINTS = {'♥': 100, '♦': 80, '♣': 60, '♠': 40}


def round_to_five(n):
    return 5 * round(n / 5)


class Card:
    def __init__(self, suit, rank):
        self.suit, self.rank = suit, rank
        self.x, self.y = PLAY_AREA_CENTER_X, SCREEN_HEIGHT // 2
        self.dest_x, self.dest_y = self.x, self.y
        self.face_up = False
        self.points = CARD_POINTS[rank]
        self.is_hovered = False
        self.can_play = False

    def move_to(self, x, y):
        self.dest_x, self.dest_y = x, y

    def update(self):
        self.x += (self.dest_x - self.x) * LERP_SPEED
        target_y = self.dest_y + (15 if self.is_hovered else 0)
        self.y += (target_y - self.y) * LERP_SPEED

    def draw(self):
        rect = arcade.XYWH(self.x, self.y, CARD_WIDTH, CARD_HEIGHT)
        arcade.draw_rect_filled(rect, arcade.color.WHITE if self.face_up else (110, 155, 210))
        if self.can_play and self.face_up:
            arcade.draw_rect_outline(rect, HIGHLIGHT_COLOR, 4)
        elif self.is_hovered:
            arcade.draw_rect_outline(rect, GOLD_COLOR, 2)
        else:
            arcade.draw_rect_outline(rect, arcade.color.BLACK, 1)
        if self.face_up:
            color = SUIT_COLORS[self.suit]
            arcade.draw_text(self.rank, self.x - 25, self.y + 35, color, 14, bold=True)
            arcade.draw_text(self.suit, self.x, self.y - 5, color, 32, anchor_x="center", anchor_y="center")


class Player:
    def __init__(self, name, is_human):
        self.name, self.is_human = name, is_human
        self.hand, self.global_score, self.round_points = [], 0, 0
        self.barrel_attempts = 0
        self.bolts = 0
        self.tricks_taken = 0  # Количество взяток в раунде
        self.pending_marriage_points = 0  # Очки за марьяж, которые ждут первой взятки

    def has_any_marriage(self):
        for s in SUITS_ORDER:
            ranks = {c.rank for c in self.hand if c.suit == s}
            if 'Q' in ranks and 'K' in ranks: return True
        return False

    def get_max_possible(self):
        pts = sum(c.points for c in self.hand)
        m_pts = 0
        for s in SUITS_ORDER:
            ranks = {c.rank for c in self.hand if c.suit == s}
            if 'Q' in ranks and 'K' in ranks: m_pts += MARRIAGE_POINTS[s]
        return round_to_five(pts + m_pts)

    def sort_and_position(self):
        self.hand.sort(key=lambda c: (SUITS_ORDER.index(c.suit), CARD_POINTS[c.rank]))
        y_base = 110 if self.is_human else SCREEN_HEIGHT - 110
        gap = 65
        start_x = PLAY_AREA_CENTER_X - ((len(self.hand) - 1) * gap) // 2
        for i, card in enumerate(self.hand):
            card.move_to(start_x + i * gap, y_base)
            card.face_up = self.is_human


class ThousandGame(arcade.Window):
    def __init__(self):
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, "Игра 1000")
        arcade.set_background_color(BG_COLOR)
        self.players = [Player("ИГРОК", True), Player("ИИ", False)]
        self.prikup1, self.prikup2, self.table, self.unused_prikup = [], [], [], []
        self.trump_suit, self.game_state, self.message = None, "bidding", ""
        self.timer, self.action_queue, self.current_bid, self.turn_idx = 0, [], 100, 0
        self.bid_winner_idx, self.ai_delay_timer = 0, 0
        self.marriage_effect_timer, self.marriage_msg = 0, ""
        self.round_counter = 0
        self.setup_round()

    def setup_round(self):
        for p in self.players:
            if p.global_score >= 1000:
                self.message = f"ПОБЕДА: {p.name}!"
                self.game_state = "game_over"
                return

        self.round_counter += 1
        self.table, self.unused_prikup = [], []
        self.trump_suit = None
        for p in self.players:
            p.round_points = 0
            p.tricks_taken = 0
            p.pending_marriage_points = 0

        deck = [Card(s, r) for s in SUITS_ORDER for r in ['9', 'J', 'Q', 'K', '10', 'A']]
        random.shuffle(deck)
        for p in self.players:
            p.hand = [deck.pop() for _ in range(7)]
            p.sort_and_position()
        self.prikup1, self.prikup2 = [deck.pop() for _ in range(3)], [deck.pop() for _ in range(3)]
        for i, c in enumerate(self.prikup1): c.move_to(PLAY_AREA_CENTER_X - 120 + i * 20, SCREEN_HEIGHT // 2)
        for i, c in enumerate(self.prikup2): c.move_to(PLAY_AREA_CENTER_X + 120 + i * 20, SCREEN_HEIGHT // 2)

        self.game_state, self.current_bid, self.turn_idx = "bidding", 100, 0

        bidder = self.players[0] if self.players[0].barrel_attempts > 0 else (
            self.players[1] if self.players[1].barrel_attempts > 0 else None)
        if bidder:
            self.current_bid = 120
            self.bid_winner_idx = 0 if bidder == self.players[0] else 1
            self.message = f"{bidder.name} НА БОЧКЕ!"
            self.timer = 1.0
            self.action_queue.append(lambda: self.take_prikup(self.bid_winner_idx, random.randint(1, 2)))
        else:
            self.message = "ВАШ ХОД: ↑ - поднять, P - пас"

    def apply_round_scores(self, painted=False):
        mult = 2 if self.round_counter == 1 else 1

        for i, p in enumerate(self.players):
            is_bidder = (i == self.bid_winner_idx)

            # Логика болтов (только для не-заказывающих)
            if not is_bidder and not painted:
                if p.tricks_taken == 0:
                    p.bolts += 1
                    if p.bolts >= 3:
                        p.global_score -= 120
                        p.bolts = 0
                        self.message = f"{p.name}: Штраф за 3 болта!"

            gain = 0
            if painted and is_bidder:
                gain = -self.current_bid * mult
                self.players[1 - i].global_score += 60 * mult
                if p.barrel_attempts > 0: p.barrel_attempts = 0
            elif is_bidder:
                if p.round_points >= self.current_bid:
                    gain = self.current_bid * mult
                    if p.barrel_attempts > 0:
                        p.global_score = 1000
                        return
                else:
                    gain = -self.current_bid * mult
                    if p.barrel_attempts > 0: p.barrel_attempts = 0
            else:
                gain = round_to_five(p.round_points) * mult

            new_score = p.global_score + gain
            if new_score >= 880 and p.global_score < 880:
                p.global_score = 880
                p.barrel_attempts = 1
            elif p.barrel_attempts > 0:
                p.barrel_attempts += 1
                if p.barrel_attempts > 3:
                    p.global_score -= 120
                    p.barrel_attempts = 0
            else:
                p.global_score = new_score

            if p.global_score > 880 and p.barrel_attempts == 0:
                p.global_score = 880

    def play_card(self, card):
        p = self.players[self.turn_idx]
        # Проверка хваления (марьяжа)
        if not self.table and card.rank in ['Q', 'K']:
            if any(c.rank in ['Q', 'K'] and c.suit == card.suit and c != card for c in p.hand):
                self.trump_suit = card.suit
                m_points = MARRIAGE_POINTS[card.suit]

                # Если взятки уже были — начисляем сразу, иначе — в очередь
                if p.tricks_taken > 0:
                    p.round_points += m_points
                    self.marriage_msg = f"МАРЬЯЖ! {card.suit} +{m_points}"
                else:
                    p.pending_marriage_points += m_points
                    self.marriage_msg = f"МАРЬЯЖ! (после взятки +{m_points})"

                self.marriage_effect_timer = 2.0

        card.face_up = True
        self.table.append(card)
        card.move_to(PLAY_AREA_CENTER_X + (50 if len(self.table) > 1 else -50), SCREEN_HEIGHT // 2 + 30)

        if len(self.table) == 2:
            self.timer = 0.8
            self.action_queue.append(self.resolve_trick)
        else:
            self.turn_idx = 1 - self.turn_idx

    def resolve_trick(self):
        c1, c2 = self.table[0], self.table[1]
        win_idx = self.turn_idx
        if c1.suit == c2.suit:
            if c1.points > c2.points: win_idx = 1 - self.turn_idx
        elif c2.suit != self.trump_suit:
            win_idx = 1 - self.turn_idx

        winner = self.players[win_idx]
        winner.round_points += c1.points + c2.points
        winner.tricks_taken += 1

        # Если была отложенная хвалёнка — зачисляем её сейчас
        if winner.pending_marriage_points > 0:
            winner.round_points += winner.pending_marriage_points
            winner.pending_marriage_points = 0

        for c in self.table:
            self.unused_prikup.append(c)
            c.move_to(-150, SCREEN_HEIGHT // 2)
        self.table, self.turn_idx = [], win_idx

        if not self.players[0].hand:
            self.apply_round_scores()
            self.timer = 1.5
            self.action_queue.append(self.setup_round)

    def on_draw(self):
        self.clear()
        arcade.draw_rect_filled(arcade.XYWH(SCREEN_WIDTH - 125, 375, 250, 750), PANEL_COLOR)

        txt_y = SCREEN_HEIGHT - 40
        arcade.draw_text(f"СТАВКА: {self.current_bid}", SCREEN_WIDTH - 230, txt_y, (255, 255, 255), 14, bold=True)

        if self.trump_suit:
            arcade.draw_text(f"КОЗЫРЬ: {self.trump_suit}", SCREEN_WIDTH - 230, txt_y - 30, SUIT_COLORS[self.trump_suit],
                             18, bold=True)

        for i, p in enumerate(self.players):
            y = SCREEN_HEIGHT - 200 - (i * 220)
            name_color = BARREL_COLOR if p.barrel_attempts > 0 else GOLD_COLOR
            arcade.draw_text(p.name, SCREEN_WIDTH - 230, y, name_color, 16, bold=True)

            # Отображение болтов
            bolts_str = "• " * p.bolts
            arcade.draw_text(f"Болты: {bolts_str}", SCREEN_WIDTH - 230, y - 25, arcade.color.GRAY, 12)

            arcade.draw_text(f"Счет: {p.global_score}", SCREEN_WIDTH - 230, y - 50, arcade.color.LIGHT_BLUE, 14)
            arcade.draw_text(f"Взятки: {p.round_points}", SCREEN_WIDTH - 230, y - 75, arcade.color.WHITE, 12)
            if p.pending_marriage_points > 0:
                arcade.draw_text(f"(Ожидание: +{p.pending_marriage_points})", SCREEN_WIDTH - 230, y - 95, (200, 200, 0),
                                 10)

        arcade.draw_text(self.message, PLAY_AREA_CENTER_X, SCREEN_HEIGHT - 250, arcade.color.WHITE, 16,
                         anchor_x="center")

        for p in self.players:
            for c in p.hand: c.draw()
        for c in self.prikup1 + self.prikup2 + self.table + self.unused_prikup: c.draw()

        if self.marriage_effect_timer > 0:
            color = list(SUIT_COLORS.get(self.trump_suit, (255, 255, 255)))
            color.append(int(255 * (self.marriage_effect_timer / 2)))
            arcade.draw_text(self.marriage_msg, PLAY_AREA_CENTER_X, SCREEN_HEIGHT // 2 + 150, color, 25, bold=True,
                             anchor_x="center")

    # === Остальные методы без изменений логики (on_update, mouse/key handlers) ===
    def on_update(self, dt):
        for p in self.players:
            for c in p.hand: c.update()
        for c in self.prikup1 + self.prikup2 + self.table + self.unused_prikup: c.update()
        if self.game_state == "playing" and self.turn_idx == 0:
            for c in self.players[0].hand:
                if not self.table:
                    c.can_play = True
                else:
                    lead = self.table[0]
                    has_suit = any(x.suit == lead.suit for x in self.players[0].hand)
                    has_trump = any(x.suit == self.trump_suit for x in self.players[0].hand)
                    c.can_play = (c.suit == lead.suit) if has_suit else (
                        (c.suit == self.trump_suit) if has_trump else True)
        if self.marriage_effect_timer > 0: self.marriage_effect_timer -= dt
        if self.timer > 0:
            self.timer -= dt
            if self.timer <= 0 and self.action_queue: self.action_queue.pop(0)()
            return
        if self.game_state == "bidding" and self.turn_idx == 1:
            self.ai_delay_timer += dt
            if self.ai_delay_timer >= 0.8:
                self.ai_delay_timer = 0
                limit = self.players[1].get_max_possible() + 20
                if limit > self.current_bid:
                    self.current_bid += 5
                    self.message = f"ИИ поднял до {self.current_bid}. Ваш ход?"
                    self.turn_idx = 0
                else:
                    self.message = "ИИ спасовал! Выберите прикуп кликом."
                    self.game_state = "select_prikup"
        if self.game_state == "playing" and self.turn_idx == 1 and len(self.table) < 2:
            self.ai_delay_timer += dt
            if self.ai_delay_timer >= 0.7:
                self.ai_play_turn()
                self.ai_delay_timer = 0

    def ai_play_turn(self):
        hand = self.players[1].hand
        if not hand: return
        if not self.table:
            chosen = hand[0]
            for c in hand:
                if c.rank in ['Q', 'K'] and any(x.suit == c.suit and x.rank in ['Q', 'K'] and x != c for x in hand):
                    chosen = c;
                    break
            hand.remove(chosen)
        else:
            lead = self.table[0]
            in_suit = [c for c in hand if c.suit == lead.suit]
            if in_suit:
                in_suit.sort(key=lambda x: x.points)
                chosen = in_suit[-1] if in_suit[-1].points > lead.points else in_suit[0]
                hand.remove(chosen)
            else:
                trumps = [c for c in hand if c.suit == self.trump_suit]
                if trumps:
                    trumps.sort(key=lambda x: x.points)
                    chosen = trumps[0];
                    hand.remove(chosen)
                else:
                    hand.sort(key=lambda x: x.points);
                    chosen = hand.pop(0)
        self.play_card(chosen)

    def take_prikup(self, winner_idx, num):
        self.bid_winner_idx = winner_idx
        chosen = self.prikup1 if num == 1 else self.prikup2
        other = self.prikup2 if num == 1 else self.prikup1
        for c in other: self.unused_prikup.append(c); c.move_to(-100, SCREEN_HEIGHT // 2)
        self.players[winner_idx].hand.extend(chosen)
        self.prikup1 = self.prikup2 = []
        if self.players[winner_idx].is_human:
            for c in chosen: c.face_up = True
            self.players[0].sort_and_position()
            self.game_state, self.message = "give_to_ai", "ОТДАЙТЕ 1 КАРТУ ИИ (клик)"
        else:
            self.players[1].hand.sort(key=lambda x: x.points)
            gift = self.players[1].hand.pop(0);
            self.players[0].hand.append(gift)
            trash = self.players[1].hand.pop(0);
            self.unused_prikup.append(trash);
            trash.move_to(-150, SCREEN_HEIGHT // 2)
            self.players[0].sort_and_position();
            self.players[1].sort_and_position()
            self.game_state, self.turn_idx = "playing", 1
            self.message = f"ИИ ЗАКАЗАЛ {self.current_bid}. ЕГО ХОД"

    def on_mouse_press(self, x, y, button, modifiers):
        if self.game_state == "select_prikup":
            for c in self.prikup1 + self.prikup2:
                if abs(x - c.x) < 40 and abs(y - c.y) < 60:
                    self.take_prikup(0, 1 if c in self.prikup1 else 2);
                    return
        elif self.game_state == "give_to_ai":
            for i, c in enumerate(self.players[0].hand):
                if abs(x - c.x) < 35 and abs(y - c.y) < 55:
                    card = self.players[0].hand.pop(i)
                    self.players[1].hand.append(card);
                    card.face_up = False
                    self.players[1].sort_and_position();
                    self.players[0].sort_and_position()
                    self.game_state, self.message = "discard_prikup", "СНЕСИТЕ 1 КАРТУ В СБРОС"
                    break
        elif self.game_state == "discard_prikup":
            for i, c in enumerate(self.players[0].hand):
                if abs(x - c.x) < 35 and abs(y - c.y) < 55:
                    trash = self.players[0].hand.pop(i)
                    self.unused_prikup.append(trash);
                    trash.move_to(-150, SCREEN_HEIGHT // 2)
                    self.players[0].sort_and_position()
                    self.game_state, self.message = "final_bet", f"ЗАКАЗ: {self.current_bid} (↑ поднять, Enter - ИГРАТЬ, S - РОСПИСЬ)"
                    break
        elif self.game_state == "playing" and self.turn_idx == 0:
            for i, c in enumerate(self.players[0].hand):
                if abs(x - c.x) < 35 and abs(y - c.y) < 55 and c.can_play:
                    self.play_card(self.players[0].hand.pop(i))
                    self.players[0].sort_and_position();
                    break

    def on_key_press(self, key, modifiers):
        if self.game_state == "bidding" and self.turn_idx == 0:
            if key == arcade.key.UP:
                if self.current_bid < 120 or self.players[0].has_any_marriage():
                    self.current_bid += 5;
                    self.turn_idx = 1
            elif key == arcade.key.P:
                self.take_prikup(1, random.randint(1, 2))
        elif self.game_state in ["final_bet", "playing"] and self.bid_winner_idx == 0:
            if key == arcade.key.S:
                self.apply_round_scores(painted=True)
                self.timer = 2.0;
                self.action_queue.append(self.setup_round)
            elif key == arcade.key.UP and self.game_state == "final_bet":
                if self.current_bid < self.players[0].get_max_possible():
                    self.current_bid += 5;
                    self.message = f"ЗАКАЗ: {self.current_bid} (Enter-ИГРАТЬ, S-РОСПИСЬ)"
            elif key == arcade.key.ENTER and self.game_state == "final_bet":
                self.game_state, self.turn_idx, self.message = "playing", 0, "ВАШ ХОД"

    def on_mouse_motion(self, x, y, dx, dy):
        for c in self.players[0].hand: c.is_hovered = (abs(x - c.x) < 35 and abs(y - c.y) < 55)


if __name__ == "__main__":
    ThousandGame()
    arcade.run()