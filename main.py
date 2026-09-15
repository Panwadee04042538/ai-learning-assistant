import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import os
import json
import asyncio
import pandas as pd
import discord
from student_response_service import (
    evaluate_student_response
)
from hint_service import get_hint

from discord.ext import commands
from dotenv import load_dotenv

from ui import MainMenu
from config import QUESTION_BANK_PATH
from typhoon_service import (
    ask_ai,
    ask_grounded_answer,
    ask_reflection,
    ask_evaluation,
    ask_summary
)

from controllers.planning_controller import start_planning
from controllers.monitoring_controller import start_monitoring
from controllers.evaluation_controller import start_evaluation
from question_service import get_question_for_learning
try:
    from qp_service import select_qp, get_qp_by_lg_phase
except ImportError:
    from qp_service import select_qp
    get_qp_by_lg_phase = None

from retrieval_service import RetrievalService
from learning_goal_service import LearningGoalService
from intent_service import detect_intent
from logger import (
    add_learning_log,
    update_learning_log,
    complete_learning_session,
    add_metacognitive_response,
    add_hint_usage
)


# ==================================================
# Load Environment
# ==================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")


# ==================================================
# Discord Intent
# ==================================================

intents = discord.Intents.default()
intents.message_content = True


bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# ==================================================
# Services
# ==================================================

retrieval_service = RetrievalService()

learning_goal_service = LearningGoalService()


# ==================================================
# Ready Event
# ==================================================

@bot.event
async def on_ready():

    print("=" * 40)
    print(f"Logged in as {bot.user}")
    print("AI Learning Assistant Ready")
    print("=" * 40)


# ==================================================
# Send Long Message
# ==================================================

async def send_long_message(ctx, text):
    """
    ส่งข้อความยาวให้ Discord โดยพยายามตัดที่ย่อหน้า/บรรทัด/ช่องว่าง
    เพื่อไม่ให้ข้อความถูกตัดกลางคำหรือกลางประโยค
    """

    MAX_LENGTH = 1900

    if not text:
        await ctx.send("❌ AI ไม่ได้ตอบกลับ")
        return

    text = str(text).strip()

    while len(text) > MAX_LENGTH:

        # 1. พยายามตัดตรงย่อหน้า
        split_at = text.rfind(
            "\n\n",
            0,
            MAX_LENGTH
        )

        # 2. ถ้าไม่เจอ ให้ตัดตรงขึ้นบรรทัดใหม่
        if split_at == -1:
            split_at = text.rfind(
                "\n",
                0,
                MAX_LENGTH
            )

        # 3. ถ้าไม่เจอ ให้ตัดตรงช่องว่าง
        if split_at == -1:
            split_at = text.rfind(
                " ",
                0,
                MAX_LENGTH
            )

        # 4. ถ้ายังหาไม่ได้จริง ๆ
        #    ตัดที่ MAX_LENGTH เพื่อป้องกัน loop ไม่จบ
        if split_at == -1:
            split_at = MAX_LENGTH

        chunk = text[:split_at].strip()

        # ป้องกันกรณี chunk ว่าง
        if not chunk:
            split_at = MAX_LENGTH
            chunk = text[:split_at].strip()

        await ctx.send(chunk)

        # ตัดส่วนที่ส่งไปแล้วออก
        text = text[split_at:].lstrip()

    # ส่งข้อความส่วนสุดท้าย
    if text:
        await ctx.send(text)


# ==================================================
# Hello Command
# ==================================================

@bot.command()
async def hello(ctx):

    await ctx.send(
        "👋 สวัสดีครับ ผมคือ AI Learning Assistant"
    )


# ==================================================
# Ask Gemini Command
# ==================================================

@bot.command()
async def ask(ctx, *, question):

    await ctx.send("🤖 กำลังคิด...")

    try:

        answer = await asyncio.to_thread(
            ask_ai,
            question
        )

        await send_long_message(
            ctx,
            answer
        )

    except Exception as e:

        await ctx.send(
            f"❌ เกิดข้อผิดพลาด\n```{e}```"
        )


# ==================================================
# Start Menu
# ==================================================

@bot.command()
async def start(ctx):

    await ctx.send(

        "## 🤖 AI Learning Assistant\n"
        "กรุณาเลือกโมดูล",

        view=MainMenu()
    )


# ==================================================
# Planning Module
# ==================================================

@bot.command()
async def planning(ctx, topic):

    await start_planning(

        bot=bot,
        ctx=ctx,
        topic=topic,
        send_long_message=send_long_message
    )


# ==================================================
# Monitoring Module
# ==================================================

@bot.command()
async def monitoring(ctx, topic):

    await start_monitoring(

        bot=bot,
        ctx=ctx,
        topic=topic,
        send_long_message=send_long_message
    )


# ==================================================
# Evaluation Module
# ==================================================

@bot.command()
async def evaluation(ctx, topic):

    await start_evaluation(

        bot=bot,
        ctx=ctx,
        topic=topic,
        send_long_message=send_long_message
    )


# ==================================================
# Learning Goal Detection
# ==================================================

def parse_related_ku(value):
    if not value:
        return []

    text = str(value).strip().upper()

    # รองรับ dash หลายแบบ
    text = (
        text
        .replace("–", "-")
        .replace("—", "-")
    )

    # เอาเฉพาะบรรทัดแรก
    text = text.split("\n")[0].strip()

    results = []

    # comma separated
    parts = [
        x.strip()
        for x in text.split(",")
        if x.strip()
    ]

    for part in parts:

        # Range เช่น KU01-KU06
        if "-" in part:
            start, end = (
                x.strip()
                for x in part.split("-", 1)
            )

            # ตัดข้อความส่วนขยาย
            start = start.split()[0]
            end = end.split()[0]

            if (
                start.startswith("KU")
                and end.startswith("KU")
                and len(start) == 4
                and len(end) == 4
                and start[2:].isdigit()
                and end[2:].isdigit()
            ):
                start_num = int(start[2:])
                end_num = int(end[2:])

                for number in range(start_num, end_num + 1):
                    ku_id = f"KU{number:02d}"

                    if ku_id not in results:
                        results.append(ku_id)

                continue

        # KU เดี่ยว
        candidate = part[:4]

        if (
            candidate.startswith("KU")
            and len(candidate) == 4
            and candidate[2:].isdigit()
        ):
            if candidate not in results:
                results.append(candidate)

    return results


