import json
import logging
from typing import Dict, Any
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are an expert AI Lead Scoring Assistant for an AI Automation Agency. 
The agency builds custom AI tools, automations, workflows (using Claude, Antigravity AI, n8n, Make, Python) for service providers, agencies, and businesses.

Your task is to analyze an X (Twitter) post text and evaluate if the poster is a prospective client who needs AI automations, workflow optimization, or custom tools to make work easier.

Return ONLY a raw JSON object with the following schema:
{
  "is_lead": boolean (true if the post indicates a need for AI automations, workflows, or tool building; false otherwise),
  "confidence_score": integer (1 to 10),
  "service_match_reason": string (1-2 sentences explaining why this is a good lead or why it was rejected),
  "suggested_comment": string (Short, 1-2 sentence, natural, conversational, non-spammy outreach response offering helpful insights/value)
}
"""

async def evaluate_tweet_lead(tweet_text: str, api_key: str) -> Dict[str, Any]:
    """
    Evaluates a tweet to determine if the author is a potential lead for AI automation services.
    Uses Gemini 2.5 Flash Lite via the google-genai SDK.
    """
    try:
        client = genai.Client(api_key=api_key)
        prompt = f"Target Tweet Content:\n\"\"\"{tweet_text}\"\"\""
        
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json"
            )
        )
        
        raw_text = response.text.strip() if response.text else ""
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()

        result = json.loads(raw_text)
        return result
    except Exception as e:
        logger.error(f"Error evaluating tweet with Gemini Flash Lite: {e}")
        return {
            "is_lead": False,
            "confidence_score": 0,
            "service_match_reason": f"Error: {str(e)}",
            "suggested_comment": ""
        }
