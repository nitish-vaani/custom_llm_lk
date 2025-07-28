import os
from openai import OpenAI
from dotenv import load_dotenv
import json
from datetime import datetime
# from prompt_for_eval.azent import get_lead_classification_prompt



# Get current date dynamically
current_date = datetime.now()
current_date_str = current_date.strftime("%B %d, %Y")  # "May 28, 2025"
current_year = current_date.year
next_year = current_year + 1

# Load API key from .env.local
load_dotenv("/app/.env.local")
api_key = os.getenv("OPENAI_API_KEY")



if not api_key:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

# Instantiate the client
client = OpenAI(api_key=api_key)


async def has_user_speech(transcript: str) -> bool:
    for line in transcript.split("\n"):
        if line.strip().lower().startswith(("user:", "you:")):
            return True
    return False


NO_USER_EVAL = "{\n\"clarity\": { \"score\": 0, \"feedback\": \"There is no user speech in the provided transcript.\" },\n\"fluency\": { \"score\": 0, \"feedback\": \"There is no user speech in the provided transcript.\" },\n\"coherence\": { \"score\": 0, \"feedback\": \"There is no user speech in the provided transcript.\" },\n\"engagement\": { \"score\": 0, \"feedback\": \"There is no user speech in the provided transcript.\" },\n\"vocabulary\": { \"score\": 0, \"feedback\": \"There is no user speech in the provided transcript.\" },\n\"listening\": { \"score\": 0, \"feedback\": \"There is no user speech in the provided transcript.\" },\n\"summary\": \"No user speech was present in the conversation for evaluation.\",\n\"tip\": \"Ensure to provide user speech in the transcript for a comprehensive evaluation of communication skills.\"\n}"

async def call_summary(transcript: str) -> str:
    """
    Takes the complete transcipt and returns a 60-100 word summary for the conversation.
    """
    load_dotenv("/app/.env.local")
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    
    client = OpenAI(api_key=api_key)

    prompt = f"""
You are a professional conversation summarizer for a flight booking service. 
Your task is to analyse the conversation transcript and pick out the key points discussed
between the user and the agent. Summary should be crisp, concise and clear. moreover,
it should be enough for anyone reading to understand the main points of the conversation.
it should not exceed 100 words.
Transcript:
{transcript}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional conversation summarizer for a flight booking service. Your task is to analyse the conversation transcript and pick out the key points discussed between the user and the agent. Summary should be crisp, concise and clear."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.2
        )

        content = response.choices[0].message.content.strip()
        result = {
            "summary": content,
            "status_code": 200
        }
        return result

    except Exception as e:
        # Return default structure with "Not Mentioned"
        result = {
            "summary": "Some error generating summary, please try again later.",
            "status_code": 400
        }
        return result


async def extract_entities_from_transcript(transcript: str, fields: list[tuple[str, str]]) -> dict:
    """
    Extracts specified entities from the USER's responses in a transcript.
    
    Parameters:
        transcript (str): The full conversation transcript.
        entity_fields (list): A list of field names you want to extract.

    Returns:
        dict: Structured result with extracted entities or default values on failure.
    """
    # Load API Key
    load_dotenv("/app/.env.local") 
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")

    client = OpenAI(api_key=api_key)

    # Prepare dynamic prompt
    field_instructions = "\n".join(
        [f"{i+1}. {field}: {desc}" for i, (field, desc) in enumerate(fields)]
    )

    # JSON template
    json_template = ",\n".join(
        [f'"{field}": {{"text": "...", "value": "...", "confidence": "..."}}' for field, _ in fields]
    )

    prompt = f"""
You are an intelligent entity extraction system. Given a conversation transcript, extract the following fields ONLY based on what the USER says.

Ignore the interviewer, assistant, or system. Focus only on USER responses.

Here are the fields to extract:
{field_instructions}

Return a JSON object in the following format:
{{
{json_template}
}}

Rules:
- "text": the actual user quote where the information is mentioned
- "value": cleaned, structured value
- "confidence": "high", "medium", "low" depending on clarity of user speech
- If the user does not mention something, return:
  {{ "text": "NA", "value": "Not Mentioned", "confidence": "NA" }}
- Do NOT include commentary. Only return valid JSON.
Transcript:
{transcript}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {
                    "role": "system",
                    "content": "You are a specialized entity extraction system that focuses on job-related lifestyle and earnings information from user responses in conversations. Extract only what the user explicitly states."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.2
        )

        content = response.choices[0].message.content
        # Remove markdown ```json ... ``` wrapping if present
        if content.startswith("```json"):
            content = content[7:]  # Remove ```json\n
        if content.endswith("```"):
            content = content[:-3]  # Remove trailing ```

        content = content.strip()
        return json.loads(content)

    except Exception as e:
        # Return default structure with "Not Mentioned"
        return {
            "error": f"Entity extraction failed: {str(e)}",
            "result": None
        }

