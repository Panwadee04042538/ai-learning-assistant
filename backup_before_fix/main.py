import os
import json
import asyncio
import discord
from student_response_service import (
    evaluate_student_response
)
from hint_service import get_hint

from discord.ext import commands
from dotenv import load_dotenv

from ui import MainMenu
'''from gemini_service import (
    ask_gemini,
    ask_grounded_answer,
    ask_evaluation,
)'''
from typhoon_service import (
    ask_gemini,
    ask_grounded_answer,
    ask_reflection,
    ask_evaluation,
    ask_summary
)

from controllers.planning_controller import start_planning
from controllers.monitoring_controller import start_monitoring
from controllers.evaluation_controller import start_evaluation
from question_service import get_question_for_learning

from retrieval_service import RetrievalService
from learning_goal_service import LearningGoalService
from intent_service import detect_intent
from logger import (
    add_learning_log,
    update_learning_log,
    complete_learning_session
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

    MAX_LENGTH = 1900

    if not text:
        await ctx.send("❌ AI ไม่ได้ตอบกลับ")
        return

    while len(text) > MAX_LENGTH:

        await ctx.send(text[:MAX_LENGTH])

        text = text[MAX_LENGTH:]

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
            ask_gemini,
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

    question_bank_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "question_bank.json"
    )

    try:
        with open(
            question_bank_path,
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
# Practice Request Detection
# ==================================================

def is_practice_request(question):
    """
    ตรวจว่าผู้เรียนกำลังขอแบบฝึกหัดหรือโจทย์ฝึกหรือไม่
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
    # Practice Request
    # ----------------------------------------------

    if is_practice_request(question):

        practice_prompt = f"""
คุณคือ AI Learning Assistant
ผู้เรียนกำลังขอ "โจทย์ฝึกทำ" เรื่อง Algorithm

คำขอ:
{question}

ให้สร้างโจทย์ฝึกจำนวน 1 ข้อ

ข้อกำหนด:
- เหมาะกับนักเรียนระดับอาชีวศึกษา
- เป็นสถานการณ์ที่สามารถเขียน Algorithm ได้จริง
- ผู้เรียนต้องสามารถวิเคราะห์ Input, Process และ Output ได้
- อาจมี Sequence, Selection หรือ Loop ตามความเหมาะสม
- ห้ามเฉลย
- ห้ามเขียน Algorithm สำเร็จรูป
- ให้คำถามช่วยคิดไม่เกิน 3 ข้อ
- ตอบสั้น กระชับ
- ภาษาไทย

รูปแบบ:

### 📝 โจทย์ฝึก
[โจทย์]

### 💭 คำถามช่วยคิด
1. Input คืออะไร?
2. Process ต้องทำอะไรบ้าง?
3. Output คืออะไร?

### 🚀 ลองทำ
ให้ผู้เรียนเขียน Algorithm ด้วยตนเอง
"""

        try:

            practice_answer = await asyncio.to_thread(
                ask_gemini,
                practice_prompt
            )

        except Exception as e:

            practice_answer = (
                "❌ ไม่สามารถสร้างโจทย์ฝึกได้ในขณะนี้\n"
                f"`{type(e).__name__}: {e}`"
            )

        # ------------------------------------------
        # Create Practice Learning Session
        # ------------------------------------------

        user_id = ctx.author.id

        pending_learning_sessions[user_id] = {
            "learning_goal": "LG08 — ฝึกออกแบบ Algorithm จากสถานการณ์",
            "question": (
                "จากโจทย์สถานการณ์ที่กำหนด "
                "จงเขียน Algorithm เพื่อแก้ปัญหา "
                "โดยระบุขั้นตอนการทำงานให้ชัดเจน"
            ),
            "ku_id": None,
            "lg_id": "LG08",
            "question_id": "PRACTICE",
            "attempt": 1,
            "max_attempts": MAX_ATTEMPTS,
            "hint_level": 0,
            "session_id": None,
            "practice_mode": True,
            "practice_prompt": practice_answer
        }
        
        print("\n========== PRACTICE SESSION DEBUG ==========")
        print("User ID:", user_id)
        print("Session exists:", user_id in pending_learning_sessions)
        print("Session:", pending_learning_sessions.get(user_id))
        print("============================================\n")

        print("\n========== PRACTICE SESSION ==========")
        print(f"User    : {ctx.author}")
        print("LG      : LG08")
        print("Mode    : PRACTICE")
        print("Session : ACTIVE")
        print("======================================\n")

        message = (
            "## 📝 โจทย์ฝึก Algorithm\n\n"
            f"{practice_answer}\n\n"
            "💡 **เมื่อลองทำเสร็จแล้ว**\n"
            "ส่ง Algorithm ของคุณมาได้เลย "
            "ระบบจะช่วยตรวจสอบคำตอบและให้คำแนะนำ"
        )

        await send_long_message(
            ctx,
            message
        )

        return
    
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
    # Retrieval Failed
    # ----------------------------------------------

    if not knowledge_result:

        await ctx.send(

            "❌ **Knowledge Retrieval Failed**\n\n"

            f"**Input:** {question}\n\n"

            "ไม่พบข้อมูลความรู้ที่เกี่ยวข้อง"
        )

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
# Get Learning Question
# ==========================================
    learning_question = get_question_for_learning(
        lg_id=goal_id,
        ku_id=ku_id,
        user_input=question
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
    # Prepare Reflection Question
    # ==========================================

    reflection_question = learning_question.get(
        "system_question"
    )


    # ==========================================
    # Save Pending Learning Session
    # ==========================================

    if reflection_question:
        pending_learning_sessions[ctx.author.id] = {
        "learning_goal": learning_goal,
        "question": reflection_question,
        "ku_id": ku_id,
        "lg_id": goal_id,
        "question_id": learning_question.get("question_id"),
        "attempt": 1,
        "max_attempts": MAX_ATTEMPTS,
        "hint_level": 0,
        "session_id": (
            log_entry.get("session_id")
            if log_entry
            else None,       
        )
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
    # Reflection Question
    # ----------------------------------------------

    if reflection_question:

        message += (

            "\n\n### 💭 ลองคิดต่อ\n\n"

            f"{reflection_question}"
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

    print("\n========== MESSAGE DEBUG ==========")
    print("User ID:", user_id)
    print("Message:", message.content)
    print(
    "Pending users:",
    list(pending_learning_sessions.keys())
)
    print(
    "Session found:",
    user_id in pending_learning_sessions
)
    print("===================================\n")
    if user_id in pending_learning_sessions:

        session = pending_learning_sessions[user_id]


        # ------------------------------------------
        # Show Processing Message
        # ------------------------------------------

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

                ask_evaluation
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

                    f"รายละเอียด: "
                    f"{result.get('message', '-')}"
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

                "### 💬 Feedback\n\n"

                f"{feedback}\n\n"

                "### 💪 สิ่งที่ทำได้ดี\n\n"

                f"{strength}\n\n"

                "### 🔧 สิ่งที่ควรเพิ่มเติม\n\n"

                f"{improvement}\n"
            )


            # ======================================
            # GOOD
            # ======================================

            if level == "GOOD":

                feedback_message += (

                    "\n\n### 🚀 ขั้นต่อไป\n\n"

                    "🎉 คุณเข้าใจเนื้อหาได้ดีแล้ว "
                    "สามารถเรียนรู้หัวข้อถัดไปได้เลย"
                )


                # ----------------------------------
                # Send Feedback
                # ----------------------------------

                await message.channel.send(
                    feedback_message
                )


                # ----------------------------------
                # Complete Learning Session
                # ----------------------------------

                if session_id:

                    complete_learning_session(

                        session_id=session_id,

                        final_status="COMPLETED",

                        final_understanding_level="GOOD"
                    )


                # ----------------------------------
                # End Session
                # ----------------------------------

                del pending_learning_sessions[user_id]

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

                feedback_message += (

                    "\n\n### 📚 สิ้นสุดรอบการฝึกตอบ\n\n"

                    "คุณได้ลองตอบคำถามครบจำนวนครั้งที่กำหนดแล้ว\n\n"

                    "แนะนำให้กลับไปทบทวนเนื้อหา "
                    "และลองเรียนรู้ใหม่อีกครั้งนะ 😊"
                )


                await message.channel.send(
                    feedback_message
                )


                # ----------------------------------
                # Complete Learning Session
                # ----------------------------------

                if session_id:

                    complete_learning_session(

                        session_id=session_id,

                        final_status="MAX_ATTEMPTS_REACHED",

                        final_understanding_level=level
                    )


                # ----------------------------------
                # End Session
                # ----------------------------------

                del pending_learning_sessions[user_id]

                return


            # ======================================
            # PARTIAL → HINT
            # ======================================

            if level == "PARTIAL":

                # ----------------------------------
                # Progressive Hint from Hint Bank
                # ----------------------------------

                current_hint_level = session.get("hint_level", 0)
                next_hint_level = current_hint_level + 1

                hint = get_hint(
                    question_id=session.get("question_id"),
                    hint_level=next_hint_level
                )

                if hint:
                    session["hint_level"] = next_hint_level

                    hint_text = hint.get(
                        "Hint Text",
                        "ลองพิจารณาคำถามอีกครั้ง"
                    )

                    feedback_message += (

                        f"\n\n### 💡 คำใบ้ระดับที่ "
                        f"{next_hint_level}/3\n\n"

                        f"{hint_text}\n\n"

                        "💭 **ลองตอบคำถามอีกครั้ง:**\n\n"

                        f"**{session['question']}**"
                    )

                else:
                    feedback_message += (

                        f"\n\n### 💡 คำใบ้ "
                        f"(ครั้งที่ {attempt}/{max_attempts})\n\n"

                        "ลองพิจารณาแนวคิดสำคัญของเรื่องนี้อีกครั้ง\n"

                        "แล้วลองเชื่อมโยงองค์ประกอบสำคัญเข้าด้วยกัน\n\n"

                        "💭 **ลองตอบคำถามอีกครั้ง:**\n\n"

                        f"**{session['question']}**"
                    )


            # ======================================
            # NEEDS_IMPROVEMENT → EXPLAIN
            # ======================================

            elif level == "NEEDS_IMPROVEMENT":

                feedback_message += (

                    f"\n\n### 📖 ลองทบทวนเพิ่มเติม "
                    f"(ครั้งที่ {attempt}/{max_attempts})\n\n"

                    "คำตอบของคุณอาจยังไม่ตรงกับแนวคิดสำคัญของเรื่องนี้\n\n"

                    "ลองกลับไปทบทวนคำอธิบายที่ AI "
                    "ให้ไว้ก่อนหน้านี้ "
                    "และพิจารณาแนวคิดหลักอีกครั้ง\n\n"

                    "💭 จากนั้นลองตอบคำถามนี้อีกครั้ง:\n\n"

                    f"**{session['question']}**"
                )


            # --------------------------------------
            # Send Adaptive Feedback
            # --------------------------------------

            await message.channel.send(
                feedback_message
            )


            # --------------------------------------
            # Keep Session Active
            # --------------------------------------

            return


        except Exception as e:

            try:

                await processing_message.delete()

            except Exception:

                pass


            print(
                "\n========== "
                "STUDENT EVALUATION ERROR "
                "=========="
            )

            print(
                type(e).__name__
            )

            print(e)

            print(
                "==============================================\n"
            )


            await message.channel.send(

                "❌ เกิดข้อผิดพลาดระหว่างวิเคราะห์คำตอบ"
            )


        return


    # ----------------------------------------------
    # Process Other Messages
    # ----------------------------------------------

    await bot.process_commands(message)

# ==================================================
# Run Bot
# ==================================================

bot.run(TOKEN)