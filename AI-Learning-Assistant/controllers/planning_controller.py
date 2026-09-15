import asyncio
import logging
import time

from database import create_session, finish_session, get_or_create_user, save_feedback, save_response
from gemini_service import ask_reflection, ask_summary
from planning import PlanningSession

logger = logging.getLogger(__name__)
active_planning_sessions = set()
ANSWER_TIMEOUT = 300
REFLECTION_ROUNDS = 2


async def _send_message(source, message):
    if hasattr(source, "response"):
        if source.response.is_done():
            if source.channel is not None:
                await source.channel.send(message)
            else:
                await source.followup.send(message)
        else:
            await source.response.send_message(message)
        return
    await source.send(message)


async def _send_long_message(source, text):
    if not text:
        await _send_message(source, "❌ AI ไม่ได้ตอบกลับ")
        return
    while len(text) > 1900:
        await _send_message(source, text[:1900])
        text = text[1900:]
    await _send_message(source, text)


def _get_user_and_channel(source):
    return getattr(source, "author", None) or source.user, source.channel


async def _wait_for_answer(bot, user, channel):
    started_at = time.time()

    def check(message):
        return message.author == user and message.channel == channel

    message = await bot.wait_for("message", timeout=ANSWER_TIMEOUT, check=check)
    return message.content, round(time.time() - started_at, 2)


async def _run_reflection_rounds(bot, ctx, session, user, channel):
    for _ in range(REFLECTION_ROUNDS):
        question = await asyncio.to_thread(ask_reflection, session.build_reflection_prompt())
        await _send_message(ctx, question.strip())
        answer, _ = await _wait_for_answer(bot, user, channel)
        session.add_reflection(question, answer)


async def start_planning(bot, ctx, topic, send_long_message=None):
    """Run Planning, exactly two reflection rounds, then one final summary."""
    topic = topic.lower()
    session_id = None
    session_finished = False
    session_registered = False
    session_key = None

    try:
        session = PlanningSession(topic)
        user, channel = _get_user_and_channel(ctx)
        session_key = (user.id, channel.id)
        if session_key in active_planning_sessions:
            await _send_message(ctx, "❌ คุณมี Planning ที่กำลังดำเนินการอยู่ในห้องนี้")
            return

        active_planning_sessions.add(session_key)
        session_registered = True
        user_id = get_or_create_user(user.id, user.name)
        session_id = create_session(user_id=user_id, topic=topic, phase="planning")
        await _send_message(ctx, f"🧠 **Planning Module : {topic.title()}**\n\nกรุณาตอบคำถามทีละข้อ")

        question_no = 1
        while not session.is_finished():
            question = session.get_current_question()
            await _send_message(ctx, f"**ข้อ {question_no}**\n{question}")
            try:
                answer, elapsed = await _wait_for_answer(bot, user, channel)
            except asyncio.TimeoutError:
                await _send_message(ctx, "⏰ หมดเวลาการตอบ")
                finish_session(session_id)
                session_finished = True
                return
            session.add_answer(answer)
            save_response(session_id, question_no, question, answer, elapsed)
            question_no += 1

        try:
            await _run_reflection_rounds(bot, ctx, session, user, channel)
        except asyncio.TimeoutError:
            await _send_message(ctx, "⏰ หมดเวลาการตอบ")
            finish_session(session_id)
            session_finished = True
            return
        except Exception:
            logger.exception("Reflection failed for planning session %s", session_id)
            await _send_message(ctx, "❌ เกิดข้อผิดพลาดระหว่างการทำ Reflection")
            finish_session(session_id)
            session_finished = True
            return

        await _send_message(ctx, "🧠 กำลังวิเคราะห์...")
        try:
            feedback = await asyncio.to_thread(ask_summary, session.build_summary_prompt())
        except Exception:
            logger.exception("Summary failed for planning session %s", session_id)
            await _send_message(ctx, "❌ Gemini Error")
            finish_session(session_id)
            session_finished = True
            return

        save_feedback(session_id, feedback)
        finish_session(session_id)
        session_finished = True
        await (send_long_message or _send_long_message)(ctx, feedback)

    except Exception:
        logger.exception("Planning workflow failed for topic %s", topic)
        if session_id is not None and not session_finished:
            try:
                finish_session(session_id)
            except Exception:
                logger.exception("Unable to close planning session %s", session_id)
        try:
            await _send_message(ctx, "❌ เกิดข้อผิดพลาดระหว่างการทำ Planning")
        except Exception:
            logger.exception("Unable to notify the user about a planning failure")
    finally:
        if session_registered:
            active_planning_sessions.discard(session_key)
