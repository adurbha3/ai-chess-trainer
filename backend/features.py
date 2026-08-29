"""
Extracts structural and relational chess features from a board position.

Two layers:
  PositionFeatures  — scalar counts (global structure)
  RelationalSignals — specific spatial relationships between named pieces
"""
import chess
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Scalar features (global counts)
# ---------------------------------------------------------------------------

@dataclass
class PositionFeatures:
    isolated_pawns: int
    doubled_pawns: int
    backward_pawns: int
    passed_pawns: int
    pawn_islands: int
    pawn_mobility: int
    knight_on_rim: int
    knight_mobility_avg: float
    bishop_mobility_avg: float
    rooks_on_open_files: int
    rooks_on_semiopen_files: int
    king_pawn_shield: int
    king_open_files: int
    total_mobility: int
    hanging_pieces: int


# ---------------------------------------------------------------------------
# Relational signals — each is a human-readable string describing a
# specific spatial relationship that is bad for the moving side.
# ---------------------------------------------------------------------------

@dataclass
class RelationalSignals:
    signals: list[str] = field(default_factory=list)

    def add(self, s: str):
        self.signals.append(s)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pawn_files(board: chess.Board, color: chess.Color) -> list[int]:
    return [chess.square_file(sq) for sq in board.pieces(chess.PAWN, color)]


def _square_name(sq: int) -> str:
    return chess.square_name(sq)


def _piece_name(board: chess.Board, sq: int) -> str:
    p = board.piece_at(sq)
    if p is None:
        return "piece"
    symbols = {chess.KNIGHT: "N", chess.BISHOP: "B", chess.ROOK: "R", chess.QUEEN: "Q", chess.KING: "K", chess.PAWN: ""}
    return symbols.get(p.piece_type, "?") + _square_name(sq)


def _isolated_pawn_squares(board: chess.Board, color: chess.Color) -> list[int]:
    pawns = list(board.pieces(chess.PAWN, color))
    files = [chess.square_file(sq) for sq in pawns]
    result = []
    for sq in pawns:
        f = chess.square_file(sq)
        adj = [f - 1, f + 1]
        if not any(af in files for af in adj if 0 <= af <= 7):
            result.append(sq)
    return result


def _passed_pawn_squares(board: chess.Board, color: chess.Color) -> list[int]:
    pawns = list(board.pieces(chess.PAWN, color))
    enemy_pawns = list(board.pieces(chess.PAWN, not color))
    result = []
    for sq in pawns:
        f = chess.square_file(sq)
        r = chess.square_rank(sq)
        is_passed = True
        for esq in enemy_pawns:
            ef = chess.square_file(esq)
            er = chess.square_rank(esq)
            if abs(ef - f) <= 1:
                if color == chess.WHITE and er > r:
                    is_passed = False; break
                if color == chess.BLACK and er < r:
                    is_passed = False; break
        if is_passed:
            result.append(sq)
    return result


def _square_in_front(sq: int, color: chess.Color) -> int | None:
    r = chess.square_rank(sq)
    f = chess.square_file(sq)
    nr = r + (1 if color == chess.WHITE else -1)
    if 0 <= nr <= 7:
        return chess.square(f, nr)
    return None


# ---------------------------------------------------------------------------
# Relational signal extraction
# ---------------------------------------------------------------------------

