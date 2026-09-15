from flask import Flask, render_template
import json
import os
from collections import Counter


# ==========================================
# Flask App
# ==========================================

app = Flask(__name__)


# ==========================================
# Paths
# ==========================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

LOG_PATH = os.path.join(
    BASE_DIR,
    "learning_logs.json"
)


# ==========================================
# Load Logs
# ==========================================

def load_logs():

    if not os.path.exists(LOG_PATH):
        return []

    try:

        with open(
            LOG_PATH,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

            if isinstance(data, list):
                return data

            return []

    except (
        json.JSONDecodeError,
        FileNotFoundError
    ):

        return []


# ==========================================
# Dashboard
# ==========================================

@app.route("/")
def dashboard():

    # --------------------------------------
    # Load Data
    # --------------------------------------

    logs = load_logs()


    # ======================================
    # Basic Summary
    # ======================================

    total_sessions = len(logs)

    unique_students = len(
        set(
            str(log.get("user_id"))
            for log in logs
            if log.get("user_id")
        )
    )


    # ======================================
    # Session Status Statistics
    # ======================================

    status_counter = Counter()

    for log in logs:

        status = log.get(
            "final_status",
            "IN_PROGRESS"
        )

        status_counter[status] += 1


    completed_sessions = status_counter.get(
        "COMPLETED",
        0
    )

    max_attempt_sessions = status_counter.get(
        "MAX_ATTEMPTS_REACHED",
        0
    )

    in_progress_sessions = status_counter.get(
        "IN_PROGRESS",
        0
    )


    # ======================================
    # Understanding Level Statistics
    # ======================================

    understanding_counter = Counter()

    for log in logs:

        level = log.get(
            "final_understanding_level"
        )

        if level:

            understanding_counter[level] += 1


    good_count = understanding_counter.get(
        "GOOD",
        0
    )

    partial_count = understanding_counter.get(
        "PARTIAL",
        0
    )

    needs_improvement_count = (
        understanding_counter.get(
            "NEEDS_IMPROVEMENT",
            0
        )
    )


    # ======================================
    # Attempt Statistics
    # ======================================

    total_attempts = 0

    for log in logs:

        responses = log.get(
            "student_responses",
            []
        )

        if isinstance(responses, list):

            total_attempts += len(responses)


    # ======================================
    # Learning Goals Statistics
    # ======================================

    lg_counter = Counter()
    lg_names = {}

    for log in logs:

        lg = log.get(
            "learning_goal",
            {}
        )

        if not isinstance(lg, dict):
            continue

        lg_id = lg.get("lg_id")
        lg_name = lg.get("name", "")

        if lg_id:

            lg_counter[lg_id] += 1

            if lg_name:

                lg_names[lg_id] = lg_name


    # ======================================
    # Knowledge Units Statistics
    # ======================================

    ku_counter = Counter()
    ku_names = {}

    for log in logs:

        ku = log.get(
            "knowledge_unit",
            {}
        )

        if not isinstance(ku, dict):
            continue

        ku_id = ku.get("ku_id")
        ku_title = ku.get("title", "")

        if ku_id:

            ku_counter[ku_id] += 1

            if ku_title:

                ku_names[ku_id] = ku_title


    # ======================================
    # Format LG Statistics
    # ======================================

    lg_stats = []

    for lg_id, count in lg_counter.most_common():

        lg_stats.append({

            "id": lg_id,

            "name": lg_names.get(
                lg_id,
                ""
            ),

            "count": count

        })


    # ======================================
    # Format KU Statistics
    # ======================================

    ku_stats = []

    for ku_id, count in ku_counter.most_common():

        ku_stats.append({

            "id": ku_id,

            "name": ku_names.get(
                ku_id,
                ""
            ),

            "count": count

        })


    # ======================================
    # Recent Logs
    # ======================================

    recent_logs = logs[-10:][::-1]


    # ======================================
    # Render Dashboard
    # ======================================

    return render_template(

        "dashboard.html",

        # ----------------------------------
        # Basic Summary
        # ----------------------------------

        total_questions=total_sessions,

        total_sessions=total_sessions,

        total_students=unique_students,


        # ----------------------------------
        # Session Statistics
        # ----------------------------------

        completed_sessions=completed_sessions,

        max_attempt_sessions=max_attempt_sessions,

        in_progress_sessions=in_progress_sessions,


        # ----------------------------------
        # Understanding Statistics
        # ----------------------------------

        good_count=good_count,

        partial_count=partial_count,

        needs_improvement_count=(
            needs_improvement_count
        ),


        # ----------------------------------
        # Attempt Statistics
        # ----------------------------------

        total_attempts=total_attempts,


        # ----------------------------------
        # LG / KU Summary
        # ----------------------------------

        total_lg=len(lg_counter),

        total_ku=len(ku_counter),

        lg_stats=lg_stats,

        ku_stats=ku_stats,


        # ----------------------------------
        # Recent Logs
        # ----------------------------------

        recent_logs=recent_logs

    )


# ==========================================
# Run Server
# ==========================================

if __name__ == "__main__":

    app.run(
        debug=True,
        port=5000
    )