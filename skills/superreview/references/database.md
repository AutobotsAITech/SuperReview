# Database and migrations

Trace read/check/write races to isolation guarantees and unique constraints. A row lock
cannot lock a row that does not exist. Check transaction retries and external effects that
cannot roll back. Analyze lock modes, table size, engine/version, index creation behavior,
backfill batching, and rolling-deploy compatibility. Do not claim every added default rewrites
a table; engine and version matter. Seek expand/contract or an explicit safe alternative.
Validate rollback/forward-fix strategy and application assumptions. Separate migrations only
when repository policy requires it; scope preference alone is not a defect.
