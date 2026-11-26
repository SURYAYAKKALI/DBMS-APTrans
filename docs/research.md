# TransactionGuard Research Foundation & Theoretical Background

## 1. Context & Theoretical Critique

In 1992, ANSI SQL-92 defined four isolation levels based on three phenomena:
1. Dirty Read ($P_1$)
2. Non-Repeatable Read ($P_2$)
3. Phantom Read ($P_3$)

In 1995, Berenson et al. ("A Critique of ANSI SQL Isolation Levels") demonstrated that ANSI SQL definitions were ambiguous and incomplete, failing to specify critical anomalies including:
- **Lost Update ($P_4$)**: Two transactions concurrently read $X$ and both update $X$, one overwriting the other.
- **Write Skew ($A5B$)**: Transactions read overlapping data sets but write disjoint records, breaking global invariants (e.g. Doctor-on-Duty).
- **Read Skew ($A5A$)**: Non-repeatable read across disparate relations violating multi-record consistency.

## 2. Adya's Dependency Model (1999)

Atul Adya established formal graph-theoretic criteria for isolation levels based on directed serialization graphs:
- **$ww$-dependency**: $T_1$ writes version $x_i$, $T_2$ creates subsequent version $x_j$.
- **$wr$-dependency**: $T_1$ writes version $x_i$, $T_2$ reads version $x_i$.
- **$rw$-dependency (Anti-dependency)**: $T_1$ reads version $x_i$, $T_2$ writes subsequent version $x_j > x_i$.

In Serializable Snapshot Isolation (SSI, Cahill et al. 2008 / PostgreSQL 9.1+), any cycle containing two consecutive $rw$-edges indicates a non-serializable execution and causes transaction abortion with SQLSTATE 40001.

## 3. Comparison with APTrans (SIGMOD 2026)

APTrans demonstrated automated bug detection in database kernels (MySQL, MariaDB, OceanBase) via anomaly pattern synthesis.
**TransactionGuard** elevates this theoretical insight into a full developer-facing assurance platform:
- Integrates real-world application business invariants (Inventory and Reservations).
- Differentiates engine bugs, permitted weak isolation behavior, and application-level design flaws.
- Provides interactive visual dependency graphs and actionable SQL code remediations.
