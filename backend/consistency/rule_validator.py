"""
Business Rule Manager & Custom Rule Evaluator
"""

from typing import List, Dict, Any
from database.connection import db_manager

class RuleValidator:
    @staticmethod
    def list_rules() -> List[Dict[str, Any]]:
        conn = db_manager.get_raw_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT rule_id, name, description, target_table, rule_definition, severity, enabled FROM business_rules")
        rows = cursor.fetchall()
        rules = []
        for r in rows:
            rules.append({
                "rule_id": r[0],
                "name": r[1],
                "description": r[2],
                "target_table": r[3],
                "rule_definition": r[4],
                "severity": r[5],
                "enabled": bool(r[6])
            })
        conn.close()
        return rules

    @staticmethod
    def add_rule(name: str, description: str, target_table: str, rule_definition: str, severity: str = "CRITICAL") -> Dict[str, Any]:
        import uuid
        rule_id = f"RULE-{uuid.uuid4().hex[:8].upper()}"
        conn = db_manager.get_raw_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO business_rules (rule_id, name, description, target_table, rule_definition, severity, enabled) "
            "VALUES (?, ?, ?, ?, ?, ?, 1)",
            (rule_id, name, description, target_table, rule_definition, severity)
        )
        conn.commit()
        conn.close()
        return {
            "rule_id": rule_id,
            "name": name,
            "description": description,
            "target_table": target_table,
            "rule_definition": rule_definition,
            "severity": severity,
            "enabled": True
        }
