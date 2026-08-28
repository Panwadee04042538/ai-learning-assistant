import asyncio
import logging
import time

from evaluation import EvaluationSession
from gemini_service import ask_gemini

from database import (
    get_or_create_user,
    create_session,
    save_response,
    save_feedback,
    finish_session
)


logger = logging.getLogger(__name__)

active_evaluation_sessions = set()


EVALUATION_TIMEOUT = 600


# ==========================================
# ส่งข้อความ
# ==========================================

async def _send_message(source, message):

    # Discord Interaction
    if hasattr(source, "response"):

        if source.response.is_done():

            if source.channel is not None:

                await source.channel.send(message)

            else:

                await source.followup.send(message)

        else:

            await source.response.send_message(message)

        return

    # Discord Context
    await source.send(message)


# ==========================================
# ส่งข้อความยาว
# ==========================================

async def _send_long_message(source, text):

    if not text:

        await _send_message(
            source,
            "❌ AI ไม่ได้ตอบกลับ"
        )

        return

    max_length = 1900

    while len(text) > max_length:

        await _send_message(
            source,
            text[:max_length]
        )

        text = text[max_length:]

    await _send_message(
        source,
        text
    )


# ==========================================
# หา User และ Channel
# ==========================================

def _get_user_and_channel(source):

    user = getattr(
        source,
        "author",
        None
    )

    if user is None:

        user = source.user

    return user, source.channel


# ==========================================
# รอคำตอบ
# ==========================================

async def _wait_for_answer(
    bot,
    user,
    channel
):

    start = time.time()

    def check(message):

        return (
            message.author == user
            and message.channel == channel
        )

    message = await bot.wait_for(
        "message",
        timeout=EVALUATION_TIMEOUT,
        check=check
    )

    elapsed = round(
        time.time() - start,
        2
    )

    return message.content, elapsed


# ==========================================
# Evaluation Workflow
# ==========================================

async def start_evaluation(
    bot,
    ctx,
    topic,
    goal_id=None,
    qp=None,
    send_long_message=None
):

    topic = topic.lower()

    session_id = None
    session_finished = False
    session_registered = False
    session_key = None

    try:

        # --------------------------
        # สร้าง Evaluation Session
        # --------------------------

        session = EvaluationSession(
            topic=topic,
            goal_id=goal_id,
            qp=qp
        )

        user, channel = _get_user_and_channel(ctx)

        session_key = (
            user.id,
            channel.id
        )

        # --------------------------
        # ป้องกันเปิดซ้ำ
        # --------------------------

        if session_key in active_evaluation_sessions:

            await _send_message(
                ctx,
                "❌ คุณมี Evaluation ที่กำลังดำเนินการอยู่ในห้องนี้"
            )

            return

        active_evaluation_sessions.add(
            session_key
        )

        session_registered = True

        # --------------------------
        # Database User
        # --------------------------

        user_id = get_or_create_user(
            user.id,
            user.name
        )

        # --------------------------
        # Database Session
        # --------------------------

        session_id = create_session(
            user_id=user_id,
            topic=topic,
            phase="evaluation"
        )

        # --------------------------
        # เริ่ม Evaluation
        # --------------------------

        await _send_message(
            ctx,
            f"📊 **Evaluation Module : {topic.title()}**\n\n"
            "กรุณาตอบคำถามทีละข้อ\n"
            "ตอบตามความเข้าใจของคุณเอง"
        )

        question_no = 1

        # ==========================
        # ถามคำถาม
        # ==========================

        while not session.is_finished():

            question = session.get_current_question()

            await _send_message(
                ctx,
                f"**ข้อ {question_no}**\n{question}"
            )

            try:

                answer, elapsed = await _wait_for_answer(
                    bot,
                    user,
                    channel
                )

            except asyncio.TimeoutError:

                await _send_message(
                    ctx,
                    "⌛ หมดเวลาการทำ Evaluation"
                )

                finish_session(
                    session_id
                )

                session_finished = True

                return

            # --------------------------
            # บันทึกคำตอบ
            # --------------------------

            session.add_answer(
                answer
            )

            save_response(
                session_id=session_id,
                question_no=question_no,
                question=question,
                answer=answer,
                response_time=elapsed
            )

            question_no += 1

        # ==========================
        # วิเคราะห์ผล
        # ==========================

        await _send_message(
            ctx,
            "🤖 กำลังประเมินผล..."
        )

        prompt = session.build_prompt()

        try:

            feedback = await asyncio.to_thread(
                ask_gemini,
                prompt
            )

        except Exception:

            logger.exception(
                "Evaluation Gemini failed for session %s",
                session_id
            )

            await _send_message(
                ctx,
                "❌ Gemini Error"
            )

            finish_session(
                session_id
            )

            session_finished = True

            return

        # ==========================
        # บันทึกผลประเมิน
        # ==========================

        save_feedback(
            session_id=session_id,
            feedback=feedback
        )

        # ==========================
        # จบ Session
        # ==========================

        finish_session(
            session_id
        )

        session_finished = True

        # ==========================
        # ส่งผลประเมิน
        # ==========================

        if send_long_message:

            await send_long_message(
                ctx,
                feedback
            )

        else:

            await _send_long_message(
                ctx,
                feedback
            )

        await _send_message(
            ctx,
            "✅ Evaluation เสร็จสมบูรณ์"
        )

    # ==========================================
    # Error Handling
    # ==========================================

    except Exception:

        logger.exception(
            "Evaluation workflow failed for topic %s",
            topic
        )

        if (
            session_id is not None
            and not session_finished
        ):

            try:

                finish_session(
                    session_id
                )

            except Exception:

                logger.exception(
                    "Unable to close evaluation session %s",
                    session_id
                )

        try:

            await _send_message(
                ctx,
                "❌ เกิดข้อผิดพลาดระหว่างการทำ Evaluation"
            )

        except Exception:

            logger.exception(
                "Unable to notify user about evaluation error"
            )

    finally:

        if session_registered:

            active_evaluation_sessions.discard(
                session_key
            )