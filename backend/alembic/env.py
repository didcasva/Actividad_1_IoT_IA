from alembic import context
from app.core.database import Base, engine
from app.models import entities

with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
