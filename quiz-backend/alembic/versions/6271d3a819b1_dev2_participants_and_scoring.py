"""dev2_participants_and_scoring

Developer 2: joining, rejoining and scoring.
  - game_participants: rejoin token, nickname key, is_active, scoring state
    (correct count/time, streaks, rank, previous rank); one nickname per game
  - games.current_question_started_at: when answers opened
  - scored_questions: guards each (game, question) against being scored twice

Existing rows get the server defaults (active, zero scores, no rank yet).
game_participants uses batch mode so the migration also runs on SQLite;
on PostgreSQL it emits plain ALTER TABLE statements.

Revision ID: 6271d3a819b1
Revises: 35a0f2fc1941
Create Date: 2026-10-24 13:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6271d3a819b1'
down_revision: Union[str, None] = '35a0f2fc1941'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('games', sa.Column('current_question_started_at', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('game_participants') as batch_op:
        batch_op.add_column(sa.Column('token', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('nickname_key', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False))
        batch_op.add_column(sa.Column('correct_count', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('correct_time_ms', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('current_streak', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('best_streak', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('rank', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('previous_rank', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_game_participants_token'), ['token'], unique=True)
        batch_op.create_unique_constraint('uq_game_participants_game_nickname', ['game_id', 'nickname_key'])

    op.create_table('scored_questions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('game_id', sa.Integer(), nullable=False),
    sa.Column('question_id', sa.Integer(), nullable=False),
    sa.Column('scored_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['game_id'], ['games.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('game_id', 'question_id', name='uq_scored_questions_game_question')
    )
    op.create_index(op.f('ix_scored_questions_id'), 'scored_questions', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_scored_questions_id'), table_name='scored_questions')
    op.drop_table('scored_questions')

    with op.batch_alter_table('game_participants') as batch_op:
        batch_op.drop_constraint('uq_game_participants_game_nickname', type_='unique')
        batch_op.drop_index(batch_op.f('ix_game_participants_token'))
        batch_op.drop_column('previous_rank')
        batch_op.drop_column('rank')
        batch_op.drop_column('best_streak')
        batch_op.drop_column('current_streak')
        batch_op.drop_column('correct_time_ms')
        batch_op.drop_column('correct_count')
        batch_op.drop_column('is_active')
        batch_op.drop_column('nickname_key')
        batch_op.drop_column('token')

    op.drop_column('games', 'current_question_started_at')
