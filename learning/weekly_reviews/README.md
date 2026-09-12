# Mongo weekly learning reviews

Create one immutable review per completed NFL week, named `2026-week-NN.json`, using `TEMPLATE.json`.

Each review must include: best decisions; worst decisions; good process/bad result; bad process/good result; missed opportunities; signals that worked; signals that failed; data-quality issues; timing issues; rule changes proposed; rule changes adopted; and rules rejected for insufficient sample.

It must also include `NFL PULSE PERFORMANCE`: pulses considered, used and rejected; actions changed by Pulse; successful and unsuccessful changed actions; average information lead time; highly useful, misleading and late Pulse counts; and category/source performance. Repeated reports of one underlying NFL fact use one `pulse_information_event_id` and count as one information event.

Rule changes belong in a new version under `learning/rules/`; never rewrite an older rules file.
