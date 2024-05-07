from typing import Dict
import chainlit as cl
from src.chain import answer_question


def format_answer(raw: Dict) -> str:
    answer = raw.get("answer", "")
    if answer == "" or str(answer).startswith("Sorry"):
        answer = "Sorry, I didn't understand your question. Can you try again?"
    else:
        answer += f"\n\nReferences:\n"
        for ref in raw.get("context", []):
            answer += "* " + ref + "\n"
    return answer


@cl.on_message
async def answer(message: cl.Message):
    answer = answer_question(message.content)
    formatted = answer.get("answer")
    await cl.Message(content=formatted).send()