def detect_learning_goal(question):
    """
    Learning Mapping

    User Question
        ↓
    Intent Detection
        ↓
    Learning Goal
        ↓
    Question Bank Mapping
        ↓
    Allowed Knowledge Units
        ↓
    Knowledge Retrieval
        ↓
    Learning Mapping Result
    """

    if not question or not question.strip():
        return None, None, None

    question = question.strip()

    # ==========================================
    # 1. INTENT → LEARNING GOAL
    # ==========================================

    intent_result = detect_intent(question)

    goal = None
    intent_lg_id = None

    if intent_result:
        intent_lg_id = intent_result.get("lg_id")

        if intent_lg_id:
            goal = (
                learning_goal_service
                .get_learning_goal_by_id(intent_lg_id)
            )

    # ==========================================
    # 2. FIND ALLOWED KU FROM QUESTION BANK
    # ==========================================

    allowed_ku_ids = []

    try:
        with open(
            QUESTION_BANK_PATH,
            "r",
            encoding="utf-8"
        ) as file:
            question_bank_data = json.load(file)

        question_bank = question_bank_data.get(
            "question_bank",
            []
        )

    except Exception as e:
        print(f"⚠️ Question Bank Load Error: {e}")
        question_bank = []

    # ==========================================
    # 3. LG → ALLOWED KU
    # ==========================================

    if intent_lg_id:

        for question_item in question_bank:

            question_lg = str(
                question_item.get(
                    "lg_id",
                    ""
                )
            ).strip().upper()

            if (
                question_lg
                != str(intent_lg_id).strip().upper()
            ):
                continue

            related_ku = question_item.get(
                "related_ku",
                ""
            )

            ku_ids = parse_related_ku(
                related_ku
            )

            for ku_id in ku_ids:

                if ku_id not in allowed_ku_ids:
                    allowed_ku_ids.append(ku_id)

    print("\n========== LEARNING MAPPING ==========")
    print(f"Question: {question}")
    print(f"Intent LG: {intent_lg_id}")
    print(f"Allowed KU: {allowed_ku_ids}")
    print("=======================================\n")

    # ==========================================
    # 4. KNOWLEDGE RETRIEVAL
    # ==========================================

    if allowed_ku_ids:

        knowledge_result = (
            retrieval_service
            .get_best_match(
                question,
                allowed_ku_ids=allowed_ku_ids
            )
        )

    else:

        knowledge_result = (
            retrieval_service
            .get_best_match(
                question
            )
        )

    # ==========================================
    # 5. GET UNIT
    # ==========================================

    unit = None

    if knowledge_result:
        unit = knowledge_result.get("unit")

    # ==========================================
    # 6. FALLBACK LG
    # ==========================================

    if not goal and unit:

        goal = (
            learning_goal_service
            .get_primary_learning_goal(unit)
        )

    # ==========================================
    # 7. ATTACH INTENT
    # ==========================================

    if (
        knowledge_result
        and intent_result
    ):
        knowledge_result["intent_result"] = intent_result

    # ==========================================
    # 8. RETURN
    # ==========================================

    return (
        goal,
        unit,
        knowledge_result
    )


pending_learning_sessions = {}
MAX_ATTEMPTS = 3

# ==================================================
# Allowed Knowledge Units Helper
# ==================================================

def get_allowed_ku_ids_for_lg(lg_id):
    """
    Return all KU IDs mapped to the specified Learning Goal
    from question_bank.json.

    This helper is intentionally independent from Retrieval.
    It is used when Retrieval returns no direct KU so that
    the AI Knowledge Completion path can still report the
    correct learning scope.
    """

    if not lg_id:
        return []

    try:
        with open(
            QUESTION_BANK_PATH,
            "r",
            encoding="utf-8"
        ) as file:
            question_bank_data = json.load(file)

        question_bank = question_bank_data.get(
            "question_bank",
            []
        )

    except Exception as e:
        print(f"⚠️ Question Bank Load Error: {e}")
        return []

    allowed_ku_ids = []

    target_lg = str(lg_id).strip().upper()

    for question_item in question_bank:

        question_lg = str(
            question_item.get(
                "lg_id",
                ""
            )
        ).strip().upper()

        if question_lg != target_lg:
            continue

        related_ku = question_item.get(
            "related_ku",
            ""
        )

        ku_ids = parse_related_ku(
            related_ku
        )

        for ku_id in ku_ids:

            if ku_id not in allowed_ku_ids:
                allowed_ku_ids.append(ku_id)

    return allowed_ku_ids



# ==================================================
# QP / Metacognition Helpers
# ==================================================

def get_session_qp(lg_id, phase, exclude_question_ids=None):
    """
    เลือก QP จาก QP.xlsx ตาม LG + Phase

    ใช้ qp_service เป็นหลัก และมี fallback อ่าน QP.xlsx โดยตรง
    เพื่อป้องกันกรณี qp_service.py ในเครื่องยังเป็นรุ่นเก่า
    """
    excluded = {str(x).strip().upper() for x in (exclude_question_ids or [])}

    # 1) ใช้ qp_service ถ้ามี
    try:
        if get_qp_by_lg_phase is not None:
            candidates = get_qp_by_lg_phase(lg_id, phase) or []
            for qp in candidates:
                qid = str(qp.get("question_id", "")).strip().upper()
                if qid not in excluded:
                    print(
                        f"[QP SELECT] LG={lg_id} Phase={phase} "
                        f"Question={qp.get('question_id')} QP={qp.get('qp_id')}"
                    )
                    return qp
    except Exception as e:
        print(f"[QP SERVICE WARNING] {type(e).__name__}: {e}")

    # 2) fallback: select_qp จาก qp_service รุ่นเก่า/ต่าง signature
    try:
        qp = select_qp(
            lg_id=lg_id,
            phase=phase,
            exclude_question_ids=list(excluded)
        )
        if qp:
            print(
                f"[QP SELECT FALLBACK] LG={lg_id} Phase={phase} "
                f"Question={qp.get('question_id')} QP={qp.get('qp_id')}"
            )
            return qp
    except Exception as e:
        print(f"[QP SELECT WARNING] {type(e).__name__}: {e}")

    # 3) fallback สุดท้าย: อ่าน QP.xlsx โดยตรง
    try:
        qp_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "QP.xlsx"
        )

        df = pd.read_excel(qp_path).dropna(how="all")

        current_lg = ""
        target_lg = str(lg_id).strip().upper()
        target_phase = str(phase).strip().lower()

        for _, row in df.iterrows():
            values = [str(v).strip() for v in row.tolist()
                      if pd.notna(v) and str(v).strip()]
            row_text = " | ".join(values)

            # LG header เช่น "LG08 ..."
            import re
            m = re.search(r"\bLG\s*0*(\d+)\b", row_text, re.IGNORECASE)
            if m:
                current_lg = f"LG{int(m.group(1)):02d}"

            raw_lg = str(row.get("LG ID", "")).strip()
            if raw_lg and raw_lg.lower() != "nan":
                current_lg = raw_lg.upper()

            qid = str(row.get("Question ID", "")).strip()
            phase_value = str(row.get("Phase", "")).strip()
            system_question = str(row.get("System Question", "")).strip()

            if not qid or qid.lower() == "nan":
                continue
            if not phase_value or phase_value.lower() == "nan":
                continue
            if not system_question or system_question.lower() == "nan":
                continue
            if current_lg != target_lg:
                continue
            if phase_value.lower() != target_phase:
                continue
            if qid.upper() in excluded:
                continue

            qp = {
                "question_id": qid,
                "lg_id": current_lg,
                "qp_id": str(row.get("QP ID", "")).strip(),
                "related_ku": str(row.get("Related KU", "")).strip(),
                "trigger": str(
                    row.get("Example User Input / Trigger", "")
                ).strip(),
                "phase": phase_value,
                "system_question": system_question,
                "question_purpose": str(
                    row.get("Question Purpose", "")
                ).strip(),
                "expect_input": str(
                    row.get("Expect Input", "")
                ).strip(),
            }

            print(
                f"[QP SELECT DIRECT] LG={target_lg} Phase={phase} "
                f"Question={qid} QP={qp['qp_id']}"
            )
            return qp

    except Exception as e:
        print(f"⚠️ QP.xlsx Direct Read Error: {type(e).__name__}: {e}")

    print(f"[QP NOT FOUND] LG={lg_id} Phase={phase}")
    return None


