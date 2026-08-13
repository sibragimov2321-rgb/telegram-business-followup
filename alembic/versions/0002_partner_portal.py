"""partner and agent portal tables"""
from alembic import op
import sqlalchemy as sa

revision = "0002_partner_portal"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("portal_users", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True), sa.Column("username", sa.String(255)), sa.Column("first_name", sa.String(255)), sa.Column("last_name", sa.String(255)), sa.Column("language_code", sa.String(16)), sa.Column("photo_url", sa.Text()), sa.Column("role", sa.String(32), nullable=False, server_default="guest"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("applications", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("telegram_id", sa.BigInteger(), nullable=False), sa.Column("kind", sa.String(20), nullable=False), sa.Column("payload", sa.Text(), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="new"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("blocked_contacts", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("value", sa.String(255), nullable=False, unique=True), sa.Column("reason", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("faq_items", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("audience", sa.String(20), nullable=False), sa.Column("question", sa.Text(), nullable=False), sa.Column("answer", sa.Text(), nullable=False), sa.Column("position", sa.Integer(), nullable=False, server_default="0"), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table("support_tickets", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("telegram_id", sa.BigInteger(), nullable=False), sa.Column("subject", sa.String(255), nullable=False), sa.Column("text", sa.Text(), nullable=False), sa.Column("category", sa.String(64), nullable=False, server_default="general"), sa.Column("status", sa.String(20), nullable=False, server_default="open"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("agents", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True), sa.Column("agent_code", sa.String(64), nullable=False, unique=True), sa.Column("status", sa.String(20), nullable=False, server_default="new"), sa.Column("geo", sa.String(64)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("partners", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True), sa.Column("affiliate_code", sa.String(64), nullable=False, unique=True), sa.Column("status", sa.String(20), nullable=False, server_default="new"), sa.Column("geo", sa.String(64)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))

def downgrade():
    for name in ("partners", "agents", "support_tickets", "faq_items", "blocked_contacts", "applications", "portal_users"):
        op.drop_table(name)
