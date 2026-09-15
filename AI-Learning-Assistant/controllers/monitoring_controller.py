import asyncio
import logging
import time

from database import (
    create_session,
    finish_session,
    get_or_create_user,
    save_feedback,
    save_response,
)

from gemini_service import ask_gemini
from monitoring import MonitoringSession

logger = logging.getLogger(__name__)

active_monitoring_sessions = set()

MONITORING_TIMEOUT = 600


# ==========================================
# Send Message
# ==========================================

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


# ==========================================
# Send Long Message
# ==========================================

async def _send_long_message(source, text):

    if not text:

        await _send_message(
            source,
            "❌ AI ไม่ได้ตอบกลับ"
        )

        return

    while len(text) > 1900:

        await _send_message(
            source,
            text[:1900]
        )

        text = text[1900:]

    await _send_message(
        source,
        text
    )


# ==========================================
# User / Channel
# ==========================================

def _get_user_and_channel(source):

    user = getattr(source, "author", None)

    if user is None:

        user = source.user

    return user, source.channel


# ==========================================
# Wait Submission
# ==========================================

async def _wait_for_submission(
    bot,
    user,
    channel
):

    started_at = time.time()

    def check(message):

        return (

            message.author == user

            and

            message.channel == channel

        )

    message = await bot.wait_for(

        "message",

        timeout=MONITORING_TIMEOUT,

        check=check

    )

    elapsed = round(

        time.time() - started_at,

        2

    )

    return message.content, elapsed


# ==========================================
# Monitoring Workflow
# ==========================================

async def start_monitoring(

    bot,

    ctx,

    topic,

    send_long_message=None

):

    topic = topic.lower()

    session_id = None

    session_finished = False

    session_registered = False

    session_key = None

    try:

        session = MonitoringSession(topic)

        user, channel = _get_user_and_channel(ctx)

        session_key = (

            user.id,

            channel.id

        )

        if session_key in active_monitoring_sessions:

            await _send_message(

                ctx,

                "❌ คุณมี Monitoring ที่กำลังดำเนินการอยู่ในห้องนี้"

            )

            return False

        active_monitoring_sessions.add(

            session_key

        )

        session_registered = True

        user_id = get_or_create_user(

            user.id,

            user.name

        )

        session_id = create_session(

            user_id=user_id,

            topic=topic,

            phase="monitoring"

        )

        await _send_message(

            ctx,

            f"🔍 **Monitoring Module : {topic.title()}**\n\n"

            "กรุณาส่งผลงานของคุณ\n"

            "สามารถส่งได้หลายครั้ง\n"

            "เมื่อเสร็จแล้วพิมพ์ **finish**"

        )

        attempt = 1

        while True:

            try:

                submission, elapsed = await _wait_for_submission(

                    bot,

                    user,

                    channel

                )

            except asyncio.TimeoutError:

                await _send_message(

                    ctx,

                    "⌛ หมดเวลาการใช้งาน"

                )

                finish_session(session_id)

                session_finished = True

                return

            # -------------------------
            # Finish
            # -------------------------

            if submission.lower() == "finish":

                break

            # -------------------------
            # Save Submission
            # -------------------------

            session.add_submission(
                submission
            )

            save_response(

                session_id,

                attempt,

                f"Submission {attempt}",

                submission,

                elapsed

            )

            await _send_message(

                ctx,

                "🤖 กำลังวิเคราะห์..."

            )

            prompt = session.build_prompt()
                        # -------------------------
            # Gemini
            # -------------------------

            try:

                feedback = await asyncio.to_thread(
                    ask_gemini,
                    prompt
                )

            except Exception:

                logger.exception(
                    "Monitoring failed for session %s",
                    session_id
                )

                await _send_message(
                    ctx,
                    "❌ Gemini Error"
                )

                finish_session(session_id)

                session_finished = True

                return True

            # -------------------------
            # Save Feedback
            # -------------------------

            session.add_feedback(
                feedback
            )

            save_feedback(
                session_id,
                feedback
            )

            # -------------------------
            # Send Feedback
            # -------------------------

            await (
                send_long_message
                or
                _send_long_message
            )(
                ctx,
                feedback
            )

            # -------------------------
            # Continue Monitoring
            # -------------------------

            await _send_message(

                ctx,

                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 Attempt : {attempt}\n\n"

                "หากต้องการแก้ไข\n"

                "ส่งผลงานใหม่ได้เลย\n\n"

                "หรือพิมพ์ **finish** เพื่อจบ Monitoring"

            )

            attempt += 1

        # =====================================
        # Finish Monitoring
        # =====================================

        finish_session(
            session_id
        )

        session_finished = True

        history = session.get_history()

        await _send_message(

            ctx,

            "✅ Monitoring เสร็จสมบูรณ์\n\n"

            f"จำนวนครั้งที่ส่ง : {len(history)} ครั้ง\n\n"

            "สามารถเข้าสู่ Evaluation ได้"

        )

    except Exception:

        logger.exception(

            "Monitoring workflow failed for topic %s",

            topic

        )

        if (

            session_id is not None

            and

            not session_finished

        ):

            try:

                finish_session(
                    session_id
                )

            except Exception:

                logger.exception(

                    "Unable to close monitoring session %s",

                    session_id

                )

        try:

            await _send_message(

                ctx,

                "❌ เกิดข้อผิดพลาดระหว่างการทำ Monitoring"

            )

        except Exception:

            logger.exception(

                "Unable to notify user"

            )

    finally:

        if session_registered:

            active_monitoring_sessions.discard(

                session_key

            )