"""


import os
import time
import asyncio
import discord

from discord.ext import commands
from dotenv import load_dotenv
from ui import MainMenu
from gemini_service import ask_gemini

from controllers.planning_controller import start_planning
from controllers.monitoring_controller import start_monitoring
from controllers.evaluation_controller import start_evaluation

from database import (
    get_or_create_user,
    create_session,
    save_response,
    save_feedback,
    finish_session
)

# ==========================
# Load .env
# ==========================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

# ==========================
# Discord Intent
# ==========================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# ==========================
# Ready
# ==========================

@bot.event
async def on_ready():
    print("=" * 40)
    print(f"Logged in as {bot.user}")
    print("AI Learning Assistant Ready")
    print("=" * 40)

# ==========================
# ส่งข้อความยาว
# ==========================

async def send_long_message(ctx, text):

    MAX_LENGTH = 1900

    if not text:
        await ctx.send("❌ AI ไม่ได้ตอบกลับ")
        return

    while len(text) > MAX_LENGTH:
        await ctx.send(text[:MAX_LENGTH])
        text = text[MAX_LENGTH:]

    await ctx.send(text)

# ==========================
# Hello
# ==========================

@bot.command()
async def hello(ctx):

    await ctx.send("👋 สวัสดีครับ ผมคือ AI Learning Assistant")

# ==========================
# Ask Gemini
# ==========================

@bot.command()
async def ask(ctx, *, question):

    await ctx.send("🤖 กำลังคิด...")

    try:

        answer = await asyncio.to_thread(
            ask_gemini,
            question
        )

        await send_long_message(ctx, answer)

    except Exception as e:

        await ctx.send(f"❌ เกิดข้อผิดพลาด\n```{e}```")

# ==========================
# กรุณาเลือกโมดูล
# ==========================
@bot.command()
async def start(ctx):

    await ctx.send(

        "## 🤖 AI Learning Assistant\n"
        "กรุณาเลือกโมดูล",

        view=MainMenu()

    )

# ==========================
# Planning Module
# ==========================

@bot.command()
async def planning(ctx, topic):

    await start_planning(
        bot=bot,
        ctx=ctx,
        topic=topic,
        send_long_message=send_long_message
    )



# ==========================
# Monitoring Module
# ==========================

@bot.command()
async def monitoring(ctx, topic):

    await start_monitoring(
        bot=bot,
        ctx=ctx,
        topic=topic,
        send_long_message=send_long_message
    )

# ==========================
# Evaluation Module
# ==========================

@bot.command()
async def evaluation(ctx, topic):

    await start_evaluation(
        bot=bot,
        ctx=ctx,
        topic=topic,
        send_long_message=send_long_message
    )

# ==========================
# Run Bot
# ==========================  

bot.run(TOKEN)
"""

import os
import time
import asyncio
import discord

from discord.ext import commands
from dotenv import load_dotenv
from ui import MainMenu
from gemini_service import ask_gemini

from controllers.planning_controller import start_planning
from controllers.monitoring_controller import start_monitoring
from controllers.evaluation_controller import start_evaluation
from controllers.learning_flow_controller import run_learning_flow

from database import (
    get_or_create_user,
    create_session,
    save_response,
    save_feedback,
    finish_session
)

# ==========================
# Load .env
# ==========================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

# ==========================
# Discord Intent
# ==========================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# ==========================
# Algorithm Prototype
# ==========================

