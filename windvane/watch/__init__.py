"""24h watch layer: poll watchlist quotes, detect anomalies, notify."""

from windvane.watch.notify import notify_macos
from windvane.watch.quotes import Quote, fetch_quote
from windvane.watch.rules import Alert, evaluate

__all__ = ["Alert", "Quote", "evaluate", "fetch_quote", "notify_macos"]
