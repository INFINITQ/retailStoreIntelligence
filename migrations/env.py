# You are writing the Alembic migration environment file for a retail store CCTV analytics API.

# FILE: migrations/env.py
# PURPOSE: Standard Alembic env.py customised to: (1) read DATABASE_URL_SYNC from environment
# instead of alembic.ini, (2) import all ORM models so autogenerate can detect them,
# (3) support both offline and online migration modes.

# TECH: Python 3.11, alembic==1.14.0, sqlalchemy, psycopg2-binary

# IMPLEMENT:

# Standard Alembic env.py pattern with these customisations:

# 1. Import load_dotenv and call load_dotenv() at top to load .env file.

# 2. Import all ORM models to register them with Base.metadata:
#    from app.models.db_models import Event, VisitorSession, POSTransaction, AnomalyLog

# 3. Import Base from app.database: from app.database import Base

# 4. Override sqlalchemy.url from environment:
#    ```python
#    import os
#    from dotenv import load_dotenv
#    load_dotenv()
#    db_url = os.getenv("DATABASE_URL_SYNC",
#                        "postgresql+psycopg2://store_user:store_pass@localhost/store_intelligence")
#    config.set_main_option("sqlalchemy.url", db_url)
#    ```

# 5. Set `target_metadata = Base.metadata` (required for autogenerate).

# 6. Implement `run_migrations_offline()` — standard Alembic pattern.

# 7. Implement `run_migrations_online()` — standard Alembic pattern with connectable from engine.

# The rest is standard Alembic boilerplate. Do not deviate from Alembic 1.14 API.

# IMPORTS NEEDED: alembic (context), alembic.config (Config), logging, os,
# sqlalchemy (engine_from_config, pool), python-dotenv (load_dotenv),
# app.database (Base), app.models.db_models (all models)
