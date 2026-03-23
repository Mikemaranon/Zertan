# db_methods/t_site_features.py


class SiteFeaturesTable:
    def __init__(self, db):
        self.db = db

    def list_all(self):
        _, rows = self.db.execute(
            """
            SELECT feature_key, label, description, enabled, updated_at
            FROM site_features
            ORDER BY lower(label), feature_key
            """,
            fetchall=True,
        )
        return [self._row_to_feature(row) for row in rows]

    def get(self, feature_key):
        _, row = self.db.execute(
            """
            SELECT feature_key, label, description, enabled, updated_at
            FROM site_features
            WHERE feature_key = ?
            """,
            (feature_key,),
            fetchone=True,
        )
        return self._row_to_feature(row)

    def set_enabled(self, feature_key, enabled):
        self.db.execute(
            """
            UPDATE site_features
            SET enabled = ?, updated_at = CURRENT_TIMESTAMP
            WHERE feature_key = ?
            """,
            (1 if enabled else 0, feature_key),
        )
        return self.get(feature_key)

    def enabled_map(self):
        return {feature["feature_key"]: feature["enabled"] for feature in self.list_all()}

    def _row_to_feature(self, row):
        if not row:
            return None
        return {
            "feature_key": row["feature_key"],
            "label": row["label"],
            "description": row["description"] or "",
            "enabled": bool(row["enabled"]),
            "updated_at": row["updated_at"],
        }