def build_qp_feedback_prompt(qp, student_answer, learning_goal, context=""):
    return f"""
คุณคือ AI Learning Assistant ทำหน้าที่เป็นผู้ช่วยด้าน Metacognition

Learning Goal: {learning_goal}
Phase: {qp.get('phase', '-')}
คำถาม QP: {qp.get('system_question', '-')}
จุดประสงค์ของคำถาม: {qp.get('question_purpose', '-')}
สิ่งที่คาดหวังให้ผู้เรียนตอบ: {qp.get('expect_input', '-')}
บริบทเพิ่มเติม: {context or '-'}

คำตอบของผู้เรียน:
{student_answer}

หน้าที่:
1. สะท้อนคำตอบของผู้เรียนอย่างสั้นและตรงประเด็น
2. ชี้ให้เห็นจุดที่คิดหรือวางแผนได้ดี
3. ถ้ามีจุดที่ควรตรวจสอบ ให้ชี้เป็นคำแนะนำสั้น ๆ โดยไม่เฉลยทั้งหมด
4. ห้ามสร้างคำถาม Metacognition ใหม่
5. ไม่ต้องให้คะแนนและไม่ต้องรายงาน progress
6. ภาษาไทย เหมาะกับนักเรียนระดับอาชีวศึกษา

ตอบไม่เกิน 5 บรรทัด
"""


async def handle_qp_response(message, session):
    """ประมวลผลคำตอบ QP โดยไม่ใช้ attempt ของ Adaptive Practice"""
    phase = session.get("phase", "")
    qp = session.get("active_qp") or {}
    student_answer = message.content.strip()

    processing = await message.channel.send("🧠 กำลังสะท้อนคำตอบของคุณ...")
    try:
        prompt = build_qp_feedback_prompt(
            qp, student_answer, session.get("learning_goal", "-"),
            session.get("practice_prompt", "")
        )
        qp_feedback = await asyncio.to_thread(ask_ai, prompt)
    except Exception as e:
        qp_feedback = "ลองตรวจสอบเหตุผลของคำตอบกับคำถามอีกครั้ง แล้วนำแนวคิดนั้นไปใช้ในขั้นตอนถัดไป"
        print(f"⚠️ QP Response Error: {type(e).__name__}: {e}")
    finally:
        try:
            await processing.delete()
        except Exception:
            pass

    add_metacognitive_response(
        session_id=session.get("session_id"),
        phase=qp.get("phase", phase),
        question_id=qp.get("question_id"),
        qp_id=qp.get("qp_id"),
        system_question=qp.get("system_question"),
        student_answer=student_answer,
        feedback=qp_feedback
    )

    session.setdefault("qp_responses", []).append({
        "question_id": qp.get("question_id"),
        "qp_id": qp.get("qp_id"),
        "phase": phase,
        "question": qp.get("system_question"),
        "student_answer": student_answer,
        "feedback": qp_feedback,
    })

    if phase == "PLANNING_QP":
        session["phase"] = "ALGORITHM_ANSWER"
        await send_long_message(message.channel,
            "## 🧠 วางแผนก่อนลงมือ\n\n"
            f"{qp_feedback}\n\n"
            "### 🚀 ลองทำโจทย์\n\n"
            f"{session.get('algorithm_question', '-')}\n\n"
            "ส่ง Algorithm ของคุณมาได้เลย")
        return

    if phase == "MONITORING_QP":
        session["phase"] = "ALGORITHM_ANSWER"
        hint_text = session.pop("pending_hint_text", None)
        text = "## 🔎 ลองตรวจสอบอีกครั้ง\n\n" + f"{qp_feedback}\n\n"
        if hint_text:
            text += "### 💡 คำใบ้\n\n" + f"{hint_text}\n\n"
        text += "### ✏️ ลองปรับ Algorithm\n\n" + f"{session.get('algorithm_question', '-')}"
        await send_long_message(message.channel, text)
        return

    if phase == "EVALUATION_QP":
        session["reflection_shown"] = True
        session_id = session.get("session_id")
        if session_id:
            complete_learning_session(
                session_id=session_id,
                final_status=session.get("pending_final_status", "COMPLETED"),
                final_understanding_level=session.get("last_understanding_level", "GOOD")
            )
        await send_long_message(message.channel,
            "## 🪞 สะท้อนการเรียนรู้\n\n"
            f"{qp_feedback}\n\n"
            "🎉 จบรอบการเรียนรู้ครั้งนี้แล้ว")
        pending_learning_sessions.pop(message.author.id, None)
        return


# ==================================================
# Practice Request Detection
# ==================================================

def is_practice_request(question):
    """
    ตรวจว่าผู้เรียนกำลังขอแบบฝึกหัด/โจทย์ฝึกหรือไม่
    """

    if not question:
        return False

    text = question.strip().lower()

    practice_patterns = [
        "ขอโจทย์ฝึก",
        "ขอโจทย์ฝึกหน่อย",
        "ขอโจทย์",
        "ขอแบบฝึก",
        "ขอแบบฝึกทำ",
        "ขอแบบฝึกหัด",
        "ขอแบบฝึกหัดฝึกทำ",
        "ขอแบบฝึกหัดฝึกทำหน่อย",
        "มีโจทย์ให้ฝึก",
        "มีโจทย์ให้ลองทำ",
        "อยากลองทำโจทย์",
        "ขอ exercise",
        "ขอโจทย์ algorithm",
        "ขอแบบฝึก algorithm",
    ]

    return any(
        pattern in text
        for pattern in practice_patterns
    )


# ==================================================
# Help Trigger Detection
# ==================================================

HELP_TRIGGER_PATTERNS = {
    # ตรวจ STILL_STUCK ก่อน STUCK เสมอ เพราะวลีอย่าง
    # "ยังไม่รู้" มีคำว่า "ไม่รู้" ปนอยู่ด้วย
    "STILL_STUCK": ["ยังไม่รู้", "ยังคิดไม่ออก"],
    "ANSWER_REQUEST": ["ขอเฉลย", "เขียนให้หน่อย", "บอกคำตอบ"],
    "QUIT_REQUEST": ["พอแล้ว", "จบได้แล้ว", "เลิก"],
    "STUCK": ["ไม่รู้", "คิดไม่ออก", "ช่วยหน่อย", "ไม่เข้าใจ"],
}

