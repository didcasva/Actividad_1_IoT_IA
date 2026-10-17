"""Initial schema and mobile health unit demo device."""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("devices", sa.Column("id", sa.Integer, primary_key=True), sa.Column("device_code", sa.String(80), unique=True, nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("sensor_type", sa.String(10), nullable=False), sa.Column("location", sa.String(200), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("is_active", sa.Boolean, nullable=False), sa.CheckConstraint("sensor_type IN ('DHT11','DHT22')"))
    op.create_table("sensor_readings", sa.Column("id", sa.Integer, primary_key=True), sa.Column("device_id", sa.Integer, sa.ForeignKey("devices.id"), nullable=False), sa.Column("temperature_c", sa.Float, nullable=False), sa.Column("humidity_percent", sa.Float, nullable=False), sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False), sa.Column("received_at", sa.DateTime(timezone=True), nullable=False), sa.Column("boot_id", sa.String(80), nullable=False), sa.Column("sequence_number", sa.Integer, nullable=False), sa.UniqueConstraint("device_id", "boot_id", "sequence_number"), sa.CheckConstraint("humidity_percent BETWEEN 0 AND 100"), sa.CheckConstraint("temperature_c BETWEEN -40 AND 80"), sa.CheckConstraint("sequence_number >= 0"))
    op.create_index("ix_device_time", "sensor_readings", ["device_id", "measured_at"])
    op.execute(sa.text("INSERT INTO devices (device_code,name,sensor_type,location,created_at,is_active) VALUES ('esp32-01','Unidad móvil 01','DHT22','Área de atención de la unidad móvil 01',CURRENT_TIMESTAMP,true)"))


def downgrade():
    op.drop_table("sensor_readings")
    op.drop_table("devices")
