"""High-score storage: top-5 runs in ~/.depths_high.json."""
import json, time

from . import constants


def load_scores():
    try:
        with open(HIGH) as f:
            return json.load(f)
    except Exception:
        return []


def score_key(s):
    return (1 if s.get("victory") else 0, s.get("floor", 0), s.get("level", 0), s.get("gold", 0))


def record_score(game):
    """Record a finished run once; returns the current top-5."""
    if getattr(game, "_scored", False):
        return getattr(game, "_scores", load_scores())
    game._scored = True
    entry = {"floor": game.floor, "level": game.player["level"], "gold": game.player["gold"],
             "victory": bool(getattr(game, "victory", False)),
             "date": time.strftime("%Y-%m-%d %H:%M")}
    scores = load_scores()
    scores.append(entry)
    scores.sort(key=score_key, reverse=True)
    scores = scores[:5]
    try:
        json.dump(scores, open(constants.HIGH, "w"))
    except Exception:
        pass
    game._scores = scores
    return scores

