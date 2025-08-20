"""
AI Response Handler for Job Application Bot

This module handles all AI-related responses for form filling in job applications.
It contains methods to interact with OpenAI API and generate appropriate responses
for different types of form fields and sections.

Author: Automated Job Application System
Version: 2.0
"""

import json
from typing import Dict, List, Any, Tuple
import openai


class AIResponseHandler:
    """Class to handle all AI responses for job application form filling"""
    
    def __init__(self, openai_client: openai.AsyncOpenAI):
        """Initialize the AI response handler
        
        Args:
            openai_client: Initialized OpenAI async client
        """
        self.client = openai_client
    
    async def get_ai_response_without_skipping(self, current_data: Dict[str, Any], panel_elements: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Get AI response for form fields using OpenAI without skipping any fields"""
        try:
            form_fields = []
            key_mapping = {}

            for el in panel_elements:
                full_key = f"[{el['question']}, {el['input_id']}, {el['input_type']}, {el['aria_labelledby']}, {el['input_tag']}]"
                
                form_fields.append({
                    "full_key": full_key,
                    "question": el['question'],
                    "input_id": el['input_id'],
                    "input_type": el['input_type'],
                    "input_tag": el['input_tag'],
                    "aria_labelledby": el['aria_labelledby'],
                    "options": el['options'], 
                    "placeholder": el.get('placeholder'),
                    "required": el.get('required'),
                    "role": el.get('role')
                })
                
                key_mapping[full_key] = el

            prompt = f"""
You are helping fill a job application form.
You are mapping user profile data to a web job application form.

You are given:
- An Entry from user profile data (JSON)
- A list of form fields from the application panel (including labels, field types, and available options if there is dropdown for the element)

Return a JSON dictionary mapping the EXACT "full_key" values to appropriate values. Use the user data to fill the values. 
do not SKIP any field in the my information section, fill up the most accurate response you can come up with based on user profile

CRITICAL: You MUST use the EXACT "full_key" value as the key in your response JSON. Do NOT use just the question text.

IMPORTANT RULES:
- Donot skip the elements give the best possible answer, if the question is ambgious or not in user profile data then give an answer that yields highest probability of the application passing. Especially for listboxes, textfields and radio/checkboxes in the application,voluntary disclosures section
- For radio_group fields:
  - You MUST select ONLY necessary options from the provided options list
  - Choose the option that best matches the user's profile. If the question is have you worked at the company before, the answer is no so respond accoringly based on question and radio option
  - Use EXACT text from the options list (case-sensitive)
- For questions regarding "when are you available to start". Take the respective date-related field from '10-Day 09-month 2025-year'and give DD or MM or YYYY based on the input_id and question
- For date-related fields (e.g. type="spinbutton" or input_id includes "Month" or "Year"):
  - Use "MM" format for months (e.g., "01" for January)
  - Use "YYYY" format for years (e.g., "2022")
  - Use "DD" format for days (e.g., "01" for the first day of the month)
- For salary fields, just print a single number as expectation
- For the country phone code under multiinputcontainer(as a button). Output the country name not the phone code as it fills automatically.
- For fields with "options" not None:
  - You MUST select ONLY from the list of provided OPTIONS (case-sensitive)
  - If the user data is longer (e.g., "Bachelor of Engineering in Computer Science") and options are shorter (e.g., "BS"), choose the CLOSEST MATCH based on meaning
- For text fields: Keep responses concise and relevant
- Match options exactly as they appear in the options list (case-sensitive) when options is not None
- After filling the form, if a field for save and continue is present, respond with yes to save the form

SPECIAL HANDLING FOR SKILLS/MULTI-VALUE FIELDS:
- For fields related to skills, technologies, competencies, or any field that should contain multiple items:
  - Return an ARRAY of strings instead of a single comma-separated string
  - Each skill/technology should be a separate string in the array
  - Example: ["C#", "TypeScript", "Java", "SQL", "HTML5", "CSS3", "Python"] instead of "C#, TypeScript, Java, SQL, HTML5, CSS3, Python"
- Identify skills fields by keywords in the question like: "skills", "technologies", "competencies", "tools", "programming languages", etc.

Data from User Profile:
{json.dumps(current_data, indent=2)}

Form Fields:
{json.dumps(form_fields, indent=2)}

Example response format:
{{
  "[School or University*, unknown, text, Education-(Optional)-2-panel, input]": "University Name",
  "[Degree*, unknown, button, Education-(Optional)-2-panel, button]": "MS",
  "[Field of Study, unknown, unknown, Education-(Optional)-2-panel, input]": "Computer Science",
  "[Type to Add Skills, unknown, unknown, Skills-section, input]": ["C#", "TypeScript", "Java", "SQL", "HTML5", "CSS3", "Python", ".NET Core", "Angular 2+", "RxJS", "Entity Framework", "React", "Redux", "Bootstrap 4"]
}}

Respond ONLY with a valid JSON object using the exact "full_key" values as keys.
"""
            
            response = await self.client.chat.completions.create(
                model="o4-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.choices[0].message.content.strip()
            
            # Clean up the response to extract JSON
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            ai_response = json.loads(content)
            return ai_response, key_mapping
            
        except Exception as e:
            print(f"Error in get_ai_response_without_skipping: {e}")
            return {}, {}

    async def get_ai_response_for_personal_information(self, current_data: Dict[str, Any], panel_elements: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Get AI response for personal information form fields using OpenAI"""
        try:
            form_fields = []
            key_mapping = {}

            for el in panel_elements:
                full_key = f"[{el['question']}, {el['input_id']}, {el['input_type']}, {el['aria_labelledby']}, {el['input_tag']}]"
                
                form_fields.append({
                    "full_key": full_key,
                    "question": el['question'],
                    "input_id": el['input_id'],
                    "input_type": el['input_type'],
                    "input_tag": el['input_tag'],
                    "aria_labelledby": el['aria_labelledby'],
                    "options": el['options'], 
                    "placeholder": el.get('placeholder'),
                    "required": el.get('required'),
                    "role": el.get('role')
                })
                
                key_mapping[full_key] = el

            prompt = f"""
You are helping fill a job application form.
You are mapping user profile data to a web job application form.

You are given:
- An Entry from user profile data (JSON)
- A list of form fields from the application panel (including labels, field types, and available options if there is dropdown for the element)

Return a JSON dictionary mapping the EXACT "full_key" values to appropriate values. Use the user data to fill the values. 
do not SKIP any field in the my information section, fill up the most accurate response you can come up with based on user profile

CRITICAL: You MUST use the EXACT "full_key" value as the key in your response JSON. Do NOT use just the question text.

IMPORTANT RULES:
- For radio_group fields:
  - You MUST select ONLY necessary options from the provided options list
  - Choose the option that best matches the user's profile. If the question is have you worked at the company before, the answer should be 'no' so respond accoringly based on question and radio option
  - Use EXACT text from the options list (case-sensitive)
- For the country phone code under multiinputcontainer(as a button). Output the country name not the phone code as it fills automatically.
- For fields with "options" not None:
  - You MUST select ONLY from the list of provided OPTIONS (case-sensitive)
  - If the user data is longer (e.g., "Bachelor of Engineering in Computer Science") and options are shorter (e.g., "BS"), choose the CLOSEST MATCH based on meaning
- For text fields: Keep responses concise and relevant
- Match options exactly as they appear in the options list (case-sensitive) when options is not None
- After filling the form, if a field for save and continue is present, respond with yes to save the form

SPECIAL HANDLING FOR SKILLS/MULTI-VALUE FIELDS:
- For fields related to skills, technologies, competencies, or any field that should contain multiple items:
  - Return an ARRAY of strings instead of a single comma-separated string
  - Each skill/technology should be a separate string in the array
  - Example: ["C#", "TypeScript", "Java", "SQL", "HTML5", "CSS3", "Python"] instead of "C#, TypeScript, Java, SQL, HTML5, CSS3, Python"
- Identify skills fields by keywords in the question like: "skills", "technologies", "competencies", "tools", "programming languages", etc.

Data from User Profile:
{json.dumps(current_data, indent=2)}

Form Fields:
{json.dumps(form_fields, indent=2)}

Example response format:
{{
  "[School or University*, unknown, text, Education-(Optional)-2-panel, input]": "University Name",
  "[Degree*, unknown, button, Education-(Optional)-2-panel, button]": "MS",
  "[Field of Study, unknown, unknown, Education-(Optional)-2-panel, input]": "Computer Science",
  "[Type to Add Skills, unknown, unknown, Skills-section, input]": ["C#", "TypeScript", "Java", "SQL", "HTML5", "CSS3", "Python", ".NET Core", "Angular 2+", "RxJS", "Entity Framework", "React", "Redux", "Bootstrap 4"]
}}

Respond ONLY with a valid JSON object using the exact "full_key" values as keys.
"""
            
            response = await self.client.chat.completions.create(
                model="o4-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.choices[0].message.content.strip()
            
            # Clean up the response to extract JSON
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            ai_response = json.loads(content)
            return ai_response, key_mapping
            
        except Exception as e:
            print(f"Error in get_ai_response_for_personal_information: {e}")
            return {}, {}

    async def get_ai_response_for_section(self, current_data: Dict[str, Any], panel_elements: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Get AI response for general form section fields using OpenAI"""
        try:
            form_fields = []
            key_mapping = {}

            for el in panel_elements:
                full_key = f"[{el['question']}, {el['input_id']}, {el['input_type']}, {el['aria_labelledby']}, {el['input_tag']}]"
                
                form_fields.append({
                    "full_key": full_key,
                    "question": el['question'],
                    "input_id": el['input_id'],
                    "input_type": el['input_type'],
                    "input_tag": el['input_tag'],
                    "aria_labelledby": el['aria_labelledby'],
                    "options": el['options'], 
                    "placeholder": el.get('placeholder'),
                    "required": el.get('required'),
                    "role": el.get('role')
                })
                
                key_mapping[full_key] = el

            prompt = f"""
You are helping fill a job application form.
You are mapping user profile data to a web form.

You are given:
- An Entry from user profile data (JSON)
- A list of form fields from the application panel (including labels, field types, and available options if there is dropdown for the element)

Return a JSON dictionary mapping the EXACT "full_key" values to appropriate values. Use the user data to fill the values. If a field is not relevant, map it to "SKIP".

CRITICAL: You MUST use the EXACT "full_key" value as the key in your response JSON. Do NOT use just the question text.

IMPORTANT RULES:
- For language fields asking fluency, use the closest match from the options list even if its not mentioned and make sure to fill all the listboxes about language fluency based on multiple metrics.
- Note that fill all the listboxes about langauge fluency that are present in the form.
- For fields with "options" not None:
  - You MUST select ONLY from the list of provided OPTIONS (case-sensitive)
  - If the user data is longer (e.g., "Bachelor of Engineering in Computer Science") and options are shorter (e.g., "BS"), choose the CLOSEST MATCH based on meaning
  - If no match is appropriate, use "SKIP"
- For radio_group fields:
  - You MUST select ONLY necessary options from the provided options list
  - Choose the option that best matches the user's profile or a reasonable default
  - Use EXACT text from the options list (case-sensitive)
- For date fields: Month should be number format (e.g., "01" for January), year should be "YYYY" format
- For date-related fields (e.g. type="spinbutton" or input_id includes "Month" or "Year"):
  - Use "MM" format for months (e.g., "01" for January)
  - Use "YYYY" format for years (e.g., "2022")
  - Match "start date", "end date", "graduation date", etc., with the corresponding data from user profile
- Make sure not to skip voluntary disclosure questions about gender, ethnicity, disability, and veteran status and other similar questions
- For text fields: Keep responses concise and relevant
- Match options exactly as they appear in the options list (case-sensitive) when options is not None
- After filling the form, if a field for save and continue is present, respond with yes to save the form

SPECIAL HANDLING FOR SKILLS/MULTI-VALUE FIELDS:
- For fields related to skills, technologies, competencies, or any field that should contain multiple items:
  - Return an ARRAY of strings instead of a single comma-separated string
  - Each skill/technology should be a separate string in the array
  - Example: ["C#", "TypeScript", "Java", "SQL", "HTML5", "CSS3", "Python"] instead of "C#, TypeScript, Java, SQL, HTML5, CSS3, Python"
- Identify skills fields by keywords in the question like: "skills", "technologies", "competencies", "tools", "programming languages", etc.

Data from User Profile:
{json.dumps(current_data, indent=2)}

Form Fields:
{json.dumps(form_fields, indent=2)}

Example response format:
{{
  "[School or University*, unknown, text, Education-(Optional)-2-panel, input]": "University Name",
  "[Degree*, unknown, button, Education-(Optional)-2-panel, button]": "MS",
  "[Field of Study, unknown, unknown, Education-(Optional)-2-panel, input]": "Computer Science",
  "[Type to Add Skills, unknown, unknown, Skills-section, input]": ["C#", "TypeScript", "Java", "SQL", "HTML5", "CSS3", "Python", ".NET Core", "Angular 2+", "RxJS", "Entity Framework", "React", "Redux", "Bootstrap 4"]
}}

Respond ONLY with a valid JSON object using the exact "full_key" values as keys.
"""
            
            response = await self.client.chat.completions.create(
                model="o4-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.choices[0].message.content.strip()
            
            # Clean up the response to extract JSON
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            ai_response = json.loads(content)
            return ai_response, key_mapping
            
        except Exception as e:
            print(f"Error in get_ai_response_for_section: {e}")
            return {}, {}
