# Workflows

Completed add/drop: back up for risky/bulk work; resolve league and team; verify the dropped player is owned; reject an add confirmed owned elsewhere unless trade/correction; append a transaction group, ownership events, and FAAB debit in one database transaction; rebuild; validate; commit. A drop resolves to `UNKNOWN`, not confirmed free agency.

Proposed pickup: query current league ownership. Recommend action only when availability is confirmed; otherwise request league evidence.