ALGORITHM_GOALS = {
    "LG01": {"name": "เข้าใจความหมายและหลักการของ Algorithm", "qp": "QP01", "phases": ["Evaluation"],
             "keywords": ["algorithm คืออะไร", "อัลกอริทึมคืออะไร", "ความหมายของ algorithm"]},
    "LG02": {"name": "วิเคราะห์ปัญหาหรืองานก่อนออกแบบ Algorithm", "qp": "QP02", "phases": ["Planning", "Monitoring", "Evaluation"],
             "keywords": ["วิเคราะห์โจทย์", "วิเคราะห์ปัญหา", "ไม่รู้จะเริ่ม", "เริ่มเขียน algorithm"]},
    "LG03": {"name": "กำหนดแนวทางการแก้ปัญหา", "qp": "QP03", "phases": ["Planning", "Monitoring", "Evaluation"],
             "keywords": ["ออกแบบ algorithm", "จะทำยังไง", "กำหนดแนวทาง", "แนวทางแก้ปัญหา"]},
    "LG04": {"name": "จัดลำดับขั้นตอนการทำงาน", "qp": "QP04", "phases": ["Planning", "Monitoring", "Evaluation"],
             "keywords": ["ลำดับขั้นตอน", "เรียงขั้นตอน", "ขั้นตอนการทำงาน", "ทำก่อนทำหลัง"]},
    "LG05": {"name": "ตรวจสอบความถูกต้องของ Algorithm", "qp": "QP05", "phases": ["Monitoring", "Evaluation"],
             "keywords": ["ตรวจสอบ algorithm", "ถูกไหม", "ตรวจ algorithm", "เช็ค algorithm"]},
    "LG06": {
    "name": "เลือกใช้โครงสร้างของ Algorithm",
    "qp": "QP06",
    "phases": ["Planning", "Monitoring", "Evaluation"],
    "keywords": [
        "sequence",
        "selection",
        "loop",
        "วนซ้ำ",
        "ทำซ้ำ",
        "เงื่อนไข",
        "if",
        "if else",
        "for",
        "while",
        "ใช้โครงสร้างอะไร",
        "ควรใช้โครงสร้างอะไร",
        "โครงสร้างแบบไหน",
        "โจทย์นี้ใช้โครงสร้างอะไร",
        "โจทย์นี้เป็นโครงสร้างแบบไหน",
        "เป็น sequence ไหม",
        "เป็น selection ไหม",
        "เป็น loop ไหม",
        "ต้องใช้เงื่อนไขไหม",
        "ต้องใช้การทำซ้ำไหม",
        "โครงสร้าง Algorithm"
    ]
},
    "LG07": {"name": "ตรวจสอบและปรับปรุง Algorithm", "qp": "QP07", "phases": ["Monitoring", "Evaluation"],
             "keywords": ["ปรับปรุง algorithm", "แก้ algorithm", "ช่วยดู algorithm"]},
    "LG08": {"name": "ฝึกออกแบบ Algorithm จากสถานการณ์", "qp": "QP08", "phases": ["Planning", "Monitoring", "Evaluation"],
             "keywords": ["ฝึก algorithm", "ลองทำ algorithm", "โจทย์ algorithm", "แบบฝึกหัด algorithm"]},
}

algorithm_sessions = {}