def extract_relational(board: chess.Board, color: chess.Color) -> RelationalSignals:
    signals = RelationalSignals()
    pawns = list(board.pieces(chess.PAWN, color))

    # 1. Piece blocking an isolated pawn (especially knight/bishop on the square ahead)
    for iso_sq in _isolated_pawn_squares(board, color):
        front = _square_in_front(iso_sq, color)
        if front is not None:
            blocker = board.piece_at(front)
            if blocker is not None and blocker.color == color and blocker.piece_type != chess.PAWN:
                signals.add(
                    f"{_piece_name(board, front)} is blocking your isolated pawn on {_square_name(iso_sq)} — "
                    f"the pawn cannot advance and the piece restricts its own activity"
                )

    # 2. Piece blocking a passed pawn
    for pp_sq in _passed_pawn_squares(board, color):
        front = _square_in_front(pp_sq, color)
        if front is not None:
            blocker = board.piece_at(front)
            if blocker is not None and blocker.color == color and blocker.piece_type != chess.PAWN:
                signals.add(
                    f"{_piece_name(board, front)} is blocking your passed pawn on {_square_name(pp_sq)} — "
                    f"passed pawns should be pushed or cleared"
                )

    # 3. Bad bishop (bishop on same color as majority of own pawns)
    for bishop_sq in board.pieces(chess.BISHOP, color):
        is_light = (chess.square_rank(bishop_sq) + chess.square_file(bishop_sq)) % 2 == 1
        same_color_pawns = sum(
            1 for p in pawns
            if ((chess.square_rank(p) + chess.square_file(p)) % 2 == 1) == is_light
        )
        total_pawns = len(pawns)
        if total_pawns >= 3 and same_color_pawns / total_pawns >= 0.6:
            color_label = "light" if is_light else "dark"
            signals.add(
                f"Your {_piece_name(board, bishop_sq)} is a 'bad bishop' — {same_color_pawns}/{total_pawns} "
                f"of your pawns are on {color_label} squares, blocking its diagonals"
            )

    # 4. Bishop diagonals blocked by own pawns
    for bishop_sq in board.pieces(chess.BISHOP, color):
        blocked = 0
        for direction in [7, 9, -7, -9]:
            sq = bishop_sq + direction
            if 0 <= sq < 64:
                p = board.piece_at(sq)
                if p is not None and p.color == color and p.piece_type == chess.PAWN:
                    blocked += 1
        if blocked >= 2:
            signals.add(
                f"{_piece_name(board, bishop_sq)} has {blocked} diagonal squares immediately blocked by own pawns"
            )

    # 5. Knight on the rim with no outpost compensation
    rim_files = {0, 7}
    rim_ranks = {0, 7}
    for knight_sq in board.pieces(chess.KNIGHT, color):
        f, r = chess.square_file(knight_sq), chess.square_rank(knight_sq)
        if f in rim_files or r in rim_ranks:
            mobility = len(list(board.attacks(knight_sq)))
            signals.add(
                f"{_piece_name(board, knight_sq)} is on the rim with only {mobility} available squares "
                f"— knights on the edge are worth ~1.5 pawns less than centralised knights"
            )

    # 6. Pinned piece (non-king piece that can't move without exposing the king)
    king_sq = board.king(color)
    if king_sq is not None:
        for piece_sq in (
            list(board.pieces(chess.KNIGHT, color)) +
            list(board.pieces(chess.BISHOP, color)) +
            list(board.pieces(chess.ROOK, color)) +
            list(board.pieces(chess.QUEEN, color))
        ):
            if board.is_pinned(color, piece_sq):
                # Find the attacker
                attacker_sq = None
                for att_sq in board.attackers(not color, king_sq):
                    att = board.piece_at(att_sq)
                    if att and att.piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN):
                        # Check if piece_sq is between att_sq and king_sq
                        if chess.square_file(att_sq) == chess.square_file(piece_sq) == chess.square_file(king_sq):
                            attacker_sq = att_sq; break
                        if chess.square_rank(att_sq) == chess.square_rank(piece_sq) == chess.square_rank(king_sq):
                            attacker_sq = att_sq; break
                        # Diagonal
                        if (abs(chess.square_file(att_sq) - chess.square_file(king_sq)) ==
                                abs(chess.square_rank(att_sq) - chess.square_rank(king_sq))):
                            attacker_sq = att_sq; break
                attacker_name = _piece_name(board, attacker_sq) if attacker_sq else "enemy piece"
                signals.add(
                    f"{_piece_name(board, piece_sq)} is pinned against your king by {attacker_name} "
                    f"and cannot move freely"
                )

    # 7. Overloaded defender: a piece defending two or more attacked enemy-targeted pieces
    attacked_friendly = [
        sq for sq in (
            list(board.pieces(chess.KNIGHT, color)) +
            list(board.pieces(chess.BISHOP, color)) +
            list(board.pieces(chess.ROOK, color)) +
            list(board.pieces(chess.QUEEN, color))
        )
        if board.is_attacked_by(not color, sq)
    ]
    # For each defender, count how many of the attacked pieces it defends
    defender_load: dict[int, list[int]] = {}
    for att_sq in attacked_friendly:
        for def_sq in board.attackers(color, att_sq):
            if board.piece_at(def_sq) and board.piece_at(def_sq).piece_type != chess.KING:
                defender_load.setdefault(def_sq, []).append(att_sq)
    for def_sq, targets in defender_load.items():
        if len(targets) >= 2:
            target_names = " and ".join(_piece_name(board, t) for t in targets[:2])
            signals.add(
                f"{_piece_name(board, def_sq)} is overloaded — it is the only defender of both {target_names}"
            )

    # 8. Rook trapped behind own pawns (rook on back rank with pawns blocking every exit file)
    for rook_sq in board.pieces(chess.ROOK, color):
        r = chess.square_rank(rook_sq)
        back_rank = 0 if color == chess.WHITE else 7
        if r == back_rank:
            f = chess.square_file(rook_sq)
            # Check if pawns block the file and adjacent files
            blocked_files = 0
            for cf in range(max(0, f - 1), min(8, f + 2)):
                if any(chess.square_file(p) == cf for p in pawns):
                    blocked_files += 1
            if blocked_files == 3:
                signals.add(
                    f"{_piece_name(board, rook_sq)} is trapped on the back rank — "
                    f"own pawns on adjacent files prevent activation"
                )

    # 9. King exposed: castled king with pawn shield broken
    if king_sq is not None:
        kf, kr = chess.square_file(king_sq), chess.square_rank(king_sq)
        back = 0 if color == chess.WHITE else 7
        is_castled = (kf in (6, 2) and kr == back)
        if is_castled:
            shield_missing = []
            direction = 1 if color == chess.WHITE else -1
            for sf in range(max(0, kf - 1), min(8, kf + 2)):
                sq1 = chess.square(sf, kr + direction)
                sq2 = chess.square(sf, kr + 2 * direction) if 0 <= kr + 2 * direction <= 7 else None
                has_pawn = (
                    (board.piece_at(sq1) == chess.Piece(chess.PAWN, color)) or
                    (sq2 and board.piece_at(sq2) == chess.Piece(chess.PAWN, color))
                )
                if not has_pawn:
                    shield_missing.append(chess.FILE_NAMES[sf])
            if len(shield_missing) >= 2:
                signals.add(
                    f"Your castled king has no pawn cover on the {'- and '.join(shield_missing)}-file(s) — "
                    f"the position is open toward your king"
                )

    return signals


