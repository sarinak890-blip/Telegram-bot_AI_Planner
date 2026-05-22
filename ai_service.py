import json
import logging
import httpx
from config import OPENROUTER_API_KEY
 
logger = logging.getLogger(__name__)
 
async def generate_plan(aim: str, days_count: int) -> list | None:
    system_prompt = (
        "Ты — профессиональный AI-планировщик.\n"
        f"1. Твой ответ должен содержать ровно {days_count} шагов.\n"
        "2. Выводи ответ СТРОГО в формате JSON-массива объектов: "
        "[{\"step\": 1, \"description\": \"...\"}]. Никакого другого текста."
    )
    user_prompt = f"Моя цель: {aim}. Распиши план действий ровно на {days_count} рабочих дней."

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "google/gemini-2.5-flash:free",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7
    }
 
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai",
                headers=headers,
                json=data,
                timeout=60.0
            )
            response.raise_for_status()
            
            result = response.json()
            raw_text = result['choices'][0]['message']['content']
            cleaned_text = raw_text.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_text)
 
    except Exception as e:
        logger.error(f"Ошибка при запросе к OpenRouter через HTTPX: {e}")
        return None
