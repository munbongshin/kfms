"""
SQL Validator for Read-Only Mode.
Validates SQL queries to ensure they are safe for execution.
"""
from typing import Dict, List, Any
import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import Keyword, DML


class SQLValidator:
    """
    Validates SQL queries for safety and read-only compliance.
    """

    # Allowed statement types (read-only operations)
    ALLOWED_TYPES = {'SELECT', 'WITH', 'EXPLAIN'}

    # Dangerous keywords that indicate write operations
    DANGEROUS_KEYWORDS = {
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'TRUNCATE', 'ALTER',
        'CREATE', 'REPLACE', 'MERGE', 'GRANT', 'REVOKE',
        'CALL', 'EXEC', 'EXECUTE', 'COPY'
    }

    # Suspicious patterns (potential for data modification)
    SUSPICIOUS_PATTERNS = {
        'INTO': 'May indicate INSERT INTO',
        'SET': 'May indicate UPDATE SET',
        'FROM ONLY': 'May indicate DELETE FROM',
    }

    @staticmethod
    def validate(sql: str) -> Dict[str, Any]:
        """
        Validate SQL query for read-only compliance.

        Args:
            sql: SQL query string

        Returns:
            Dict with validation results:
            {
                "is_safe": bool,
                "is_read_only": bool,
                "warnings": List[str],
                "sql_type": str,
                "cleaned_sql": str
            }
        """
        if not sql or not sql.strip():
            return {
                "is_safe": False,
                "is_read_only": False,
                "warnings": ["Empty SQL query"],
                "sql_type": None,
                "cleaned_sql": ""
            }

        # Clean and normalize SQL
        cleaned_sql = sql.strip()

        # Parse SQL
        try:
            parsed = sqlparse.parse(cleaned_sql)
            if not parsed:
                return {
                    "is_safe": False,
                    "is_read_only": False,
                    "warnings": ["Failed to parse SQL"],
                    "sql_type": None,
                    "cleaned_sql": cleaned_sql
                }

            statement = parsed[0]
        except Exception as e:
            return {
                "is_safe": False,
                "is_read_only": False,
                "warnings": [f"Parse error: {str(e)}"],
                "sql_type": None,
                "cleaned_sql": cleaned_sql
            }

        # Get statement type
        stmt_type = SQLValidator._get_statement_type(statement)

        # Collect warnings
        warnings = []

        # Check if statement type is allowed
        if stmt_type not in SQLValidator.ALLOWED_TYPES:
            warnings.append(f"Operation '{stmt_type}' is blocked in read-only mode")
            return {
                "is_safe": False,
                "is_read_only": False,
                "warnings": warnings,
                "sql_type": stmt_type,
                "cleaned_sql": cleaned_sql
            }

        # Check for dangerous keywords in SQL text
        sql_upper = cleaned_sql.upper()
        for keyword in SQLValidator.DANGEROUS_KEYWORDS:
            if keyword in sql_upper:
                # Check if it's actually a keyword (not part of string or identifier)
                if SQLValidator._is_dangerous_keyword_usage(cleaned_sql, keyword):
                    warnings.append(f"Dangerous keyword '{keyword}' detected - blocked")
                    return {
                        "is_safe": False,
                        "is_read_only": False,
                        "warnings": warnings,
                        "sql_type": stmt_type,
                        "cleaned_sql": cleaned_sql
                    }

        # Check for suspicious patterns
        for pattern, description in SQLValidator.SUSPICIOUS_PATTERNS.items():
            if pattern in sql_upper:
                warnings.append(f"Suspicious pattern detected: {description}")

        # Add LIMIT if not present (safety measure)
        if 'LIMIT' not in sql_upper:
            warnings.append("No LIMIT clause found - will enforce LIMIT 1000")

        # Query is safe
        is_safe = len([w for w in warnings if 'blocked' in w.lower()]) == 0

        return {
            "is_safe": is_safe,
            "is_read_only": True,
            "warnings": warnings,
            "sql_type": stmt_type,
            "cleaned_sql": cleaned_sql
        }

    @staticmethod
    def _get_statement_type(statement: Statement) -> str:
        """
        Extract statement type from parsed SQL.

        Args:
            statement: Parsed SQL statement

        Returns:
            Statement type (e.g., 'SELECT', 'INSERT', etc.)
        """
        # Get first meaningful token
        for token in statement.tokens:
            if token.ttype in (Keyword.DML, Keyword.DDL, Keyword.CTE):
                return token.value.upper()
            elif token.ttype is Keyword and token.value.upper() in {'SELECT', 'WITH', 'EXPLAIN'}:
                return token.value.upper()

        return 'UNKNOWN'

    @staticmethod
    def _is_dangerous_keyword_usage(sql: str, keyword: str) -> bool:
        """
        Check if keyword is used in a dangerous context (not in string/comment).

        Args:
            sql: SQL string
            keyword: Keyword to check

        Returns:
            True if keyword is used dangerously
        """
        # Simple heuristic: check if keyword appears outside of quotes
        # This is not perfect but catches most cases

        sql_upper = sql.upper()

        # Remove string literals (simple approach)
        in_single_quote = False
        in_double_quote = False
        cleaned = []

        for char in sql:
            if char == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
            elif char == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
            elif not in_single_quote and not in_double_quote:
                cleaned.append(char)
            else:
                cleaned.append(' ')  # Replace string content with space

        cleaned_sql = ''.join(cleaned).upper()

        return keyword in cleaned_sql

    @staticmethod
    def enforce_limit(sql: str, default_limit: int = 1000) -> str:
        """
        Add LIMIT clause if not present.

        Args:
            sql: SQL query
            default_limit: Default row limit

        Returns:
            SQL with LIMIT clause
        """
        sql_upper = sql.upper()

        if 'LIMIT' in sql_upper:
            return sql

        # Add LIMIT before ORDER BY if present, otherwise at end
        if 'ORDER BY' in sql_upper:
            # Insert LIMIT before ORDER BY
            parts = sql.split('ORDER BY')
            return f"{parts[0].rstrip()} LIMIT {default_limit} ORDER BY {'ORDER BY'.join(parts[1:])}"
        else:
            # Add LIMIT at end
            return f"{sql.rstrip()} LIMIT {default_limit}"


# Convenience function
def validate_sql(sql: str) -> Dict[str, Any]:
    """
    Validate SQL query for read-only mode.

    Args:
        sql: SQL query string

    Returns:
        Validation results
    """
    return SQLValidator.validate(sql)