def classify_algorithm_goal(text):
    t = text.lower().strip()
    if "คำนวณอายุ" in t and "algorithm" in t:
        return "LG03"
    if "algorithm คืออะไร" in t or "อัลกอริทึมคืออะไร" in t or "ความหมายของ algorithm" in t or "ที่ดี" in t:
        return "LG01"
    if any(k in t for k in [
    "ตรวจ",
    "ตรวจสอบ",
    "เช็ก",
    "เช็ค",
    "ถูกไหม",
    "ถูกหรือเปล่า",
    "ผิดไหม",
    "ผิดตรงไหน",
    "ใช้ได้ไหม",
    "ใช้ได้หรือเปล่า",
    "ทำงานถูกไหม",
]):
        return "LG05"
    if any(k in t for k in [
    "algorithm นี้ควรปรับปรุงตรงไหน",
    "algorithm ควรปรับปรุงตรงไหน",
    "ช่วยปรับปรุง algorithm",
    "ปรับปรุง algorithm",
    "ปรับปรุงอัลกอริทึม",
    "แก้ไข algorithm",
    "แก้ algorithm",
    "แก้ไขอัลกอริทึม",
    "ปรับให้ดีขึ้น",
]):
        return "LG07"
    if any(k in t for k in [
    "ควรใช้โครงสร้าง Algorithm แบบใด",
    "sequence",
    "selection",
    "loop",
    "ทำตามลำดับ",
    "เงื่อนไข",
    "if",
    "if else",
    "เลือก",
    "ตรวจสอบเงื่อนไข",
    "วนซ้ำ",
    "ทำซ้ำ",
    "for",
    "while",
    "ใช้โครงสร้างอะไร",
    "ควรใช้โครงสร้างอะไร",
    "โครงสร้างแบบไหน",
    "โจทย์นี้ใช้แบบไหน",
    "เป็น sequence ไหม",
    "เป็น selection ไหม",
    "เป็น loop ไหม",
    "ต้องใช้เงื่อนไขไหม",
    "ต้องใช้การทำซ้ำไหม",
]):
        return "LG06"
    if any(k in t for k in [
    "ลำดับ",
    "เรียง",
    "เรียงลำดับ",
    "ก่อนหลัง",
    "เกิดก่อน",
    "เกิดหลัง",
    "ทำก่อนทำหลัง",
    "ขั้นตอนไหนก่อน",
    "ขั้นตอนไหนหลัง",
    "เริ่มจากอะไร"]):
        return "LG04"
    if any(k in t for k in [
    "วิเคราะห์โจทย์",
    "ก่อนเขียน",
    "ลำดับแรกต้อง",
    "วิเคราะห์ปัญหา",
    "โจทย์ต้องการอะไร",
    "โจทย์ให้อะไรมา",
    "ต้องใช้ข้อมูลอะไร",
    "ข้อมูลที่ต้องใช้",
    "ข้อมูลอะไรบ้าง",
    "input คืออะไร",
    "output คืออะไร",
    "อินพุตคืออะไร",
    "เอาต์พุตคืออะไร",
]):
        return "LG02"
    if any(k in t for k in [
    "ฝึก algorithm",
    "อยากฝึก algorithm",
    "ลองทำ algorithm",
    "อยากลองทำ algorithm",
    "ทดลองทำ algorithm",
    "แบบฝึก algorithm",
    "แบบฝึกหัด algorithm",
    "ขอโจทย์ algorithm",
    "ขอโจทย์ให้ทำ",
    "โจทย์ให้ลองทำ",
    "อยากฝึกทำ algorithm",
    "อยากลองทำโจทย์ algorithm",
    "อยากลองออกแบบ algorithm",
    "ขอแบบฝึกให้ลองทำ",
    "มีโจทย์ให้ฝึก",
    "มีโจทย์ให้ลองทำ",
]):
        return "LG08"
    if any(k in t for k in [
    "ออกแบบ",
    "ออกแบบ algorithm",
    "แนวทาง",
    "แนวทางแก้ปัญหา",
    "แก้ปัญหา",
    "แก้โจทย์",
    "เขียน algorithm ยังไง",
    "จะเขียนยังไง",
    "ทำยังไง",
    "ต้องทำยังไง",
    "เริ่มเขียน",
    "เริ่มยังไง",
    "เริ่มจากอะไร",
]):
        return "LG03"

