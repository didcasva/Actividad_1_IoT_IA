"""Configure the academic demo unit for the user's physical DHT11."""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("UPDATE devices SET sensor_type='DHT11' WHERE device_code='esp32-01'"))


def downgrade():
    op.execute(sa.text("UPDATE devices SET sensor_type='DHT22' WHERE device_code='esp32-01'"))
