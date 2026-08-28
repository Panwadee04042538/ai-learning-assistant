"""
from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

try:
    response = client.models.generate_content(
        model="models/gemini-3.6-flash",
        contents="สวัสดี"
    )

    print(response.text)

except Exception as e:
    print(e)


from knowledge_loader import *

print(load_topic("algorithm"))

print()

print(get_planning_questions("algorithm"))

print()

print(get_common_mistakes("algorithm"))

from planning import PlanningSession

session = PlanningSession("algorithm")

while not session.is_finished():

    print("\n🤖", session.get_current_question())

    answer = input("> ")

    session.add_answer(answer)

print("\n========== RESULT ==========")
print(session.get_result())


from planning import PlanningSession
from gemini_service import ask_gemini

session = PlanningSession("algorithm")

while not session.is_finished():

    print("\n🤖", session.get_current_question())

    ans = input("> ")

    session.add_answer(ans)

print("\nกำลังวิเคราะห์...\n")

prompt = session.build_prompt()

feedback = ask_gemini(prompt)

print(feedback)
"""
from database import *

user_id = get_or_create_user(
    123456789,
    "Panawadee"
)

print(user_id)

session_id = create_session(
    user_id,
    "algorithm",
    "planning"
)

print(session_id)

save_response(
    session_id,
    1,
    "Input คืออะไร",
    "น้ำหนัก ส่วนสูง"
)

save_feedback(
    session_id,
    "ตอบได้ดี"
)

finish_session(session_id)

print("Done")