async def conversation_eval(transcript: str) -> dict:
    """
    Evaluates a conversation based on clarity, fluency, coherence, engagement,
    vocabulary, and listening. Returns scores, feedback, a summary, and a tip.
    
    If data is insufficient, score is 0 and feedback explains that.
    """
    load_dotenv("/app/.env.local")
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    
    client = OpenAI(api_key=api_key)

    prompt = f"""
You are an expert communication evaluator.

Your task is to analyze the USER's responses in the transcript below and evaluate their speaking performance based on the following categories:

1. **Clarity** – How clear and understandable the user's responses are.
2. **Fluency** – The natural flow and smoothness of speech (even if text).
3. **Coherence** – How logically ideas are connected.
4. **Engagement** – Whether the user was actively participating or sounded interested.
5. **Vocabulary** – Use of varied and appropriate vocabulary.
6. **Listening** – Whether the user responded appropriately to what was said (shows active listening).
7. **Summary** – Summarize the user's overall participation.
8. **Tip** – Suggest one improvement the user can focus on next time.

Rules:
- Score each attribute from 0 to 5 (0 = not enough data, 5 = excellent).
- Give short feedback for each score.
- If there's not enough user data for a category, return: {{ "score": 0, "feedback": "Not enough data to evaluate" }}

Return your response in exactly the following JSON format:

{{
    "clarity": {{"score": ..., "feedback": "..."}},
    "fluency": {{"score": ..., "feedback": "..."}},
    "coherence": {{"score": ..., "feedback": "..."}},
    "engagement": {{"score": ..., "feedback": "..."}},
    "vocabulary": {{"score": ..., "feedback": "..."}},
    "listening": {{"score": ..., "feedback": "..."}},
    "summary": "...",
    "tip": "..."
}}

Only include the JSON. Do not add commentary.

Transcript:
{transcript}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional communication coach and evaluator. Evaluate user conversations with structured metrics."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3
        )
        content = response.choices[0].message.content
        if content.startswith("```json"):
            content = content[7:]  # Remove ```json\n
        if content.endswith("```"):
            content = content[:-3]  # Remove trailing ```

        content = content.strip()
        return json.loads(content)
        # result = json.loads(llm_output)
        # return result
    
    except Exception as e:
        return {
            "error": f"Evaluation failed: {str(e)}",
            "conversation_eval": {
                attr: {"score": 0, "feedback": "Not enough data to evaluate"}
                for attr in ["clarity", "fluency", "coherence", "engagement", "vocabulary", "listening"]
            } | {
                "summary": "Not enough data to evaluate",
                "tip": "Not enough data to provide a tip"
            }
        }

async def extract_job_entities_mysyara(transcript: str, fields: list[tuple[str, str]] = None) -> dict:
    """
    Extracts car-related entities from a conversation transcript, focusing on USER responses.
    """

    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not found in environment variables")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You extract structured car-related information from user responses in conversations. \
Only consider information explicitly stated by the USER. Do not guess."
                },
                {
                    "role": "user",
                    "content": f"""
Extract the following fields from the user's responses ONLY in the conversation transcript below:

- Name
- Mobile_Number
- Car_Make_Model
- Year
- Approximate_Mileage
- Location
- Slot_Booking_Time

If a field is not mentioned, set "text": "NA", "value": "Not mentioned", "confidence": "NA".

Format the result strictly as JSON like this:
{{
  "Name": {{ "text": "...", "value": "...", "confidence": "high/medium/low/NA" }},
  "Mobile_Number": {{ "text": "...", "value": "...", "confidence": "high/medium/low/NA" }},
  "Car_Make_Model": {{ "text": "...", "value": "...", "confidence": "high/medium/low/NA" }},
  "Year": {{ "text": "...", "value": "...", "confidence": "high/medium/low/NA" }},
  "Approximate_Mileage": {{ "text": "...", "value": "...", "confidence": "high/medium/low/NA" }},
  "Location": {{ "text": "...", "value": "...", "confidence": "high/medium/low/NA" }},
  "Slot_Booking_Time": {{ "text": "...", "value": "...", "confidence": "high/medium/low/NA" }},
}}

