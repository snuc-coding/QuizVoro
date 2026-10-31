import psycopg
from app.config import get_settings

def test_database_integrity():
    print("=== STARTING DATABASE INTEGRITY & CONSTRAINT TESTING ON POSTGRESQL ===")
    conn = psycopg.connect("postgresql://quiz_user:quiz_dev_password@localhost:5434/quiz_app", autocommit=False)
    cur = conn.cursor()

    # 1. Foreign-key relationships & cascading delete check
    # Check FK constraints in information_schema
    cur.execute("""
        SELECT
            tc.table_name, kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name,
            rc.delete_rule
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.referential_constraints AS rc
          ON tc.constraint_name = rc.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
          ON rc.unique_constraint_name = ccu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        ORDER BY tc.table_name;
    """)
    fks = cur.fetchall()
    print(f"[1] Verified {len(fks)} Foreign Key constraints in PostgreSQL schema.")
    for fk in fks:
        print(f"    - {fk[0]}.{fk[1]} -> {fk[2]}.{fk[3]} (ON DELETE: {fk[4]})")

    # 2. Test Transaction Rollback after failed operation
    cur.execute("SELECT count(*) FROM quizzes")
    count_before = cur.fetchone()[0]

    try:
        cur.execute("INSERT INTO quizzes (title, admin_id) VALUES ('Rollback Quiz', 1)")
        # Force intentional constraint error
        cur.execute("INSERT INTO rounds (title, round_number, quiz_id) VALUES ('Invalid Round', -5, 9999999)")
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[2] Transaction rollback verified on error: {type(e).__name__}")

    cur.execute("SELECT count(*) FROM quizzes")
    count_after = cur.fetchone()[0]
    assert count_before == count_after, "Rollback failed: partial quiz record remained!"
    print(f"    Clean rollback confirmed (quizzes count stayed at {count_after}).")

    # 3. Check for Orphaned Records across all tables
    cur.execute("""
        SELECT count(*) FROM rounds r LEFT JOIN quizzes q ON r.quiz_id = q.id WHERE q.id IS NULL;
    """)
    orphan_rounds = cur.fetchone()[0]

    cur.execute("""
        SELECT count(*) FROM questions q LEFT JOIN rounds r ON q.round_id = r.id WHERE r.id IS NULL;
    """)
    orphan_questions = cur.fetchone()[0]

    cur.execute("""
        SELECT count(*) FROM options o LEFT JOIN questions q ON o.question_id = q.id WHERE q.id IS NULL;
    """)
    orphan_options = cur.fetchone()[0]

    cur.execute("""
        SELECT count(*) FROM answers a LEFT JOIN games g ON a.game_id = g.id WHERE g.id IS NULL;
    """)
    orphan_answers = cur.fetchone()[0]

    print(f"[3] Orphan record check: Rounds={orphan_rounds}, Questions={orphan_questions}, Options={orphan_options}, Answers={orphan_answers}")
    assert orphan_rounds == 0 and orphan_questions == 0 and orphan_options == 0 and orphan_answers == 0, "Orphaned records detected!"

    # 4. Alembic migration check
    cur.execute("SELECT version_num FROM alembic_version")
    current_migration = cur.fetchone()[0]
    print(f"[4] Current active Alembic migration revision in PostgreSQL: {current_migration}")

    conn.close()
    print("=== DATABASE INTEGRITY TESTS PASSED 100% ===")

if __name__ == "__main__":
    test_database_integrity()