# ---------------------------------------------------------------------------
# Scalar feature extraction (unchanged from original)
# ---------------------------------------------------------------------------

def extract(board: chess.Board, color: chess.Color) -> PositionFeatures:
    pawns = board.pieces(chess.PAWN, color)
    enemy_pawns = board.pieces(chess.PAWN, not color)
    pawn_files = [chess.square_file(sq) for sq in pawns]

    isolated = len(_isolated_pawn_squares(board, color))

    doubled = 0
    for f in range(8):
        count = pawn_files.count(f)
        if count > 1:
            doubled += count - 1

    backward = 0
    for sq in pawns:
        f = chess.square_file(sq)
        r = chess.square_rank(sq)
        direction = 1 if color == chess.WHITE else -1
        front_sq = chess.square(f, r + direction) if 0 <= r + direction <= 7 else None
        if front_sq is not None and board.is_attacked_by(not color, front_sq):
            supported = any(
                chess.square_file(s) in (f - 1, f + 1) and
                (chess.square_rank(s) < r if color == chess.WHITE else chess.square_rank(s) > r)
                for s in pawns
            )
            if not supported:
                backward += 1

    passed = len(_passed_pawn_squares(board, color))

    occupied_files = sorted(set(pawn_files))
    islands = 0
    if occupied_files:
        islands = 1
        for i in range(1, len(occupied_files)):
            if occupied_files[i] != occupied_files[i - 1] + 1:
                islands += 1

    pawn_mob = 0
    for sq in pawns:
        f, r = chess.square_file(sq), chess.square_rank(sq)
        direction = 1 if color == chess.WHITE else -1
        nr = r + direction
        if 0 <= nr <= 7 and board.piece_at(chess.square(f, nr)) is None:
            pawn_mob += 1

    knights = board.pieces(chess.KNIGHT, color)
    rim_files = {0, 7}
    rim_ranks = {0, 7}
    knight_rim = sum(
        1 for sq in knights
        if chess.square_file(sq) in rim_files or chess.square_rank(sq) in rim_ranks
    )

    knight_mobs = [len(list(board.attacks(sq))) for sq in knights]
    bishop_mobs = [len(list(board.attacks(sq))) for sq in board.pieces(chess.BISHOP, color)]
    knight_mob_avg = sum(knight_mobs) / len(knight_mobs) if knight_mobs else 0.0
    bishop_mob_avg = sum(bishop_mobs) / len(bishop_mobs) if bishop_mobs else 0.0

    open_files = 0
    semi_open_files = 0
    for sq in board.pieces(chess.ROOK, color):
        f = chess.square_file(sq)
        own_on_file = any(chess.square_file(p) == f for p in pawns)
        enemy_on_file = any(chess.square_file(p) == f for p in enemy_pawns)
        if not own_on_file and not enemy_on_file:
            open_files += 1
        elif not own_on_file:
            semi_open_files += 1

    king_sq = board.king(color)
    shield = 0
    king_open = 0
    if king_sq is not None:
        kf, kr = chess.square_file(king_sq), chess.square_rank(king_sq)
        direction = 1 if color == chess.WHITE else -1
        for sf in range(max(0, kf - 1), min(8, kf + 2)):
            for sr in [kr + direction, kr + 2 * direction]:
                if 0 <= sr <= 7:
                    if board.piece_at(chess.square(sf, sr)) == chess.Piece(chess.PAWN, color):
                        shield += 1
        for sf in range(max(0, kf - 1), min(8, kf + 2)):
            if (not any(chess.square_file(p) == sf for p in pawns) and
                    not any(chess.square_file(p) == sf for p in enemy_pawns)):
                king_open += 1

    all_pieces = (
        list(board.pieces(chess.KNIGHT, color)) +
        list(board.pieces(chess.BISHOP, color)) +
        list(board.pieces(chess.ROOK, color)) +
        list(board.pieces(chess.QUEEN, color))
    )
    total_mob = sum(len(list(board.attacks(sq))) for sq in all_pieces)
    hanging = sum(
        1 for sq in all_pieces
        if board.is_attacked_by(not color, sq) and not board.is_attacked_by(color, sq)
    )

    return PositionFeatures(
        isolated_pawns=isolated,
        doubled_pawns=doubled,
        backward_pawns=backward,
        passed_pawns=passed,
        pawn_islands=islands,
        pawn_mobility=pawn_mob,
        knight_on_rim=knight_rim,
        knight_mobility_avg=knight_mob_avg,
        bishop_mobility_avg=bishop_mob_avg,
        rooks_on_open_files=open_files,
        rooks_on_semiopen_files=semi_open_files,
        king_pawn_shield=shield,
        king_open_files=king_open,
        total_mobility=total_mob,
        hanging_pieces=hanging,
    )