def algorithm_phase_prompt(goal_id, phase):
    prompts = {
        "LG01": {"Evaluation": "ลองอธิบายด้วยคำของตัวเองว่า **Algorithm คืออะไร**"},
        "LG02": {
            "Planning": "ก่อนลงมือออกแบบ Algorithm ลองระบุว่า **โจทย์ต้องการให้โปรแกรมทำอะไร และต้องใช้ข้อมูลอะไรบ้าง**",
            "Monitoring": "ลองตรวจคำตอบของตัวเองว่า **สิ่งที่ระบุไว้ครอบคลุมสิ่งที่โจทย์ต้องการและข้อมูลที่จำเป็นแล้วหรือยัง**",
            "Evaluation": "ลองสรุปว่า **การวิเคราะห์โจทย์ช่วยให้การออกแบบ Algorithm ดีขึ้นอย่างไร**"
        },
        "LG03": {
            "Planning": "จากโจทย์ ลองแบ่งปัญหาออกเป็นสิ่งที่ต้องทำตามลำดับก่อน ยังไม่ต้องเขียน Algorithm ที่สมบูรณ์",
            "Monitoring": "ลองตรวจว่าแนวทางที่วางไว้ **มีขั้นตอนที่ขาดหายหรือมีขั้นตอนที่ไม่จำเป็นหรือไม่**",
            "Evaluation": "ถ้าทำตามแนวทางนี้ตั้งแต่ต้นจนจบ **จะแก้ปัญหาตามโจทย์ได้จริงหรือไม่ เพราะอะไร**"
        },
        "LG04": {
            "Planning": "ลองเขียนขั้นตอนที่ต้องทำทั้งหมดก่อน แล้วพิจารณาว่าขั้นตอนไหนควรเกิดก่อนหรือหลัง",
            "Monitoring": "ลองไล่ตามขั้นตอนตั้งแต่ต้นจนจบ **มีจุดใดที่ข้ามขั้นหรือทำผิดลำดับหรือไม่**",
            "Evaluation": "เมื่อทำตามลำดับที่ออกแบบแล้ว **ผลลัพธ์ตรงกับสิ่งที่โจทย์ต้องการหรือไม่**"
        },
        "LG05": {
            "Monitoring": "ลองจำลองการทำงานของ Algorithm ทีละขั้นด้วยข้อมูลตัวอย่าง 1 ชุด แล้วดูว่ามีขั้นตอนไหนให้ผลไม่ตรงกับที่คาดหรือไม่",
            "Evaluation": "จากการจำลอง คุณคิดว่า Algorithm นี้ **ถูกต้องและครอบคลุมโจทย์แล้วหรือยัง** เพราะอะไร"
        },
        "LG06": {
            "Planning": "ลองพิจารณาว่าโจทย์นี้มีลักษณะการทำงานแบบใด เช่น **Sequence (ทำตามลำดับ), Selection (มีเงื่อนไข) หรือ Loop (ทำซ้ำ)** แล้วเลือกโครงสร้างที่เหมาะสม",
            "Monitoring": "ลองตรวจสอบว่า **โครงสร้างที่เลือกสอดคล้องกับลักษณะของโจทย์หรือไม่** และมีส่วนใดที่ควรเปลี่ยนแปลงหรือไม่",
            "Evaluation": "อธิบายว่า **ทำไมโครงสร้างที่เลือกจึงเหมาะกับโจทย์นี้**"
        },
        
        "LG07": {
            "Monitoring": "ลองหาจุดที่อาจทำให้ Algorithm **ทำงานผิดพลาดหรือไม่ครอบคลุมบางกรณี**",
            "Evaluation": "หลังจากปรับปรุงแล้ว เปรียบเทียบกับแบบเดิมว่า **อะไรดีขึ้นและยังมีข้อจำกัดอะไรอยู่หรือไม่**"
        },
        "LG08": {
            "Planning": "เริ่มจากระบุ **สิ่งที่โจทย์ต้องการ ข้อมูลที่ต้องใช้ และแนวทางแก้ปัญหา** ก่อน",
            "Monitoring": "ลองจำลองขั้นตอนที่ออกแบบด้วยข้อมูลตัวอย่าง แล้วตรวจดูว่ามีขั้นตอนไหนผิดหรือขาดหาย",
            "Evaluation": "สรุปว่า Algorithm ที่ออกแบบ **สามารถแก้โจทย์ได้ครบหรือไม่** และถ้าจะปรับปรุงจะปรับตรงไหน"
        }
    }
    return prompts.get(goal_id, {}).get(phase)

async def start_algorithm(ctx, question=None):
    goal_id = classify_algorithm_goal(question or "")
    if not goal_id:
        options = "\n".join(f"**{k}** — {v['name']}" for k, v in ALGORITHM_GOALS.items())
        await ctx.send(
            "## 🧠 Algorithm Learning Assistant\n"
            "ยังระบุ Learning Goal ไม่ชัดเจน กรุณาเลือกจากรายการ:\n\n" + options +
            "\n\nหรือใช้ `!alg LG03`"
        )
        return

    algorithm_sessions[ctx.author.id] = {
    "goal": goal_id,
    "phase_index": 0,
    "responses": [],
    "evaluation_pending": False
}
    goal = ALGORITHM_GOALS[goal_id]
    phase = goal["phases"][0]
    await ctx.send(
        f"### {goal_id} — {goal['name']}\n"
        f"**Question Pattern:** `{goal['qp']}`\n"
        f"**Phase:** {phase}\n\n"
        f"{algorithm_phase_prompt(goal_id, phase)}"
    )
    
def get_expected_behavior(question, goal_id, goal):
    """
    ตรวจสอบพฤติกรรมพิเศษที่คาดหวังจาก Test Case

    ใช้สำหรับแสดงผล Test Case Mapping เท่านั้น
    """

    question = (question or "").lower().strip()

    # =========================================
    # TC06
    # ไม่รู้จะเริ่มเขียน Algorithm ยังไง
    # =========================================

    if goal_id == "LG03":

        if (
            "ไม่รู้จะเริ่ม" in question
            or "ไม่รู้จะเริ่มเขียน" in question
            or "เริ่มเขียน algorithm ยังไง" in question
        ):
            return "Planning → ระบบให้ Scaffolded Hint"


    # =========================================
    # TC10
    # ช่วยตรวจสอบ Algorithm ให้หน่อย
    # =========================================

    if goal_id == "LG05":

        if (
            "ช่วยตรวจสอบ" in question
            or "ตรวจสอบ algorithm ให้หน่อย" in question
            or "ช่วยเช็ค algorithm" in question
            or "ตรวจ algorithm" in question
        ):
            return "Monitoring → ระบบให้จำลอง/ตรวจสอบ Algorithm"


    # =========================================
    # กรณีปกติ
    # =========================================

    return None
    