Transcript:
{transcript}
"""
                }
            ],
            temperature=0.2
        )

        content = response.choices[0].message.content.strip()
        # print("🧪 RAW RESPONSE:\n", content)

        # Remove markdown ```json ... ``` wrapping if present
        if content.startswith("```json"):
            content = content[7:]  # Remove ```json\n
        if content.endswith("```"):
            content = content[:-3]  # Remove trailing ```

        content = content.strip()
        return json.loads(content)

    except Exception as e:
        return {
            "error": f"Extraction failed: {str(e)}",
            "Name": {"text": "NA", "value": "Not mentioned", "confidence": "NA"},
            "Mobile_Number": {"text": "NA", "value": "Not mentioned", "confidence": "NA"},
            "Car_Make_Model": {"text": "NA", "value": "Not mentioned", "confidence": "NA"},
            "Year": {"text": "NA", "value": "Not mentioned", "confidence": "NA"},
            "Approximate_Mileage": {"text": "NA", "value": "Not mentioned", "confidence": "NA"},
            "Location": {"text": "NA", "value": "Not mentioned", "confidence": "NA"},
            "Slot_Booking_Time": {{ "text": "...", "value": "...", "confidence": "high/medium/low/NA" }}
        }

async def extract_job_entities_shunya(transcript: str, fields: list[tuple[str, str]] = None) -> dict:
    """
    Extracts job-related lifestyle and earnings entities from a conversation transcript,
    focusing exclusively on the USER's responses.
    """
    load_dotenv("/app/.env.local")
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")

    client = OpenAI(api_key=api_key)

    prompt = f"""
You are an information extraction system. Extract structured job-related details from the USER's responses ONLY in the conversation transcript below.

Ignore anything said by the agent, interviewer, or assistant. Focus only on what the USER says.

Extract the following fields:

1. current_company: Where the user is currently working (name of the company)
2. job_role: The user's job title or role (e.g., DevOps Engineer, Delivery Executive)
3. tech_or_nontech: Whether the user works in a technical or non-technical role
4. monthly_salary: The user's current monthly take-home salary (include amount and currency, if stated)
5. expected_salary: The salary or increment the user is expecting (amount or percentage, include currency if mentioned)
6. notice_period: The duration of the user's notice period before joining a new job
7. experience: Total years of relevant experience stated by the user
8. reconnect_date_time: If the user asks to be contacted later, extract the date/time they mention for reconnecting

Return your result as a valid JSON object in this format:
{{
  "current_company" : {{ "text": ..., "value": ..., "confidence": ... }},
  "job_role": {{ "text": ..., "value": ..., "confidence": ... }},
  "tech_or_nontech": {{ "text": ..., "value": ..., "confidence": ... }},
  "monthly_salary": {{ "text": ..., "value": ..., "confidence": ... }},
  "expected_salary": {{ "text": ..., "value": ..., "confidence": ... }},
  "notice_period": {{ "text": ..., "value": ..., "confidence": ... }},
  "experience": {{ "text": ..., "value": ..., "confidence": ... }},
  "reconnect_date_time": {{ "text": ..., "value": ..., "confidence": ... }}
}}

For each field:
- "text" is the exact text from the USER's speech that contains the information
- "value" is the clean, structured extraction (e.g., "2.5 lakhs", "DevOps Engineer", "Technical", etc.)
- "confidence" should be "high", "medium", or "low" depending on how clearly the user stated the information

Important rules:
- Only extract what the USER says explicitly. Do not infer from questions.
- If something is not mentioned by the user, set:
  {{"text": "NA", "value": "Not mentioned", "confidence": "NA"}}
- If the user mentions both percentage and amount for salary, include both in the "value"
- Do not return any explanation or commentary. Only the JSON object.

Transcript:
{transcript}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {
                    "role": "system",
                    "content": "You are a specialized entity extraction system that focuses on job-related lifestyle and earnings information from user responses in conversations. Extract only what the user explicitly states."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.2,
            # response_format="json"
        )

        content = response.choices[0].message.content
        # Remove markdown ```json ... ``` wrapping if present
        if content.startswith("```json"):
            content = content[7:]  # Remove ```json\n
        if content.endswith("```"):
            content = content[:-3]  # Remove trailing ```

        content = content.strip()
        return json.loads(content)
        # result = json.loads(llm_output)
        # return {"result": result}

    except Exception as e:
        return {
            "error": f"Entity extraction failed: {str(e)}",
            "result": {
                "current_company" : { "text": "NA", "value": "Not Mentioned", "confidence": "NA" },
                "job_role": { "text": "NA", "value": "Not Mentioned", "confidence": "NA" },
                "tech_or_nontech": { "text": "NA", "value": "Not Mentioned", "confidence": "NA" },
                "monthly_salary": { "text": "NA", "value": "Not Mentioned", "confidence": "NA" },
                "expected_salary": { "text": "NA", "value": "Not Mentioned", "confidence": "NA" },
                "notice_period": { "text": "NA", "value": "Not Mentioned", "confidence": "NA" },
                "experience": { "text": "NA", "value": "Not Mentioned", "confidence": "NA" },
                "reconnect_date_time": { "text": "NA", "value": "Not Mentioned", "confidence": "NA" }
            }
        }