QUIT_CONFIRM_WORDS = ["ใช่", "yes", "y", "ยืนยัน", "โอเค", "ok"]


def detect_help_trigger(text):
    """
    ตรวจจับข้อความขอความช่วยเหลือของผู้เรียน แบ่งเป็น 4 กลุ่ม:
    STUCK / STILL_STUCK / ANSWER_REQUEST / QUIT_REQUEST

    คืนค่า None ถ้าไม่ตรงกับกลุ่มใดเลย
    """

    if not text:
        return None

    normalized = text.strip()

    if not normalized:
        return None

    for category in (
        "STILL_STUCK",
        "ANSWER_REQUEST",
        "QUIT_REQUEST",
        "STUCK"
    ):
        for pattern in HELP_TRIGGER_PATTERNS[category]:
            if pattern in normalized:
                return category

    return None


def _current_question_text(session):
    """ข้อความคำถามปัจจุบันของ session ไม่ว่าจะอยู่ Phase ใด"""

    phase = session.get("phase")

    if phase in {"PLANNING_QP", "MONITORING_QP", "EVALUATION_QP"}:
        active_qp = session.get("active_qp") or {}
        return active_qp.get("system_question", "-")

    return session.get("algorithm_question") or session.get("question", "-")


async def handle_stuck_trigger(message, session):
    """โหมด STUCK / STILL_STUCK: ให้คำใบ้ระดับถัดไป ไม่นับ attempt"""

    channel = message.channel
    current_hint_level = session.get("hint_level", 0)

    if current_hint_level >= 3:
        await send_long_message(
            channel,
            "### 🔁 ลองอ่านคำถามเดิมอีกครั้ง\n\n"
            f"{_current_question_text(session)}"
        )
        return

    next_hint_level = current_hint_level + 1
    question_id = session.get("hint_question_id") or session.get("question_id")
    hint = get_hint(question_id=question_id, hint_level=next_hint_level)

    if hint:
        hint_text = hint.get("Hint Text", "ลองพิจารณาคำถามอีกครั้ง")
        add_hint_usage(
            session_id=session.get("session_id"),
            hint_question_id=hint.get("Question ID"),
            hint_level=next_hint_level,
            hint_text=hint_text,
            attempt=session.get("attempt", 1)
        )
    else:
        hint_text = "ลองทบทวนคำถามอีกครั้ง แล้วอธิบายสิ่งที่คุณเข้าใจให้มากที่สุด"

    session["hint_level"] = next_hint_level

    await send_long_message(
        channel,
        f"### 💡 คำใบ้ระดับที่ {next_hint_level}/3\n\n"
        f"{hint_text}"
    )


async def handle_answer_request_trigger(message):
    """โหมด ANSWER_REQUEST: ห้ามเฉลย กระตุ้นให้คิดต่อใน Phase เดิม"""

    await send_long_message(
        message.channel,
        "### 🙅 ขอโทษนะ เฉลยให้ไม่ได้\n\n"
        "ลองคิดต่ออีกนิด คุณทำได้แน่นอน!\n"
        "ลองทบทวนสิ่งที่รู้แล้ว แล้วลองตอบคำถามเดิมดูอีกครั้ง"
    )


async def handle_quit_request_trigger(session, message):
    """โหมด QUIT_REQUEST: ถามยืนยันก่อน 1 ครั้ง"""

    session["awaiting_quit_confirmation"] = True

    await send_long_message(
        message.channel,
        "### ❓ ยืนยันการจบบทเรียน\n\n"
        "คุณต้องการจบบทเรียนนี้ตอนนี้เลยใช่หรือไม่?\n"
        "พิมพ์ **ใช่** เพื่อยืนยัน หรือพิมพ์ข้อความอื่นเพื่อเรียนต่อ"
    )


async def handle_quit_confirmation(message, session):
    """ประมวลผลคำตอบยืนยันการขอจบ session"""

    channel = message.channel
    user_id = message.author.id
    text = message.content.strip()

    session["awaiting_quit_confirmation"] = False

    confirmed = any(word in text.lower() for word in QUIT_CONFIRM_WORDS)

    if not confirmed:
        await send_long_message(
            channel,
            "### 👍 งั้นเรียนต่อกันเลย\n\nลองตอบคำถามปัจจุบันต่อได้เลยครับ"
        )
        return

    session_id = session.get("session_id")

    if session_id:
        complete_learning_session(
            session_id=session_id,
            final_status="CANCELLED",
            final_understanding_level=session.get("last_understanding_level")
        )

    pending_learning_sessions.pop(user_id, None)

    await send_long_message(
        channel,
        "### 👋 จบบทเรียนแล้ว\n\nขอบคุณที่ตั้งใจเรียนนะครับ แล้วกลับมาฝึกใหม่ได้เสมอ"
    )


async def handle_help_trigger(message, session, category):
    """เรียก Handler ตามประเภท Help Trigger ที่ตรวจพบ"""

    if category in ("STUCK", "STILL_STUCK"):
        await handle_stuck_trigger(message, session)
        return

    if category == "ANSWER_REQUEST":
        await handle_answer_request_trigger(message)
        return

    if category == "QUIT_REQUEST":
        await handle_quit_request_trigger(session, message)
        return


# ==================================================
# Algorithm Knowledge Test
# ==================================================