async def start_algorithm_flow(ctx, question=None):
    """
    Test Case Mapping

    Input
    → Intent / Learning Goal
    → Question Pattern
    → Metacognitive Phase
    → Expected Action (เฉพาะกรณีพิเศษ)

    หมายเหตุ:
    - ไม่เรียก run_learning_flow()
    - ไม่เริ่ม Planning / Monitoring / Evaluation Controller
    - ใช้สำหรับทดสอบ Mapping เท่านั้น
    """

    # ---------------------------------
    # ตรวจสอบ Input
    # ---------------------------------

    if not question or not question.strip():

        await ctx.send(
            "⚠️ กรุณาระบุข้อความสำหรับทดสอบ\n\n"
            "ตัวอย่าง:\n"
            "`!alg Algorithm คืออะไร`"
        )

        return


    question = question.strip()


    # ---------------------------------
    # 1. Intent Classification → LG
    # ---------------------------------

    goal_id = classify_algorithm_goal(question)


    # กรณีไม่สามารถจำแนก LG ได้
    if not goal_id:

        await ctx.send(
            "❌ **Test Case Mapping Failed**\n\n"
            f"**Input:** {question}\n\n"
            "ไม่สามารถจำแนก Learning Goal ได้"
        )

        return


    # ---------------------------------
    # 2. Learning Goal
    # ---------------------------------

    goal = ALGORITHM_GOALS.get(goal_id)


    # ป้องกันกรณี goal_id มี แต่ไม่พบข้อมูล
    if not goal:

        await ctx.send(
            "❌ **Test Case Mapping Failed**\n\n"
            f"พบ Learning Goal `{goal_id}` "
            "แต่ไม่พบข้อมูล Learning Goal"
        )

        return


    # ---------------------------------
    # 3. Question Pattern
    # ---------------------------------

    qp = goal.get("qp", "ไม่พบ QP")


    # ---------------------------------
    # 4. Metacognitive Phase
    # ---------------------------------

    phases = goal.get("phases", [])

    if phases:
        metacognitive_flow = " → ".join(phases)
    else:
        metacognitive_flow = "ไม่พบข้อมูล Phase"


    # ---------------------------------
    # 5. Expected Action
    # ---------------------------------

    expected_action = get_expected_behavior(
        question=question,
        goal_id=goal_id,
        goal=goal
    )


    # ---------------------------------
    # 6. สร้างข้อความผลการทดสอบ
    # ---------------------------------

    message = (
        "### 🎯 Learning Goal Detected\n\n"
        f"**LG:** {goal_id} — {goal['name']}\n"
        f"**QP:** `{qp}`\n"
        f"**Metacognitive Phase:** {metacognitive_flow}\n"
    )


    # แสดงเฉพาะกรณีที่มีพฤติกรรมพิเศษ
    if expected_action:

        message += (
            f"\n🧠 **Expected Action:** {expected_action}\n"
        )


    # ---------------------------------
    # 7. Test Result
    # ---------------------------------

    message += (
        "\n✅ **Test Case Mapping Success**"
    )


    # ---------------------------------
    # 8. แสดงผลและจบ
    # ---------------------------------

    await ctx.send(message)

    return
    