# def extract_lead_classification_azent(transcript: str, fields: list[tuple[str, str]] = None) -> dict:
#     """
#     Extracts lead classification and educational details from a conversation transcript,
#     focusing exclusively on the USER's responses.
#     """
    
#     load_dotenv("/app/.env.local")
#     api_key = os.getenv("OPENAI_API_KEY")
    
#     if not api_key:
#         raise ValueError("OPENAI_API_KEY not found in environment variables")

#     client = OpenAI(api_key=api_key)
    
    
    
#     # Get the prompt using the separate function
#     prompt = get_lead_classification_prompt(transcript, current_date_str, current_year, next_year)

#     try:
#         response = client.chat.completions.create(
#             # model="gpt-3.5-turbo-0125",
#             model="gpt-4o",
#             messages=[
#                 {
#                     "role": "system",
#                     "content": "You are a specialized lead qualification system that extracts educational consultation information from user responses in conversations. Extract only what the user explicitly states and classify leads based on specific criteria."
#                 },
#                 {
#                     "role": "user",
#                     "content": prompt
#                 }
#             ],
#             temperature=0.1,
#             # response_format="json"
#         )

#         content = response.choices[0].message.content
#         # Remove markdown ```json ... ``` wrapping if present
#         if content.startswith("```json"):
#             content = content[7:]  # Remove ```json\n
#         if content.endswith("```"):
#             content = content[:-3]  # Remove trailing ```

#         content = content.strip()
#         return json.loads(content)

#     except Exception as e:
#         return {
#             "error": f"Lead classification failed: {str(e)}",
#             "result": {
#                 "Lead_Strength": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 # "Reason": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Intent_Level": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Current_City": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Target_Country": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Primary_Country": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Target_Intake_Year": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Target_Intake_Month": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Target_Degree": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Current_Degree": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Score_Percentage": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Backlogs_Count": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Year_Of_Completion": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "12th_English_Percentage": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Education_Gap": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Work_Experience": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Years_Of_Experience": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Work_Sector": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Test_Status": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Test_Name": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Test_Date": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Test_Scores": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Tuition_Budget": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Visa_Refusal": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Visa_Refusal_Country": { "text": "NA", "value": "Not mentioned", "confidence": "NA" },
#                 "Visa_Refusal_Reason": { "text": "NA", "value": "Not mentioned", "confidence": "NA" }
#             }
#         }

