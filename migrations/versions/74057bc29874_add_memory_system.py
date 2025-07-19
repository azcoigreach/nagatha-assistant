"""add_memory_system

Revision ID: 74057bc29874
Revises: 0003_add_tasks_reminders
Create Date: 2025-07-19 16:20:41.521863

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '74057bc29874'
down_revision: Union[str, None] = '0003_add_tasks_reminders'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create memory_sections table
    op.create_table(
        'memory_sections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('persistence_level', sa.String(length=50), server_default='permanent', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_memory_sections_id'), 'memory_sections', ['id'], unique=False)
    op.create_index(op.f('ix_memory_sections_name'), 'memory_sections', ['name'], unique=True)
    
    # Create memory_entries table
    op.create_table(
        'memory_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('section_id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value_type', sa.String(length=50), server_default='string', nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['section_id'], ['memory_sections.id'], ),
        sa.ForeignKeyConstraint(['session_id'], ['conversation_sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_memory_entries_id'), 'memory_entries', ['id'], unique=False)
    op.create_index(op.f('ix_memory_entries_key'), 'memory_entries', ['key'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_memory_entries_key'), table_name='memory_entries')
    op.drop_index(op.f('ix_memory_entries_id'), table_name='memory_entries')
    op.drop_table('memory_entries')
    op.drop_index(op.f('ix_memory_sections_name'), table_name='memory_sections')
    op.drop_index(op.f('ix_memory_sections_id'), table_name='memory_sections')
    op.drop_table('memory_sections')
