"""add email and is_active to users

Revision ID: 2_add_email_and_is_active
Revises: 1d8eaa684b7d
Create Date: 2025-04-10 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '2_add_email_and_is_active'
down_revision = '1d8eaa684b7d'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('users', sa.Column('email', sa.String(), nullable=True))
    op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false'))
    op.create_unique_constraint('uq_users_email', 'users', ['email'])

def downgrade() -> None:
    op.drop_constraint('uq_users_email', 'users', type_='unique')
    op.drop_column('users', 'is_active')
    op.drop_column('users', 'email')