async def handle_algorithm_response(message):
    session = algorithm_sessions.get(message.author.id)
    if not session:
        return False

    text = message.content.strip()
    if not text or text.startswith("!"):
        return False

    session["responses"].append(text)

    if any(w in text.lower() for w in ["ไม่รู้", "ไม่เข้าใจ", "ช่วยหน่อย", "ทำไม่ได้", "ติด", "งง"]):
        await message.channel.send(
            "💡 **Scaffolded Hint**\n"
            "ยังไม่ต้องรีบเขียนคำตอบทั้งหมด ลองเริ่มจากคำถามย่อยนี้ก่อน:\n"
            "**โจทย์กำหนดอะไรมาให้เรา และต้องการให้เราได้อะไรเป็นผลลัพธ์?**"
        )
        return True

    goal = ALGORITHM_GOALS[session["goal"]]
    phase = goal["phases"][session["phase_index"]]

    if session["phase_index"] < len(goal["phases"]) - 1:
        session["phase_index"] += 1
        next_phase = goal["phases"][session["phase_index"]]

        await message.channel.send(
            f"**Phase ถัดไป: {next_phase}**\n\n"
            f"{algorithm_phase_prompt(session['goal'], next_phase)}"
        )

    else:
        if session["goal"] == "LG01":
            await message.channel.send(
                "### 🎯 สรุปการเรียนรู้\n"
                "คุณได้ทบทวนความหมายและลักษณะสำคัญของ Algorithm แล้ว"
            )

        elif session["goal"] == "LG02":
            await message.channel.send(
                "### 🎯 สรุปการเรียนรู้\n"
                "การวิเคราะห์โจทย์ช่วยให้เราทราบสิ่งที่โจทย์ต้องการ "
                "และข้อมูลที่จำเป็นก่อนออกแบบ Algorithm"
            )

        else:
            await message.channel.send(
                "### 🎯 สรุปการเรียนรู้\n"
                "สิ้นสุดกิจกรรมการเรียนรู้สำหรับ Learning Goal นี้"
            )

        algorithm_sessions.pop(message.author.id, None)
    return True

# ==========================
# Ready
# ==========================

@bot.event
async def on_ready():
    print("=" * 40)
    print(f"Logged in as {bot.user}")
    print("AI Learning Assistant Ready")
    print("=" * 40)

# ==========================
# ส่งข้อความยาว
# ==========================

async def send_long_message(ctx, text):

    MAX_LENGTH = 1900

    if not text:
        await ctx.send("❌ AI ไม่ได้ตอบกลับ")
        return

    while len(text) > MAX_LENGTH:
        await ctx.send(text[:MAX_LENGTH])
        text = text[MAX_LENGTH:]

    await ctx.send(text)

# ==========================
# Hello
# ==========================

@bot.command()
async def hello(ctx):

    await ctx.send("👋 สวัสดีครับ ผมคือ AI Learning Assistant")

# ==========================
# Ask Gemini
# ==========================

@bot.command()
async def ask(ctx, *, question):

    await ctx.send("🤖 กำลังคิด...")

    try:

        answer = await asyncio.to_thread(
            ask_gemini,
            question
        )

        await send_long_message(ctx, answer)

    except Exception as e:

        await ctx.send(f"❌ เกิดข้อผิดพลาด\n```{e}```")

# ==========================
# กรุณาเลือกโมดูล
# ==========================
@bot.command()
async def start(ctx):

    await ctx.send(

        "## 🤖 AI Learning Assistant\n"
        "กรุณาเลือกโมดูล",

        view=MainMenu()

    )

# ==========================
# Planning Module
# ==========================

@bot.command()
async def planning(ctx, topic):

    await start_planning(
        bot=bot,
        ctx=ctx,
        topic=topic,
        send_long_message=send_long_message
    )



# ==========================
# Monitoring Module
# ==========================

@bot.command()
async def monitoring(ctx, topic):

    await start_monitoring(
        bot=bot,
        ctx=ctx,
        topic=topic,
        send_long_message=send_long_message
    )

# ==========================
# Evaluation Module
# ==========================

@bot.command()
async def evaluation(ctx, topic):

    await start_evaluation(
        bot=bot,
        ctx=ctx,
        topic=topic,
        send_long_message=send_long_message
    )

# ==========================
# Run Bot
# ==========================  


# ==========================
# Algorithm Prototype Commands
# ==========================

@bot.command()
async def alg(ctx, *, question=None):
    await start_algorithm_flow(ctx, question)

@bot.command()
async def algstatus(ctx):
    session = algorithm_sessions.get(ctx.author.id)
    if not session:
        await ctx.send("ยังไม่มี Algorithm session")
        return
    goal = ALGORITHM_GOALS[session["goal"]]
    phase = goal["phases"][session["phase_index"]]
    await ctx.send(f"**LG:** {session['goal']}\n**QP:** {goal['qp']}\n**Phase:** {phase}")

@bot.command()
async def algreset(ctx):
    algorithm_sessions.pop(ctx.author.id, None)
    await ctx.send("🔄 รีเซ็ต Algorithm session แล้ว")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    handled = await handle_algorithm_response(message)
    if handled:
        return

    await bot.process_commands(message)

bot.run(TOKEN)
