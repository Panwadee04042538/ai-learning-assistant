import sqlite3

DB_PATH = "database/learning.db"


# ==========================
# เชื่อมฐานข้อมูล
# ==========================

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ==========================
# Users
# ==========================

def get_or_create_user(discord_id, username):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM users WHERE discord_id = ?",
        (str(discord_id),)
    )

    user = cursor.fetchone()

    if user:

        user_id = user["id"]

    else:

        cursor.execute(
            """
            INSERT INTO users(discord_id, username)
            VALUES (?, ?)
            """,
            (str(discord_id), username)
        )

        conn.commit()

        user_id = cursor.lastrowid

    conn.close()

    return user_id


# ==========================
# Session
# ==========================

def create_session(user_id, topic, phase):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO sessions(user_id, topic, phase)
        VALUES (?, ?, ?)
        """,
        (
            user_id,
            topic,
            phase
        )
    )

    conn.commit()

    session_id = cursor.lastrowid

    conn.close()

    return session_id


# ==========================
# Response
# ==========================

def save_response(
    session_id,
    question_no,
    question,
    answer,
    response_time=0
):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO responses(
            session_id,
            question_no,
            question,
            answer,
            response_time
        )

        VALUES (?, ?, ?, ?, ?)
        """,
        (
            session_id,
            question_no,
            question,
            answer,
            response_time
        )
    )

    conn.commit()

    conn.close()


# ==========================
# Feedback
# ==========================

def save_feedback(
    session_id,
    feedback
):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO feedback(
            session_id,
            feedback
        )

        VALUES (?, ?)
        """,
        (
            session_id,
            feedback
        )
    )

    conn.commit()

    conn.close()


# ==========================
# Finish Session
# ==========================

def finish_session(session_id):

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE sessions

        SET
            end_time = CURRENT_TIMESTAMP,
            status = 'COMPLETED'

        WHERE id = ?
        """,
        (session_id,)
    )

    conn.commit()

    conn.close()