# controllers/learning_flow_controller.py

from controllers.planning_controller import start_planning
from controllers.monitoring_controller import start_monitoring
from controllers.evaluation_controller import start_evaluation


async def run_phase(bot, ctx, phase, topic, send_long_message=None):
    """
    เรียก Controller ของแต่ละ Metacognitive Phase
    """

    if phase == "Planning":
        await start_planning(
            bot=bot,
            ctx=ctx,
            topic=topic,
            send_long_message=send_long_message
        )

    elif phase == "Monitoring":
        result = await start_monitoring(
        bot=bot,
        ctx=ctx,
        topic=topic,
        send_long_message=send_long_message
    )
    if result is not True:
        return False

    elif phase == "Evaluation":
        result = await start_evaluation(
        bot=bot,
        ctx=ctx,
        topic=topic,
        goal_id=goal_id,
        qp=algorithm_goals[goal_id]["qp"],
        send_long_message=send_long_message
)

        if result is not True:
            return False


async def run_learning_flow(
    bot,
    ctx,
    goal_id,
    algorithm_goals,
    topic="algorithm",
    send_long_message=None
):
    """
    ควบคุม Learning Flow ตาม phases ของ Learning Goal
    """

    goal = algorithm_goals.get(goal_id)

    if not goal:
        await ctx.send("❌ ไม่พบ Learning Goal")
        return

    phases = goal.get("phases", [])

    if not phases:
        await ctx.send("❌ Learning Goal นี้ยังไม่มี Phase")
        return

    await ctx.send(
        f"🧠 **เริ่ม Learning Flow**\n"
        f"**{goal_id} — {goal['name']}**\n"
        f"**QP:** `{goal['qp']}`"
    )

    for index, phase in enumerate(phases):

        await ctx.send(
            f"### Phase {index + 1}/{len(phases)}: {phase}"
        )

        await run_phase(
            bot=bot,
            ctx=ctx,
            phase=phase,
            topic=topic,
            send_long_message=send_long_message
        )

    await ctx.send(
        "🎯 **สิ้นสุด Learning Flow**\n"
        f"คุณได้ทำกิจกรรมครบตาม {goal_id} แล้ว"
    )