"""Add notes, tags, and note_tags tables

Revision ID: 0002_add_notes
Revises: 0001_initial
Create Date: 2025-05-03
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_add_notes'
down_revision = '0001_initial'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create tags table
    op.create_table(
        'tags',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False, unique=True),
    )
    # Create notes table
    op.create_table(
        'notes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
    )
    # Create association table for notes and tags
    op.create_table(
        'note_tags',
        sa.Column('note_id', sa.Integer(), sa.ForeignKey('notes.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('tag_id', sa.Integer(), sa.ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True),
    )

def downgrade() -> None:
    op.drop_table('note_tags')
    op.drop_table('notes')
    op.drop_table('tags')