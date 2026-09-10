"""Authoritative visible Sparta transaction ledger from Yahoo screenshots supplied Sept. 10, 2026.

Times are Yahoo display times (ET). FA=free agent before add; W=waivers after drop.
This file intentionally records only transactions visible in the supplied screenshots.
"""

SPARTA_TRANSACTIONS = [
    # (timestamp_et, team_code, action, added, dropped)
    ("2026-08-31 21:49", "JD", "DROP", None, "Devin Neal"),
    ("2026-09-01 20:00", "JD", "ADD", "Malik Davis", None),
    ("2026-09-01 21:10", "JU", "ADD_DROP", "James Conner", "Harrison Mevis"),
    ("2026-09-01 21:10", "JU", "ADD", "George Holani", None),
    ("2026-09-01 21:15", "MC", "ADD", "Jordan Love", None),
    ("2026-09-01 23:29", "SR", "ADD_DROP", "Baker Mayfield", "T.J. Hockenson"),
    ("2026-09-02 08:01", "JD", "ADD_DROP", "Devaughn Vele", "Pat Bryant"),
    ("2026-09-02 11:43", "SR", "ADD_DROP", "Jacob Saylors", "Hunter Henry"),
    ("2026-09-02 12:24", "VV", "ADD_DROP", "Najee Harris", "Jaydon Blue"),
    ("2026-09-04 03:16", "MC", "ADD_DROP", "Hunter Henry", "Jordan Love"),
    ("2026-09-04 09:59", "JD", "ADD_DROP", "Pat Bryant", "Jake Elliott"),
    ("2026-09-05 01:09", "JD", "ADD_DROP", "Evan McPherson", "Kendre Miller"),
    ("2026-09-06 03:17", "ANT", "ADD_DROP", "Jordan Love", "Braelon Allen"),
    ("2026-09-08 07:10", "JD", "ADD_DROP", "Caleb Douglas", "Pat Bryant"),
    ("2026-09-08 08:29", "JD", "ADD_DROP", "Jets D/ST", "Ravens D/ST"),
    ("2026-09-08 17:34", "JD", "ADD_DROP", "Malachi Fields", "Malik Willis"),
    ("2026-09-08 22:27", "JP", "ADD_DROP", "Kendre Miller", "Andres Borregales"),
    ("2026-09-09 18:32", "JD", "ADD_DROP", "Michael Mayer", "Dalton Schultz"),
    ("2026-09-09 20:49", "ME", "ADD", "Daniel Jones", None),
]

# Draft-night adds visible after the board capture. These may represent completion of auction rosters
# rather than post-draft waivers, so they are preserved separately and should not be double-counted
# against the 17-player auction board without reconciliation.
VISIBLE_DRAFT_NIGHT_ADDS = [
    ("2026-08-30 19:11", "TM", "Jaguars D/ST"),
    ("2026-08-30 19:11", "TM", "Michael Wilson"),
    ("2026-08-30 19:26", "VV", "D.J. Moore"),
]
