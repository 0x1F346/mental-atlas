"""Alembic environment. Migrations run as the owner role, never the application role."""

from alembic import context
from sqlalchemy import create_engine

from atlas.db.models import Base
from atlas.settings import get_settings

target_metadata = Base.metadata


def run_migrations_online() -> None:
    url = (
        context.config.attributes.get("url") or get_settings().database_owner_url.get_secret_value()
    )
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations_online()
