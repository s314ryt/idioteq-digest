# IDIOTEQ Feed Digest

Co 30 minut sprawdza feedy i wysyla maila w stylu Feedly ze WSZYSTKIMI
nowymi wpisami (Feedly OPML + extra_feeds.txt); zero nowych wpisow = brak
maila. Dziala na GitHub Actions, niezaleznie od komputera. Nic nie gubi:
stan wyslanych ID w `seen.json`.

## Pliki
- `feeds.opml` — eksport z Feedly (zrodlo feedow)
- `extra_feeds.txt` — recznie dodane RSS (KATEGORIA | NAZWA | URL)
- `digest.py` — logika: pobierz -> wykryj nowe -> mail -> zapisz stan
- `.github/workflows/digest.yml` — tylko `workflow_dispatch`; wbudowany cron
  usuniety w `20bff0b` (kolidowal). Jedynym wyzwalaczem jest zewnetrzny
  pinger cron-job.org co 30 min (+ reczny Run workflow). Nazwa workflow
  "hourly digest" jest historyczna.
- `seen.json` — tworzony automatycznie po 1. runie

## Harmonogram i wykrywanie bledow (stan 2026-11-15)
- Rzeczywisty rytm: historia runow GitHub Actions z 2026-11-15 pokazuje
  `workflow_dispatch` o :00 i :30 kazdej godziny; ostatnie 300 runow:
  299 `success`, 1 `startup_failure`.
- Nieudany run jest widoczny jako czerwony w zakladce Actions (np. blad SMTP
  albo
  zapis `seen.json` nie przejdzie po 5 probach). Bledy pojedynczych feedow
  nie przerywaja runu — trafiaja tylko do stopki "Sanity check" w mailu.
- Brak runow (np. pinger cron-job.org przestanie dzialac) NIE jest niczym
  wykrywany: repo nie ma wlasnego crona ani kontroli "dead man". Brak maila
  nie jest sygnalem bledu, bo zero nowych wpisow tez oznacza brak maila.
- TO_VERIFY: czy ktokolwiek dostaje powiadomienia o nieudanych runach
  (ustawienia powiadomien GitHub) i o bledach wywolan po stronie cron-job.org.
- TO_VERIFY: czy maile digestu (nadawca = odbiorca = skrzynka redakcji)
  trafiaja pod etykiete Gmail DIGEST i mieszaja sie tam z inna poczta.
  Hipoteza z audytu 2026-08-31, niepotwierdzona; etykiet nie ustawia to repo.

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