def feature_delta(before: PositionFeatures, after: PositionFeatures) -> dict:
    return {
        "isolated_pawns":      after.isolated_pawns - before.isolated_pawns,
        "doubled_pawns":       after.doubled_pawns - before.doubled_pawns,
        "backward_pawns":      after.backward_pawns - before.backward_pawns,
        "passed_pawns":        after.passed_pawns - before.passed_pawns,
        "pawn_islands":        after.pawn_islands - before.pawn_islands,
        "pawn_mobility":       after.pawn_mobility - before.pawn_mobility,
        "knight_on_rim":       after.knight_on_rim - before.knight_on_rim,
        "knight_mobility_avg": after.knight_mobility_avg - before.knight_mobility_avg,
        "bishop_mobility_avg": after.bishop_mobility_avg - before.bishop_mobility_avg,
        "rooks_on_open_files": after.rooks_on_open_files - before.rooks_on_open_files,
        "king_pawn_shield":    after.king_pawn_shield - before.king_pawn_shield,
        "king_open_files":     after.king_open_files - before.king_open_files,
        "total_mobility":      after.total_mobility - before.total_mobility,
        "hanging_pieces":      after.hanging_pieces - before.hanging_pieces,
    }


def features_to_dict(f: PositionFeatures) -> dict:
    return {
        "isolated_pawns": f.isolated_pawns,
        "doubled_pawns": f.doubled_pawns,
        "backward_pawns": f.backward_pawns,
        "passed_pawns": f.passed_pawns,
        "pawn_islands": f.pawn_islands,
        "pawn_mobility": f.pawn_mobility,
        "knight_on_rim": f.knight_on_rim,
        "knight_mobility_avg": round(f.knight_mobility_avg, 1),
        "bishop_mobility_avg": round(f.bishop_mobility_avg, 1),
        "rooks_on_open_files": f.rooks_on_open_files,
        "rooks_on_semiopen_files": f.rooks_on_semiopen_files,
        "king_pawn_shield": f.king_pawn_shield,
        "king_open_files": f.king_open_files,
        "total_mobility": f.total_mobility,
        "hanging_pieces": f.hanging_pieces,
    }
