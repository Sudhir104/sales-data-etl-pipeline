"""
Load layer. Uses SQLAlchemy so the same code loads into SQLite (zero-setup
demo/default) or MySQL/Postgres (production) just by changing DB_URL --
no pipeline code changes required.
"""
import logging

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

logger = logging.getLogger("etl.load")


def get_engine(db_url: str) -> Engine:
    return create_engine(db_url)


def load_table(df: pd.DataFrame, table_name: str, engine: Engine, if_exists: str = "replace") -> None:
    df.to_sql(table_name, con=engine, if_exists=if_exists, index=False)
    logger.info("Loaded %d rows into table `%s`", len(df), table_name)