async def start_algorithm_flow(ctx, question=None):
    

    """
    Test Flow

    Input
        ↓
    Knowledge Retrieval
        ↓
    Knowledge Unit
        ↓
    Related Learning Goal
        ↓
    Display Result
    """

    if is_practice_request(question):

        practice_prompt = f"""
        คุณคือ AI Learning Assistant ผู้เรียนกำลังขอ "โจทย์ฝึกทำ" เรื่อง Algorithm
        คำขอ:
        {question}

ให้สร้างโจทย์ฝึกจำนวน 1 ข้อ

ข้อกำหนด:
- เหมาะกับนักเรียนระดับอาชีวศึกษา
- เป็นสถานการณ์ที่สามารถเขียน Algorithm ได้จริง
- ให้ผู้เรียนต้องคิด Input, Process และ Output
- อาจมี Sequence, Selection หรือ Loop ตามความเหมาะสม
- ห้ามเฉลย
- ห้ามเขียน Algorithm สำเร็จรูป
- ให้คำถามชี้นำสั้น ๆ ไม่เกิน 3 ข้อ
- ตอบสั้น กระชับ
- ภาษาไทย

รูปแบบ:

### 📝 โจทย์ฝึก
[โจทย์]

### 💭 คำถามช่วยคิด
1. Input คืออะไร?
2. Process ต้องทำอะไร?
3. Output คืออะไร?

### 🚀 ลองทำ
ให้ผู้เรียนเขียน Algorithm ด้วยตนเอง
"""

        try:

            practice_answer = await asyncio.to_thread(
                ask_ai,
                practice_prompt
            )

        except Exception as e:

            practice_answer = (
                "❌ ไม่สามารถสร้างโจทย์ฝึกได้ในขณะนี้\n"
                f"`{type(e).__name__}: {e}`"
            )

        planning_qp = get_session_qp("LG08", "Planning")

        # คำใบ้ของโหมดฝึกใช้ชุดคำใบ้ของคำถาม Monitoring ข้อแรกของ LG08
        # (hint_bank.json ผูกคำใบ้ไว้กับ Question ID ไม่มีของ "PRACTICE")
        first_monitoring_qp = get_session_qp("LG08", "Monitoring")
        hint_question_id = (
            first_monitoring_qp.get("question_id")
            if first_monitoring_qp else None
        )
        planning_text = (
            "\n\n### 🧠 วางแผนก่อนลงมือ\n\n"
            f"{planning_qp.get('system_question', '-')}\n\n"
            "✍️ **พิมพ์คำตอบของคุณใน Chat ได้เลย**"
            if planning_qp else
            "\n\n### ⚠️ ไม่พบคำถามวางแผนจาก QP.xlsx\n\n"
            "ระบบจะให้คุณลงมือเขียน Algorithm ได้เลย"
        )

        message = (
            "## 📝 โจทย์ฝึก Algorithm\n\n"
            f"{practice_answer}"
            f"{planning_text}\n\n"
            "💡 ตอบคำถามวางแผนก่อน แล้วระบบจะให้คุณลงมือเขียน Algorithm"
        )
        await send_long_message(ctx, message)

        algorithm_question = (
            "จากโจทย์สถานการณ์ที่กำหนด "
            "จงเขียน Algorithm เพื่อแก้ปัญหา "
            "โดยระบุขั้นตอนการทำงานให้ชัดเจน"
        )

        print(f"[PRACTICE QP] planning_qp={planning_qp}")

        # บันทึก Learning Log ของโหมดฝึก เพื่อใช้เป็นข้อมูลวิจัย
        practice_log = add_learning_log(
            user_id=ctx.author.id,
            username=str(ctx.author),
            user_question=question,
            ku_id=None,
            ku_title=None,
            lg_id="LG08",
            lg_name="ฝึกออกแบบ Algorithm จากสถานการณ์",
            qp_id=planning_qp.get("qp_id") if planning_qp else None,
            question_id="PRACTICE",
            system_question=practice_answer
        )

        pending_learning_sessions[ctx.author.id] = {
            "learning_goal": "LG08 — ฝึกออกแบบ Algorithm จากสถานการณ์",
            "question": algorithm_question,
            "algorithm_question": algorithm_question,
            "ku_id": None,
            "lg_id": "LG08",
            "question_id": "PRACTICE",
            "hint_question_id": hint_question_id,
            "attempt": 1,
            "max_attempts": MAX_ATTEMPTS,
            "hint_level": 0,
            "attempt_history": [],
            "qp_responses": [],
            "active_qp": planning_qp,
            "phase": "PLANNING_QP" if planning_qp else "ALGORITHM_ANSWER",
            "reflection_shown": False,
            "expected_evidence": "",
            "session_id": (
                practice_log.get("session_id") if practice_log else None
            ),
            "practice_mode": True,
            "practice_prompt": practice_answer
        }

        print("\n========== PRACTICE SESSION CREATED ==========")

        print(f"User ID: {ctx.author.id}")

        print("LG: LG08")

        print("Question ID: PRACTICE")

        print("Session:", pending_learning_sessions[ctx.author.id])

        print("==============================================\n")


        return

    # ----------------------------------------------
    # Validate Input
    # ----------------------------------------------

    if not question or not question.strip():

        await ctx.send(

            "⚠️ กรุณาระบุข้อความสำหรับทดสอบ\n\n"

            "ตัวอย่าง:\n"

            "`!alg Algorithm คืออะไร`\n"
            "`!alg อินพุตคืออะไร`\n"
            "`!alg รูปแบบวนซ้ำคืออะไร`"
        )

        return


    question = question.strip()

    # ----------------------------------------------
    # Reset Previous Learning Session
    # ----------------------------------------------
    user_id = ctx.author.id

    if user_id in pending_learning_sessions:
        old_session = pending_learning_sessions.pop(user_id)

        print(
            f"[SESSION RESET] "
            f"user={user_id} "
            f"old_session={old_session.get('session_id')} "
            f"old_lg={old_session.get('lg_id')} "
            f"new_question={question}"
        )
    # ----------------------------------------------
    # Data-driven Detection
    # ----------------------------------------------
    goal, unit, knowledge_result = (
        detect_learning_goal(question)
    )


    # ----------------------------------------------
    # Knowledge Gap / AI Learning Completion
    # ----------------------------------------------
    # "ไม่พบ KU" is a valid learning state, not a system error.
    # The Learning Goal and allowed-KU scope have already been detected.
    # If no direct KU matches, activate AI Learning Completion instead
    # of searching outside the allowed KU scope.

    if not knowledge_result:

        print("\n========== KNOWLEDGE GAP ==========")
        print(f"Question: {question}")
        intent_lg_id = (
            goal.get("lg_id")
            if goal
            else None
        )

        allowed_ku_ids = get_allowed_ku_ids_for_lg(
            intent_lg_id
        )

        print(f"Learning Goal: {intent_lg_id}")
        print(f"Allowed KU: {allowed_ku_ids}")
        print("Result: NO DIRECT KU")
        print("Mode: AI KNOWLEDGE COMPLETION")
        print("===================================\n")

        if not goal:

            await ctx.send(
                "❌ **Learning Goal Mapping Failed**\\n\\n"
                f"**Input:** {question}\\n\\n"
                "ระบบยังไม่สามารถระบุ Learning Goal "
                "เพื่อช่วยเติมเต็มความรู้ได้"
            )
            return

        goal_id = goal.get("lg_id", "-")
        learning_goal = goal.get(
            "learning_goal",
            "ไม่พบชื่อ Learning Goal"
        )

        # Build a safe, explicit completion prompt.
        # The prompt tells the AI that there is no direct KU and asks it
        # to scaffold the learner rather than pretend that a KU exists.
        allowed_text = ", ".join(allowed_ku_ids) if allowed_ku_ids else "ไม่มี KU ที่กำหนด"

        completion_prompt = f"""
คุณคือ AI Learning Assistant สำหรับช่วยผู้เรียนเรียนรู้ด้วยตนเอง

Learning Goal:
{goal_id} — {learning_goal}

คำถามของผู้เรียน:
{question}

ขอบเขต Knowledge Unit ที่ระบบอนุญาตให้ใช้เป็นบริบท:
{allowed_text}

สถานะ:
ระบบไม่พบ Knowledge Unit ที่ตรงกับคำถามนี้โดยตรง

หน้าที่ของคุณคือ "AI Learning Completion"
ไม่ใช่การรายงานว่าระบบค้นหาไม่พบ และไม่ใช่การสร้าง KU ปลอม

โปรดช่วยผู้เรียนด้วยแนวทางดังนี้:
1. อธิบายแนวคิดที่จำเป็นต่อการตอบคำถามอย่างเข้าใจง่าย
2. เชื่อมโยงคำอธิบายกับ Learning Goal ที่กำหนด
3. ช่วยผู้เรียนคิดเป็นขั้นตอนหรือใช้คำถามชี้นำ
4. ถ้าเป็นคำถามเชิงปฏิบัติ ให้เสนอแนวทางเริ่มต้น ไม่เฉลยทั้งหมดทันที
5. ห้ามอ้างว่าคำตอบมาจาก KU ใดโดยที่ระบบไม่ได้พบ KU นั้น
6. หากข้อมูลในคำถามไม่เพียงพอ ให้บอกสิ่งที่ควรพิจารณาเพิ่มเติมอย่างชัดเจน
7. ห้ามสร้างคำถาม Reflection เพิ่มเอง เพราะคำถาม Metacognition ต้องมาจาก QP.xlsx

ตอบเป็นภาษาไทย เหมาะกับนักเรียนระดับอาชีวศึกษา
"""

        try:
            ai_completion = await asyncio.to_thread(
                ask_ai,
                completion_prompt
            )
        except Exception as e:
            print("\n========== AI COMPLETION ERROR ==========")
            print(type(e).__name__)
            print(e)
            print("==========================================\n")

            ai_completion = (
                "ไม่สามารถเรียก AI เพื่อเติมเต็มความรู้ได้ในขณะนี้"
            )

        message = (
            "### 🎯 Learning Goal Detected\n\n"
            f"**LG:** {goal_id} — {learning_goal}\n\n"
            "### 🧩 Knowledge Gap Detected\n\n"
            "คำถามนี้ยังไม่มี Knowledge Unit ที่ตรงโดยตรง "
            "ในขอบเขตที่ระบบกำหนด\n\n"
            f"**Allowed KU:** "
            f"{allowed_text}\n\n"
            "### 🤖 AI Learning Completion\n\n"
            f"{ai_completion}\n\n"
            "### 🔎 สถานะการเรียนรู้\n\n"
            "ระบบตรวจพบช่องว่างของความรู้และใช้ AI "
            "ช่วยเติมเต็มเพื่อสนับสนุนการเรียนรู้"
        )

        await send_long_message(ctx, message)
        return


    # ----------------------------------------------
    # Learning Goal Failed
    # ----------------------------------------------

    if not goal:

        await ctx.send(

            "❌ **Learning Goal Mapping Failed**\n\n"

            f"**Input:** {question}\n\n"

            f"**KU:** {unit.get('ku_id')}\n"

            "พบ Knowledge Unit แต่ไม่พบ related Learning Goal"
        )

        return


    # ----------------------------------------------
    # Learning Goal Information
    # ----------------------------------------------

    goal_id = goal.get("lg_id")

    learning_goal = goal.get(
        "learning_goal",
        "ไม่พบชื่อ Learning Goal"
    )


    # ----------------------------------------------
    # Retrieval Information
    # ----------------------------------------------

    allowed_ku_ids = get_allowed_ku_ids_for_lg(
        goal.get("lg_id")
    )

    print("\n========== RETRIEVAL ==========")
    print(f"Question: {question}")
    print(f"Allowed KU: {allowed_ku_ids}")
    print(f"Result: {unit.get('ku_id', '-')}")
    print("Mode: GROUNDED KNOWLEDGE")
    print("===============================\n")

    ku_id = unit.get(
        "ku_id",
        "ไม่พบ KU"
    )

    title = unit.get(
        "title",
        "ไม่พบหัวข้อ"
    )

    matched_term = knowledge_result.get(
        "matched_term",
        "-"
    )

    match_type = knowledge_result.get(
        "match_type",
        "-"
    )

    score = knowledge_result.get(
        "score",
        "-"
    )

    # ----------------------------------------------
    # Get Concept Content
    # ----------------------------------------------

    concept_items = unit.get(
        "concept_content",
        []
    )


    concept_text = "\n\n".join(

        item.get("text", "")

        for item in concept_items

        if item.get("text")
    )
    
