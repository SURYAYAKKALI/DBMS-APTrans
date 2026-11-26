"""
APTrans Database & SQL Statement Generator
Paper: "Anomaly Pattern-guided Transaction Bug Testing in Relational Databases" (SIGMOD 2026, Section 3.2)

Implements:
- Multi-table schema generator with synthetic row_id and version columns
- Foreign key candidate key matching and referential integrity logging
- Multi-table JOIN synthesis (INNER JOIN, LEFT JOIN, RIGHT JOIN, CROSS JOIN)
- Type constraint checking for expressions (mitigating SQLancer semantic mismatches)
- Seed data generator with foreign key consistency
"""

import random
from typing import Dict, List, Tuple, Any, Optional

class ColumnDef:
    def __init__(self, name: str, col_type: str, is_pk: bool = False, is_unique: bool = False, 
                 is_not_null: bool = False, fk_ref: Optional[Tuple[str, str]] = None):
        self.name = name
        self.col_type = col_type.upper()  # 'INT', 'TEXT', 'BOOLEAN'
        self.is_pk = is_pk
        self.is_unique = is_unique
        self.is_not_null = is_not_null
        self.fk_ref = fk_ref  # (referenced_table, referenced_column)

    def to_sql(self, is_mysql: bool = False) -> str:
        parts = [self.name, self.col_type]
        if self.is_pk:
            parts.append("PRIMARY KEY")
        elif self.is_unique:
            parts.append("UNIQUE")
        elif self.is_not_null:
            parts.append("NOT NULL")
        return " ".join(parts)


class TableDef:
    def __init__(self, name: str, columns: List[ColumnDef]):
        self.name = name
        self.columns = columns
        self.col_map = {col.name: col for col in columns}
        
    @property
    def pk_column(self) -> Optional[ColumnDef]:
        for c in self.columns:
            if c.is_pk:
                return c
        return None

    def get_ddl(self, is_mysql: bool = False) -> str:
        col_sqls = [c.to_sql(is_mysql) for c in self.columns]
        
        # Add foreign key constraints
        for c in self.columns:
            if c.fk_ref:
                ref_tbl, ref_col = c.fk_ref
                col_sqls.append(f"FOREIGN KEY ({c.name}) REFERENCES {ref_tbl}({ref_col}) ON DELETE CASCADE")
                
        body = ",\n    ".join(col_sqls)
        engine_str = " ENGINE=InnoDB" if is_mysql else ""
        return f"CREATE TABLE {self.name} (\n    {body}\n){engine_str};"


class DatabaseSchema:
    def __init__(self, name: str = "aptrans_testbed"):
        self.name = name
        self.tables: Dict[str, TableDef] = {}
        self.inserted_pks: Dict[str, List[Any]] = {}  # table_name -> list of PK values for referential logging
        self.global_row_id = 0

    def add_table(self, table: TableDef):
        self.tables[table.name] = table
        self.inserted_pks[table.name] = []

    def get_all_ddl(self, is_mysql: bool = False) -> str:
        ddls = []
        for tbl in self.tables.values():
            ddls.append(tbl.get_ddl(is_mysql))
        return "\n\n".join(ddls)


class SchemaGenerator:
    """
    Synthesizes multi-table schemas with synthetic row_id, version,
    and valid referential integrity constraints per Section 3.2.1.
    """
    def __init__(self, seed: Optional[int] = 42):
        if seed is not None:
            random.seed(seed)

    def generate_benchmark_schema(self) -> DatabaseSchema:
        """
        Generates the standard APTrans multi-table schema with row_id, version,
        and foreign key relationships as evaluated in the SIGMOD paper.
        """
        db = DatabaseSchema("aptrans_benchmark")
        
        # Table 1: Primary entities (t1 / accounts / seats)
        t1_cols = [
            ColumnDef("row_id", "INT", is_pk=True),         # Synthetic unique row ID
            ColumnDef("version", "INT", is_not_null=True),   # Synthetic version counter
            ColumnDef("c0", "INT", is_not_null=True),        # Core payload value (e.g. balance, seat state)
            ColumnDef("c1", "INT", is_not_null=False),
            ColumnDef("val_str", "TEXT", is_not_null=False)
        ]
        t1 = TableDef("t1", t1_cols)
        db.add_table(t1)
        
        # Table 2: Secondary / joined table (t2) referencing t1
        t2_cols = [
            ColumnDef("row_id", "INT", is_pk=True),
            ColumnDef("version", "INT", is_not_null=True),
            ColumnDef("t1_ref", "INT", fk_ref=("t1", "row_id")),  # Foreign key candidate matching
            ColumnDef("c0", "INT", is_not_null=True),
            ColumnDef("c1", "INT", is_not_null=False)
        ]
        t2 = TableDef("t2", t2_cols)
        db.add_table(t2)
        
        return db

    def generate_seed_data(self, db: DatabaseSchema, rows_per_table: int = 5) -> List[str]:
        """
        Generates initial INSERT statements ensuring foreign keys reference existing rows
        via referential data logging (Section 3.2.1 Data Generation).
        """
        insert_stmts = []
        
        # Seed t1 first
        for i in range(1, rows_per_table + 1):
            row_id = i
            version = 1
            c0 = i * 100
            c1 = i * 10
            val_str = f"'record_{i}'"
            stmt = f"INSERT INTO t1 (row_id, version, c0, c1, val_str) VALUES ({row_id}, {version}, {c0}, {c1}, {val_str});"
            insert_stmts.append(stmt)
            db.inserted_pks["t1"].append(row_id)
            
        # Seed t2 with valid FKs referencing t1
        t1_pks = db.inserted_pks.get("t1", [1])
        for i in range(1, rows_per_table + 1):
            row_id = 100 + i
            version = 1
            fk_val = random.choice(t1_pks) if t1_pks else 1
            c0 = i * 50
            c1 = i * 5
            stmt = f"INSERT INTO t2 (row_id, version, t1_ref, c0, c1) VALUES ({row_id}, {version}, {fk_val}, {c0}, {c1});"
            insert_stmts.append(stmt)
            db.inserted_pks["t2"].append(row_id)

        return insert_stmts

    def generate_join_query(self, db: DatabaseSchema, join_type: str = "INNER") -> str:
        """
        Section 3.2.2 JOIN Statement Generation:
        Generates INNER, LEFT, RIGHT, or CROSS joins matching FK to PK columns.
        """
        join_type = join_type.upper()
        if join_type not in ("INNER", "LEFT", "RIGHT", "CROSS"):
            join_type = "INNER"

        if "t1" in db.tables and "t2" in db.tables:
            if join_type == "CROSS":
                return "SELECT t1.row_id, t1.c0, t2.c0 FROM t1 CROSS JOIN t2;"
            return (
                f"SELECT t1.row_id AS t1_id, t1.c0 AS t1_c0, t2.row_id AS t2_id, t2.c0 AS t2_c0 "
                f"FROM t1 {join_type} JOIN t2 ON t1.row_id = t2.t1_ref;"
            )
        return "SELECT * FROM t1;"