if __name__ == "__main__":
    # Example usage
    transcript = """
Agent: "नमस्ते, मै सागर बोल रहा हु ऍझन्ट ओवरसीज एज्युकेशन से. क्या मेरी बात bhudev जी से हो रही है ?"
User: हां हां हां बताइए.
Agent: धन्यवाद भूदेव जी! मैं आपसे इसलिए बात कर रहा हूं क्योंकि आपने विदेश में पढ़ाई के लिए इंटरेस्ट दिखाया था। क्या अभी बात करने का सही समय है?
User: क्या क्या आपको कैसे पता चला?
Agent: भूदेव जी, आपने या तो हमारी वेबसाइट पर फॉर्म भरा होगा या किसी इवेंट में हिस्सा लिया होगा, जहां आपने विदेश में पढ़ाई के लिए इंटरेस्ट दिखाया था। इसलिए मैं आपसे डिटेल्स जानने के लिए कॉल कर रहा हूं ताकि हम आपकी मदद कर सकें। क्या अभी बात करने का सही समय है?
User: आप कितना पैसा लेंगे फिर अगर आप मदद करने का?
Agent: भूदेव जी, हमारी कंसल्टेशन सर्विस पूरी तरह से फ्री है। हम आपको सही यूनिवर्सिटी चुनने, एडमिशन प्रोसेस और बाकी गाइडेंस में मदद करते हैं। बस आपसे कुछ डिटेल्स चाहिए ताकि हम आपकी सही तरीके से मदद कर सकें। क्या मैं आगे बढ़ सकता हूं?
User: अच्छा.
User: है
User: बताइए.
Agent: बहुत
Agent: बहुत बढ़िया भूदेव जी! तो सबसे पहले ये बताइए कि आप किस देश में पढ़ाई के लिए जाना चाहते हैं? हमारे पास USA, UK, Australia और Canada के लिए ही गाइडेंस उपलब्ध है।
User: हां हां. तो UK जाना चाहता हूं मैं UK या USA दोनों चलेगा मुझको.
Agent: बहुत बढ़िया भूदेव जी! तो UK और USA दोनों के लिए हम आपकी मदद कर सकते हैं। अब मुझे ये बताइए कि आपकी अभी तक की पढ़ाई में आपका GPA या Percentage कितना है?
User: मेरा GB 9.72 है.
Agent: वाह!9.72 GPA तो बहुत ही शानदार है, भूदेव जी। अब ये बताइए कि आप कौन सी डिग्री के लिए अप्लाई करना चाहते हैं? जैसे Masters, UG/PG Diploma, या 3/4-Year Bachelor?
User: मैं मुझे army में जाना है actually.
Agent: भूदेव जी, मैं समझता हूं कि आप आर्मी में जाने की सोच रहे हैं, लेकिन हमारी सर्विस सिर्फ विदेश में पढ़ाई के लिए गाइडेंस देने तक सीमित है। अगर आप विदेश में पढ़ाई के ज़रिए अपने करियर को आगे बढ़ाना चाहते हैं, तो मैं आपकी पूरी मदद कर सकता हूं। क्या आप फिर भी विदेश में पढ़ाई के बारे में बात करना चाहेंगे?
User: ठीक है तो मुझे मुझे यह bachelor करना है economics में.
Agent: बहुत बढ़िया भूदेव जी! तो आप Economics में Bachelor करना चाहते हैं। अब मुझे ये बताइए कि आपने अभी तक कौन सी डिग्री पूरी की है? मतलब 12th के बाद आपने क्या पढ़ाई की है?
User: Twelfth के बाद मेरा bachelors है arts में
Agent: समझ गया भूदेव जी, आपने 12th के बाद Arts में Bachelor किया है। क्या आपकी इस डिग्री में कोई बैकलॉग (Backlogs) रहे हैं?
User: हां हां मेरी बात उसमें मेरी तीन तीन back lock थे पर अभी सब clear
Agent: ठीक है भूदेव जी, तीन बैकलॉग थे लेकिन अब सब क्लियर हो गए हैं। ये जानना ज़रूरी था। अब मुझे ये बताइए कि क्या आपकी पढ़ाई के बीच में, मतलब 12th के बाद, कोई Education Gap रहा है?
User: नहीं नहीं. Education gap नहीं था बस दो साल का gap था.
Agent: समझ गया भूदेव जी, तो दो साल का gap था। कोई बात नहीं, ये भी manage किया जा सकता है। अब आखिरी सवाल, आप किस intake के लिए target कर रहे हैं? मतलब किस महीने और साल में आप अपनी पढ़ाई शुरू करना चाहते हैं? ध्यान दें कि ये तारीख बारह महीने के अंदर होनी चाहिए।
User: हां मुझे आप जनवरी दो हज़ार पच्चीस में दे दीजिए.
Agent: भूदेव जी, जनवरी दो हज़ार पच्चीस का intake तो अब निकल चुका है क्योंकि आज की तारीख है मंगलवार, सत्ताईस मई, दो हज़ार पच्चीस। आप चाहें तो सितंबर दो हज़ार पच्चीस या जनवरी दो हज़ार छब्बीस के लिए target कर सकते हैं। कौन सा intake आपके लिए सही रहेगा?
User: मुझे दोनों ही चलेगा सितंबर भी चलेगा जनवरी भी चलेगा.
Agent: ठीक है भूदेव जी, तो मैं आपके लिए सितंबर दो हज़ार पच्चीस और जनवरी दो हज़ार छब्बीस दोनों के options पर काम करूंगा। अब आपके प्रोफाइल के हिसाब से मैं आगे की प्रोसेस शुरू कर सकता हूं। अगर आपके पास कोई और सवाल हो तो आप मुझसे पूछ सकते हैं!
User: Ok
Agent: बहुत बढ़िया भूदेव जी!
User: नहीं नहीं कोई problem नहीं है.
Agent: ठीक है भूदेव जी, अगर कोई और सवाल हो तो बेझिझक पूछिए। मैं आपकी पूरी मदद करूंगा। धन्यवाद, और आपका दिन शुभ हो!
User: जी नहीं नहीं all good thank you.
"""

    import asyncio
    result = asyncio.run(call_summary(transcript))
    print(json.dumps(result, indent=2))