# ----------------------------------------------
# Generate Grounded AI Answer
# ----------------------------------------------

    if concept_text:

        try:

            ai_answer = await asyncio.to_thread(
                ask_grounded_answer,
                question,
                concept_text
            )

        except Exception as e:

            print("\n========== GROUNDED ANSWER ERROR ==========")
            print(type(e).__name__)
            print(e)
            print("===========================================\n")

            ai_answer = (
                f"❌ Grounded Answer Error:\n"
                f"`{type(e).__name__}: {e}`"
        )

    else:

        ai_answer = None

    # ==========================================
    # Select QP from QP.xlsx
    # ==========================================
    learning_question = get_session_qp(goal_id, "Evaluation")

    if not learning_question:
        learning_question = get_question_for_learning(
            lg_id=goal_id, ku_id=ku_id, user_input=question
        )

    # ==========================================
    # Validate Learning Question
    # ==========================================
    if not learning_question:
        print("\n========== LEARNING QUESTION NOT FOUND ==========")
        print(f"Question : {question}")
        print(f"LG       : {goal_id}")
        print(f"KU       : {ku_id}")
        print("=================================================\n")
        await ctx.send(
            "⚠️ **พบเนื้อหาแล้ว แต่ยังไม่พบคำถามสำหรับการเรียนรู้**\n\n"
            f"**LG:** {goal_id}\n"
            f"**KU:** {ku_id}\n\n"
            "ระบบจึงยังไม่เริ่ม Adaptive Learning Session"
        )
        return

    # ==========================================
    # Save Learning Log
    # ==========================================

    log_entry = None

    if learning_question:

        log_entry = add_learning_log(

            user_id=ctx.author.id,

            username=str(ctx.author),

            user_question=question,

            ku_id=ku_id,

            ku_title=unit.get("title"),

            lg_id=goal_id,

            lg_name=goal.get("learning_goal"),

            qp_id=learning_question.get("qp_id"),

            question_id=learning_question.get("question_id"),

            system_question=learning_question.get(
                "system_question"
            )
        )


    # ==========================================
    # Prepare QP Session
    # ==========================================
    active_qp = learning_question

    # ==========================================
    # Save Pending Learning Session
    # ==========================================
    pending_learning_sessions[ctx.author.id] = {
        "learning_goal": learning_goal,
        "question": active_qp.get("system_question", question),
        "algorithm_question": question,
        "ku_id": ku_id,
        "lg_id": goal_id,
        "question_id": active_qp.get("question_id"),
        "qp_id": active_qp.get("qp_id"),
        "attempt": 1,
        "max_attempts": MAX_ATTEMPTS,
        "hint_level": 0,
        "attempt_history": [],
        "qp_responses": [],
        "active_qp": active_qp,
        "phase": "EVALUATION_QP",
        "reflection_shown": False,
        "session_id": log_entry.get("session_id") if log_entry else None
    }

    # ----------------------------------------------
    # Build Result Message
    # ----------------------------------------------

    message = (

        "### 🎯 Learning Goal Detected\n\n"

        f"**LG:** {goal_id} — "
        f"{learning_goal}\n\n"

        "### 📚 Knowledge Retrieved\n\n"

        f"**KU:** {ku_id}\n"

        f"**หัวข้อ:** {title}\n"

        f"**Matched Term:** "
        f"`{matched_term}`\n"

        f"**Match Type:** "
        f"{match_type}\n"

        f"**Score:** "
        f"{score}\n"
    )


    # ----------------------------------------------
    # Related Learning Goals
    # ----------------------------------------------

    related_lg = unit.get(
        "related_lg",
        []
    )


    if related_lg:

        message += (

            "\n**Related LG:** "

            + ", ".join(related_lg)

            + "\n"
        )


    # ----------------------------------------------
    # AI Grounded Answer
    # ----------------------------------------------

    message += (

        "\n### 🤖 คำอธิบายจาก AI\n\n"
    )


    if ai_answer:

        message += ai_answer

    else:

        message += (

            "ยังไม่สามารถสร้างคำอธิบายจาก AI ได้"
        )


    # ----------------------------------------------
    # QP / Metacognitive Prompt
    # ----------------------------------------------

    if active_qp:
        message += (
            "\n\n### 🧠 คำถามช่วยคิด\n\n"
            f"{active_qp.get('system_question', '-')}"
        )

    # ----------------------------------------------
    # Knowledge Source
    # ----------------------------------------------

    message += (

        "\n\n### 📚 อ้างอิงเนื้อหาจาก Knowledge Unit\n\n"

        f"**KU:** {ku_id} — {title}"
    )


    # ----------------------------------------------
    # Success
    # ----------------------------------------------

    message += (

        "\n\n✅ **Test Case Mapping Success**"
    )


    # ----------------------------------------------
    # Send Result
    # ----------------------------------------------

    await send_long_message(
        ctx,
        message
    )


