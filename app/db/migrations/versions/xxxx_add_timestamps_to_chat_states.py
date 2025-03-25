"""add timestamps to chat states

Revision ID: xxxx
Revises: previous_revision
Create Date: 2024-03-25 15:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'xxxx'
down_revision = 'previous_revision'  # Replace with your previous revision
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add columns with default values
    op.add_column('chat_states', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.add_column('chat_states', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))

def downgrade() -> None:
    # Remove columns
    op.drop_column('chat_states', 'updated_at')
    op.drop_column('chat_states', 'created_at') 