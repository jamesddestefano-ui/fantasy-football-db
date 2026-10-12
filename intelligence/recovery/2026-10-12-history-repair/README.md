# Non-authoritative Mongo Pulse recovery provenance

This dated record documents the 2026-10-12 history repair. Do not ingest this metadata as current Pulse data. The live history path remains `intelligence/grok_pulse_history.jsonl`.

Original bytes are preserved in the existing immutable Git commits and blobs linked by the manifest; no additional raw archive files are published here. The manifest maps every recovered record to its original commit, blob, line range and hashes. Recovery combines 13 earlier records, 10 later records and 7 current objects into 30 valid JSONL records without changing object values or reconstructing missing snapshot-only events. No duplicate IDs or conflicting objects were found.

This repair restores historical data and JSONL formatting. It does not change or identify the producer and does not prevent another writer from overwriting the history.