# ==================================================
# Algorithm Command
# ==================================================

@bot.command()
async def alg(ctx, *, question=None):

    await start_algorithm_flow(
        ctx,
        question
    )

# ==================================================
# Student Answer Listener
# ==================================================

# ==================================================
# Student Answer Listener
# ==================================================

@bot.event
async def on_message(message):

    # ----------------------------------------------
    # Debug: confirm Discord message reaches on_message
    # ----------------------------------------------
    print(
        f"[ON_MESSAGE] "
        f"user={message.author.id} "
        f"content={message.content!r}"
    )

    # ----------------------------------------------
    # Ignore Bot Messages
    # ----------------------------------------------
    if message.author.bot:
        return

    # ----------------------------------------------
    # Allow Discord Commands
    # ----------------------------------------------
    if message.content.startswith("!"):
        await bot.process_commands(message)
        return

    # ----------------------------------------------
    # Check Pending Learning Session
    # ----------------------------------------------
    user_id = message.author.id

    if user_id not in pending_learning_sessions:
        await bot.process_commands(message)
        return

    session = pending_learning_sessions[user_id]

    # ----------------------------------------------
    # Quit Confirmation (รอคำตอบยืนยันจากรอบก่อนหน้า)
    # ----------------------------------------------
    if session.get("awaiting_quit_confirmation"):
        await handle_quit_confirmation(message, session)
        return

    # ----------------------------------------------
    # Help Triggers (ติดขัด / ยังติด / ขอเฉลย / ขอจบ)
    # ----------------------------------------------
    help_category = detect_help_trigger(message.content)

    if help_category:
        await handle_help_trigger(message, session, help_category)
        return

    # ----------------------------------------------
    # QP Metacognitive Response
    # ----------------------------------------------
    # QP responses do not consume Adaptive Practice attempts.
    if session.get("phase") in {"PLANNING_QP", "MONITORING_QP", "EVALUATION_QP"}:
        await handle_qp_response(message, session)
        return

    # ----------------------------------------------
    # Show Processing Message
    # ----------------------------------------------
    processing_message = await message.channel.send(
        "🤖 กำลังวิเคราะห์คำตอบของคุณ..."
    )

    try:

        # --------------------------------------
        # Evaluate Student Answer
        # --------------------------------------
        result = await asyncio.to_thread(
            evaluate_student_response,
            session["learning_goal"],
            session["question"],
            message.content,
            ask_evaluation,
            session.get("attempt_history", []),
            session.get("expected_evidence"),
            session.get("practice_prompt")
        )

        # --------------------------------------
        # Delete Processing Message
        # --------------------------------------
        try:
            await processing_message.delete()
        except Exception:
            pass

        # --------------------------------------
        # Evaluation Failed
        # --------------------------------------
        if not result.get("success"):
            await message.channel.send(
                "❌ ไม่สามารถวิเคราะห์คำตอบได้\n\n"
                f"รายละเอียด: {result.get('message', '-')}"
            )
            return

        # --------------------------------------
        # Extract Evaluation Result
        # --------------------------------------
        level = result.get(
            "understanding_level",
            "PARTIAL"
        )

        feedback = result.get(
            "feedback",
            "-"
        )

        strength = result.get(
            "strength",
            "-"
        )

        improvement = result.get(
            "improvement",
            "-"
        )

        next_action = result.get(
            "next_action",
            "EXPLAIN"
        )

        response_type = result.get(
            "response_type",
            "ALGORITHM_ANSWER"
        )

        progress = result.get(
            "progress",
            ""
        )

        # --------------------------------------
        # Current Attempt
        # --------------------------------------
        attempt = session.get(
            "attempt",
            1
        )

        max_attempts = session.get(
            "max_attempts",
            MAX_ATTEMPTS
        )

        # --------------------------------------
        # Save Student Response to Learning Log
        # --------------------------------------
        session_id = session.get(
            "session_id"
        )

        if session_id:
            update_learning_log(
                session_id=session_id,
                student_answer=message.content,
                understanding_level=level,
                feedback=feedback,
                strength=strength,
                improvement=improvement,
                next_action=next_action,
                attempt=attempt
            )

        # --------------------------------------
        # Save Attempt History
        # --------------------------------------
        session.setdefault("attempt_history", [])

        if response_type == "ALGORITHM_ANSWER":
            session["attempt_history"].append({
                "attempt": attempt,
                "student_answer": message.content,
                "understanding_level": level,
                "improvement": improvement
            })

        # --------------------------------------
        # Conceptual Question
        # --------------------------------------
        if response_type == "CONCEPTUAL_QUESTION":
            conceptual_message = (
                f"## 💭 คำอธิบายเพิ่มเติม\n\n"
                f"{feedback}\n"
            )

            if strength and strength != "-":
                conceptual_message += (
                    f"\n### 💡 สิ่งที่ควรรู้\n\n"
                    f"{strength}\n"
                )

            if progress and progress != "-":
                conceptual_message += (
                    f"\n### 📈 ความก้าวหน้า\n\n"
                    f"{progress}\n"
                )

            conceptual_message += (
                "\nลองปรับ Algorithm จากคำอธิบายนี้ "
                "แล้วส่งคำตอบมาได้เลย 😊"
            )

            await send_long_message(
                message.channel,
                conceptual_message
            )

            # คำถามเชิงแนวคิดไม่ใช้ attempt
            return

        # --------------------------------------
        # Understanding Level Display
        # --------------------------------------
        if level == "GOOD":
            icon = "🟢"
            title = "เข้าใจเนื้อหาได้ดี"

        elif level == "PARTIAL":
            icon = "🟡"
            title = "เข้าใจเนื้อหาบางส่วน"

        else:
            icon = "🔴"
            title = "ควรทบทวนเพิ่มเติม"

        # --------------------------------------
        # Build Feedback Message
        # --------------------------------------
        feedback_message = (
            f"## {icon} ผลการวิเคราะห์คำตอบ\n\n"
            "### 📊 ระดับความเข้าใจ\n\n"
            f"**{title}**\n\n"
        )

        if feedback and feedback != "-":
            feedback_message += (
                "### 💬 Feedback\n\n"
                f"{feedback}\n\n"
            )

        if strength and strength != "-":
            feedback_message += (
                "### 💪 สิ่งที่ทำได้ดี\n\n"
                f"{strength}\n\n"
            )

        if improvement and improvement != "-":
            feedback_message += (
                "### 🔧 สิ่งที่ควรเพิ่มเติม\n\n"
                f"{improvement}\n"
            )


        # ======================================
        # GOOD
        # ======================================
        if level == "GOOD":
            await send_long_message(message.channel, feedback_message)

            evaluation_qp = get_session_qp(
                session.get("lg_id"), "Evaluation",
                exclude_question_ids=[
                    q.get("question_id") for q in session.get("qp_responses", [])
                ]
            )

            if evaluation_qp and not session.get("reflection_shown"):
                session["last_understanding_level"] = "GOOD"
                session["pending_final_status"] = "COMPLETED"
                session["active_qp"] = evaluation_qp
                session["phase"] = "EVALUATION_QP"
                session["reflection_shown"] = False
                await send_long_message(
                    message.channel,
                    "## 🪞 สะท้อนก่อนจบ\n\n"
                    f"{evaluation_qp.get('system_question', '-')}"
                )
                return

            if session_id:
                complete_learning_session(
                    session_id=session_id, final_status="COMPLETED",
                    final_understanding_level="GOOD"
                )
            pending_learning_sessions.pop(user_id, None)
            return

        # ======================================
        # PARTIAL / NEEDS_IMPROVEMENT
        # ======================================
        attempt += 1
        session["attempt"] = attempt

        # --------------------------------------
        # Maximum Attempts Reached
        # --------------------------------------
        if attempt > max_attempts:

            await send_long_message(message.channel, feedback_message)

            evaluation_qp = get_session_qp(
                session.get("lg_id"), "Evaluation",
                exclude_question_ids=[
                    q.get("question_id") for q in session.get("qp_responses", [])
                ]
            )

            if evaluation_qp and not session.get("reflection_shown"):
                session["last_understanding_level"] = level
                session["pending_final_status"] = "MAX_ATTEMPTS_REACHED"
                session["active_qp"] = evaluation_qp
                session["phase"] = "EVALUATION_QP"
                session["reflection_shown"] = False
                await send_long_message(
                    message.channel,
                    "## 🪞 สะท้อนก่อนจบ\n\n"
                    f"{evaluation_qp.get('system_question', '-')}"
                )
                return

            if session_id:
                complete_learning_session(
                    session_id=session_id,
                    final_status="MAX_ATTEMPTS_REACHED",
                    final_understanding_level=level
                )

            pending_learning_sessions.pop(user_id, None)
            return

        # ======================================
        # PARTIAL → MONITORING QP → HINT
        # ======================================
        if level == "PARTIAL":
            current_hint_level = session.get("hint_level", 0)
            next_hint_level = current_hint_level + 1
            hint = get_hint(
                question_id=(
                    session.get("hint_question_id")
                    or session.get("question_id")
                ),
                hint_level=next_hint_level
            )
            hint_text = None
            if hint:
                session["hint_level"] = next_hint_level
                hint_text = hint.get("Hint Text", "ลองพิจารณาคำถามอีกครั้ง")
                add_hint_usage(
                    session_id=session_id,
                    hint_question_id=hint.get("Question ID"),
                    hint_level=next_hint_level,
                    hint_text=hint_text,
                    attempt=attempt
                )

            monitoring_qp = get_session_qp(
                session.get("lg_id"), "Monitoring",
                exclude_question_ids=[
                    q.get("question_id") for q in session.get("qp_responses", [])
                ]
            )
            if monitoring_qp:
                session["active_qp"] = monitoring_qp
                session["phase"] = "MONITORING_QP"
                session["pending_hint_text"] = hint_text
                await send_long_message(message.channel, feedback_message)
                await send_long_message(
                    message.channel,
                    "### 🔎 ลองตรวจสอบคำตอบของตัวเอง\n\n"
                    f"{monitoring_qp.get('system_question', '-')}"
                )
                return

            if hint_text:
                feedback_message += (
                    f"\n\n### 💡 คำใบ้ระดับที่ {next_hint_level}/3\n\n"
                    f"{hint_text}\n\nลองปรับ Algorithm แล้วส่งคำตอบมาอีกครั้ง"
                )
            else:
                feedback_message += (
                    "\n\n### 💡 ลองทบทวนอีกครั้ง\n\n"
                    "ลองเชื่อมโยงองค์ประกอบสำคัญของโจทย์ แล้วปรับ Algorithm ของคุณ"
                )

        # ======================================
        # NEEDS_IMPROVEMENT → EXPLAIN
        # ======================================
        elif level == "NEEDS_IMPROVEMENT":
            monitoring_qp = get_session_qp(
                session.get("lg_id"), "Monitoring",
                exclude_question_ids=[
                    q.get("question_id") for q in session.get("qp_responses", [])
                ]
            )
            if monitoring_qp:
                session["active_qp"] = monitoring_qp
                session["phase"] = "MONITORING_QP"
                session["pending_hint_text"] = None
                await send_long_message(message.channel, feedback_message)
                await send_long_message(
                    message.channel,
                    "### 🔎 ลองตรวจสอบความคิดของตัวเอง\n\n"
                    f"{monitoring_qp.get('system_question', '-')}"
                )
                return

            feedback_message += (
                "\n\n### 📖 ลองทบทวนเพิ่มเติม\n\n"
                "คำตอบอาจยังไม่ตรงกับแนวคิดสำคัญของเรื่องนี้ "
                "ลองกลับไปทบทวนคำอธิบาย แล้วปรับ Algorithm อีกครั้ง"
            )

        # --------------------------------------
        # Send Adaptive Feedback
        # --------------------------------------
        await send_long_message(
            message.channel,
            feedback_message
        )

        return

    except Exception as e:

        try:
            await processing_message.delete()
        except Exception:
            pass

        print(
            "\n========== STUDENT EVALUATION ERROR =========="
        )
        print(type(e).__name__)
        print(e)
        print("==============================================\n")

        await message.channel.send(
            "❌ เกิดข้อผิดพลาดระหว่างวิเคราะห์คำตอบ"
        )

    return


# ==================================================
# Run Bot
# ==================================================

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("ไม่พบ DISCORD_TOKEN ในไฟล์ .env")
    bot.run(TOKEN)