# IDIOTEQ Feed Digest

Co godzine wysyla maila w stylu Feedly ze WSZYSTKIMI nowymi wpisami
z feedow (Feedly OPML + extra_feeds.txt). Dziala na GitHub Actions,
niezaleznie od komputera. Nic nie gubi: stan wyslanych ID w `seen.json`.

## Pliki
- `feeds.opml` — eksport z Feedly (zrodlo feedow)
- `extra_feeds.txt` — recznie dodane RSS (KATEGORIA | NAZWA | URL)
- `digest.py` — logika: pobierz -> wykryj nowe -> mail -> zapisz stan
- `.github/workflows/digest.yml` — cron co godzine
- `seen.json` — tworzony automatycznie po 1. runie

## Sekrety (Settings -> Secrets and variables -> Actions)
- `MAIL_USER` = www.idioteq.com@gmail.com
- `MAIL_PASS` = App Password Gmaila (16 znakow, bez spacji)
- `MAIL_TO`   = www.idioteq.com@gmail.com

## Pierwszy run
Seeduje stan (oznacza obecne wpisy jako widziane) i NIE wysyla maila.
Kolejne runy wysylaja tylko nowe. Reczny test: zakladka Actions -> Run workflow.

## Dodanie nowego RSS
Dopisz linie do `extra_feeds.txt`. Dla kanalu YouTube RSS to:
`https://www.youtube.com/feeds/videos.xml?channel_id=UCxxxx`
