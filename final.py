"""
Job Application Automation System

A comprehensive, modular system for automating job applications on Workday-based platforms.
This system handles authentication, form filling, and various application sections including
personal information, work experience, education, skills, and voluntary disclosures.

Author: Automated Job Application System
Version: 2.0
"""

import asyncio
import json
import os
import random
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from datetime import date
from pathlib import Path

import openai
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from dotenv import load_dotenv


class JobApplicationBot:
    """Main class for job application automation"""
    
    def __init__(self, config_path: str = "data/user_profile.json"):
        """Initialize the job application bot
        
        Args:
            config_path: Path to user profile configuration file
        """
        load_dotenv()
        self.config_path = config_path
        self.user_data = self._load_user_profile()
        self.client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # Application URLs for different companies
        self.company_urls = {
            "nvidia": "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/US%2C-CA%2C-Santa-Clara/Senior-AI-and-ML-Engineer---AI-for-Networking_JR2000376/apply/applyManually?q=ml+enginer",
            "salesforce": "https://salesforce.wd12.myworkdayjobs.com/en-US/External_Career_Site/job/Singapore---Singapore/Senior-Manager--Solution-Engineering--Philippines-_JR301876/apply/applyManually",
            "hitachi": "https://hitachi.wd1.myworkdayjobs.com/en-US/hitachi/job/Alamo%2C-Tennessee%2C-United-States-of-America/Project-Engineer_R0102918/apply/applyManually",
            "icf": "https://icf.wd5.myworkdayjobs.com/en-US/ICFExternal_Career_Site/job/Reston%2C-VA/Senior-Paid-Search-Manager_R2502057/apply/applyManually",
            "harris": "https://harriscomputer.wd3.myworkdayjobs.com/en-US/1/job/Florida%2C-United-States/Vice-President-of-Sales_R0030918/apply/applyManually"
        }
        
        # Logging setup
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)
        self.current_run_dir = self.logs_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.current_run_dir.mkdir(exist_ok=True)
        
        # Track the previous question and whether it was a listbox
        self.previous_question = None
        self.previous_was_listbox = False
        
        # Data collection for final JSON output
        self.application_data = []

    def _load_user_profile(self) -> Dict[str, Any]:
        """Load user profile data from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"User profile file not found: {self.config_path}")
            return {}
        except json.JSONDecodeError:
            print(f"Invalid JSON in user profile file: {self.config_path}")
            return {}

    def reset_duplicate_tracking(self) -> None:
        """Reset the duplicate question tracking for new applications"""
        self.previous_question = None
        self.previous_was_listbox = False
        print("Reset duplicate question tracking")

    async def initialize_browser(self, headless: bool = False, slow_mo: int = 100) -> None:
        """Initialize browser and page"""
        playwright_instance = await async_playwright().start()
        self.browser = await playwright_instance.chromium.launch(
            headless=headless,
            slow_mo=slow_mo,
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 720}
        )
        self.page = await self.context.new_page()

    async def navigate_to_job(self, company: str = "harris") -> None:
        """Navigate to job application page"""
        if company not in self.company_urls:
            raise ValueError(f"Company '{company}' not supported. Available: {list(self.company_urls.keys())}")
        
        url = self.company_urls[company]
        await self.page.goto(url, wait_until='networkidle', timeout=30000)
        print(f"Navigated to {company} job application page")

    async def handle_authentication(self, auth_type: int = 1) -> bool:
        """Handle authentication (sign in or sign up)
        
        Args:
            auth_type: 1 for sign in, 2 for sign up
        """
        if auth_type == 2:
            return await self._handle_signup()
        else:
            return await self._handle_signin()

    async def _handle_signup(self) -> bool:
        """Handle user sign up process"""
        try:
            personal_info = self.user_data.get('personal_information', {})
            email = personal_info.get('email', '')
            password = personal_info.get('password', '')

            # Fill email
            email_input = await self.page.query_selector('input[data-automation-id="email"]')
            if email_input:
                await email_input.fill(email)
                print(f"Filled email: {email}")

            # Fill password
            password_input = await self.page.query_selector('input[data-automation-id="password"]')
            if password_input:
                await password_input.fill(password)
                print("Filled password")

            # Fill verify password
            verify_password_input = await self.page.query_selector('input[data-automation-id="verifyPassword"]')
            if verify_password_input:
                await verify_password_input.fill(password)
                print("Filled verify password")

            # Check the create account checkbox
            checkbox = await self.page.query_selector('input[data-automation-id="createAccountCheckbox"]')
            if checkbox:
                checked = await checkbox.is_checked()
                if not checked:
                    await checkbox.check()
                print("Checked create account checkbox")

            # Click submit button
            await asyncio.sleep(1)
            submit_btn = await self.page.query_selector('div[aria-label="Create Account"]')
            if submit_btn:
                await submit_btn.click()
                print("Clicked create account submit button")
                return True

        except Exception as e:
            print(f"Error during signup: {e}")
            return False

    async def _handle_signin(self) -> bool:
        """Handle user sign in process"""
        try:
            # Click sign in link
            sign_in_link = await self.page.query_selector('button[data-automation-id="signInLink"]')
            if sign_in_link:
                await sign_in_link.click()
                print("Clicked sign in link")

            personal_info = self.user_data.get('personal_information', {})
            email = personal_info.get('email', '')
            password = personal_info.get('password', '')

            # Fill email
            email_input = await self.page.query_selector('input[data-automation-id="email"]')
            if email_input:
                await email_input.fill(email)
                print(f"Filled email: {email}")

            # Fill password
            password_input = await self.page.query_selector('input[data-automation-id="password"]')
            if password_input:
                await password_input.fill(password)
                print("Filled password")

            # Click submit button
            await asyncio.sleep(1)
            submit_btn = await self.page.query_selector('div[aria-label="Sign In"]')
            if submit_btn:
                await submit_btn.click()
                print("Clicked sign in submit button")
                return True

        except Exception as e:
            print(f"Error during signin: {e}")
            return False

    async def _get_radio_group(self, main_page, inputs, current_index, current_radio) -> Optional[List[int]]:
        """Get all radio button indices that belong to the same group"""
        try:
            # Get the name attribute of the current radio button
            current_name = await current_radio.get_attribute('name')
            if not current_name:
                return None
            
            # Get the group label/question for this radio group
            group_question = await self._get_radio_group_question(current_radio)
            
            radio_indices = []
            
            # Find all radio buttons with the same name attribute
            for i, input_el in enumerate(inputs):
                input_type = await input_el.get_attribute('type')
                if input_type == 'radio':
                    radio_name = await input_el.get_attribute('name')
                    if radio_name == current_name:
                        radio_indices.append(i)
            
            print(f"Radio group '{group_question}' has {len(radio_indices)} options at indices: {radio_indices}")
            return radio_indices if len(radio_indices) > 1 else None
            
        except Exception as e:
            print(f"Error getting radio group: {e}")
            return None

    async def _process_radio_button(self, radio_index: int) -> None:
        """Process a single radio button by its index"""
        try:
            # Re-get the inputs to ensure fresh DOM state
            main_page = await self.page.query_selector('div[data-automation-id="applyFlowPage"]')
            inputs = await main_page.query_selector_all('button, input, select, textarea, [role="button"]')
            
            if radio_index >= len(inputs):
                print(f"Radio index {radio_index} is out of bounds")
                return
            
            radio_el = inputs[radio_index]
            
            # Get radio button information
            input_id = await radio_el.get_attribute('data-automation-id') or 'unknown'
            input_type = await radio_el.get_attribute('type')
            
            if input_type != 'radio':
                print(f"Element at index {radio_index} is not a radio button")
                return
            
            # Get the radio group question and this specific option
            group_question = await self._get_radio_group_question(radio_el)
            option_label = await self._get_nearest_label_text(radio_el) or 'Unknown Option'
            
            print(f"Processing radio option: '{option_label}' for question: '{group_question}'")
            
            # Create element info for AI processing
            element_info = {
                'question': group_question,
                'option_label': option_label,
                'input_type': 'radio',
                'input_tag': 'input',
                'input_id': input_id,
                'options': None,
                'placeholder': None,
                'required': await radio_el.get_attribute('required'),
                'role': await radio_el.get_attribute('role')
            }
            
            # Get AI response for this radio option
            full_key = f"[{group_question}, {input_id}, radio, {option_label}]"
            
            # Create a simplified structure for AI
            radio_group_info = {
                'question': group_question,
                'options': [option_label],  # This represents the current option
                'input_type': 'radio_group',
                'input_id': f"radio_group_{input_id}"
            }
            
            ai_values, _ = await self._get_ai_response_without_skipping(
                self.user_data.get('personal_information', {}), 
                [element_info]
            )
            
            # Check if AI wants to select this radio button
            response = ai_values.get(full_key, 'SKIP')
            
            if response and response != 'SKIP':
                # Check if the response matches this option or indicates selection
                should_select = (
                    response.lower() in option_label.lower() or 
                    option_label.lower() in response.lower() or
                    response in ['yes', 'true', '1', True, 1]
                )
                
                if should_select:
                    await radio_el.check()
                    print(f"✅ Selected radio option: '{option_label}' for question: '{group_question}'")
                else:
                    print(f"⏭️ Skipping radio option: '{option_label}' (AI response: {response})")
            else:
                print(f"⏭️ Skipping radio option: '{option_label}' (AI said SKIP)")
                
        except Exception as e:
            print(f"Error processing radio button at index {radio_index}: {e}")

    async def _process_radio_group_as_whole(self, main_page, inputs, radio_indices: List[int]) -> None:
        """Process an entire radio group as a single unit for AI decision"""
        try:
            if not radio_indices:
                return
            
            # Get the first radio to determine the group question
            first_radio = inputs[radio_indices[0]]
            group_question = await self._get_radio_group_question(first_radio)
            
            # Get aria_labelledby from the first radio element
            group_label, aria_labelledby = await self._get_group_label_and_aria(first_radio)
            
            # Collect all options in this group
            options = []
            radio_elements = []
            
            for radio_index in radio_indices:
                radio_el = inputs[radio_index]
                option_label = await self._get_nearest_label_text(radio_el) or f'Option {len(options) + 1}'
                options.append(option_label)
                radio_elements.append(radio_el)
            
            print(f"Processing radio group: '{group_question}' with options: {options}")
            
            # Create element info for AI processing
            element_info = {
                'question': group_question,
                'input_type': 'radio_group',
                'input_tag': 'radio_group',
                'input_id': f"radio_group_{await first_radio.get_attribute('name')}",
                'aria_labelledby': aria_labelledby,  # Add this field
                'options': options,
                'placeholder': None,
                'required': await first_radio.get_attribute('required'),
                'role': 'radiogroup'
            }
            
            # Get AI response for the entire radio group
            full_key = f"[{group_question}, {element_info['input_id']}, radio_group, {aria_labelledby}, radio_group]"
            
            ai_values, _ = await self._get_ai_response_without_skipping(
                self.user_data.get('personal_information', {}), 
                [element_info]
            )
            
            response = ai_values.get(full_key, 'SKIP')
            
            if response and response != 'SKIP':
                # Find the best matching option
                selected_index = -1
                
                # Try exact match first
                for i, option in enumerate(options):
                    if option.lower().strip() == response.lower().strip():
                        selected_index = i
                        break
                
                # Try partial match if no exact match
                if selected_index == -1:
                    for i, option in enumerate(options):
                        if response.lower() in option.lower() or option.lower() in response.lower():
                            selected_index = i
                            break
                
                # Select the radio button
                if selected_index >= 0:
                    selected_radio = radio_elements[selected_index]
                    selected_option = options[selected_index]
                    print(f"Is the option checked {await selected_radio.is_checked()}?")
                    await selected_radio.check()
                    print(f"✅ Selected radio option: '{selected_option}' for question: '{group_question}'")
                else:
                    print(f" Could not find matching option for AI response: '{response}' in {options}")
            else:
                print(f"⏭ Skipping radio group: '{group_question}' (AI said SKIP)")
                
        except Exception as e:
            print(f"Error processing radio group: {e}")

    async def _process_personal_information_section(self, section) -> None:
        """Process personal information section with radio/checkbox group handling"""
        print("Processing Personal Information section")
        
        await asyncio.sleep(5)  # Wait for page to load
        
        main_page = await self.page.query_selector('div[data-automation-id="applyFlowPage"]')
        INPUT_SELECTOR = 'button, input, select, textarea, [role="button"]'
        
        i = 0
        prev_answered_question = None
    
        while True:
            # Re-extract elements on each iteration (fresh DOM state)
            inputs = await main_page.query_selector_all(INPUT_SELECTOR)
            
            if i >= len(inputs):
                print("Reached end of inputs, exiting loop")
                break
                
            input_el = inputs[i]
            
            # Get element information
            input_id = await input_el.get_attribute('data-automation-id') or await input_el.get_attribute('aria-haspopup') or 'unknown'
            input_type = await input_el.get_attribute('type') or 'unknown'
            
            # Skip navigation buttons
            if input_id in ["pageFooterBackButton", "backToJobPosting"]:
                i += 1
                continue
            
            # Handle Next button
            if input_id == "pageFooterNextButton":
                print("Clicking Next button")
                await input_el.click()
                break
            
            # # Handle radio and checkbox groups
            # if input_type in ['radio', 'checkbox']:
            #     new_index, processed = await self._handle_radio_checkbox_group(main_page, inputs, i, input_el)
            #     if processed:
            #         i = new_index
            #         continue
            
            # Process other elements normally
            group_label, aria_labelledby = await self._get_group_label_and_aria(input_el)
            question = await self._get_nearest_label_text(input_el) or group_label or 'UNLABELED'
            
            role = await input_el.get_attribute('role')
            placeholder = await input_el.get_attribute('placeholder')
            required = await input_el.get_attribute('required')

            if input_type == "radio":
                # get all radios in this group
                radio_indices = await self._get_radio_group(main_page, inputs, i, input_el)
                num_radios = len(radio_indices) if radio_indices else 0
                if radio_indices:
                    print(f"Found radio group with indices: {radio_indices}")
                    # Process the entire radio group as one unit
                    await self._process_radio_group_as_whole(main_page, inputs, radio_indices)
                    i += num_radios
                    continue

            # Skip duplicate questions
            if question != 'UNLABELED' and question == prev_answered_question:
                print(f"⏩ Skipping duplicate question at index {i}: '{question}'")
                i += 1
                continue
            
            print("--------------------------------")
            print(f"Processing element {i}: Input ID: {input_id}, Question: {question}, Type: {input_type}")
            
            # Process other form elements one by one
            if role == "spinbutton":
                input_type = "spinbutton"
            
            tag_name = await input_el.evaluate("(el) => el.tagName.toLowerCase()")
            if tag_name and tag_name.lower() == 'textarea':
                input_type = 'textarea'
            input_tag = tag_name
            
            # Skip elements with certain directions (like RTL text)
            element_dir = await input_el.get_attribute('dir')
            if element_dir and element_dir != 'ltr':
                print(f"Skipping element {input_id} with dir={element_dir}")
                i += 1
                continue
            
            # Get options for relevant input types
            options = await self._get_element_options(input_el, input_tag, input_type)
            
            print(f"Processing form element: {question}")
            
            # Create element info for AI processing
            element_info = {
                'question': question or 'UNLABELED',
                'aria_labelledby': aria_labelledby,
                'input_type': input_type,
                'input_tag': input_tag,
                'input_id': input_id,
                'options': options,
                'placeholder': placeholder,
                'required': required,
                'role': role
            }
            
            # Get AI response for this single element
            full_key = f"[{element_info['question']}, {element_info['input_id']}, {element_info['input_type']}, {element_info['aria_labelledby']}, {element_info['input_tag']}]"
            ai_values, _ = await self._get_ai_response_for_section_for_personal_information(
                self.user_data.get('personal_information', {}), 
                [element_info]
            )
            response = ai_values.get(full_key, 'SKIP')
            
            print(f"AI response for field '{question}': {response}")
            
            # Fill this single element
            await self._fill_single_element(
                input_el, 
                input_id, 
                input_type, 
                input_tag, 
                response,
                options,
                question
            )
            
            # Update tracking
            if question != 'UNLABELED':
                prev_answered_question = question
            
            # Move to next element
            i += 1
            
            # Small delay to prevent overwhelming the page
            await asyncio.sleep(0.5)

    async def _process_later_sections(self, section) -> None:
        """Process personal information section with radio/checkbox group handling"""
        print("Processing Personal Information section")
        
        await asyncio.sleep(5)  # Wait for page to load
        
        main_page = await self.page.query_selector('div[data-automation-id="applyFlowPage"]')
        INPUT_SELECTOR = 'button, input, select, textarea, [role="button"]'
        
        i = 0
        prev_answered_question = None
        prev_type = None
    
        while True:
            # Re-extract elements on each iteration (fresh DOM state)
            inputs = await main_page.query_selector_all(INPUT_SELECTOR)
            
            if i >= len(inputs):
                print("Reached end of inputs, exiting loop")
                break
                
            input_el = inputs[i]
            
            # Get element information
            input_id = await input_el.get_attribute('data-automation-id') or await input_el.get_attribute('aria-haspopup') or 'unknown'
            input_type = await input_el.get_attribute('type') or 'unknown'
            
            # Skip navigation buttons
            if input_id in ["pageFooterBackButton", "backToJobPosting"]:
                i += 1
                continue
            
            # # Handle Next button
            # if input_id == "pageFooterNextButton":
            #     print("Clicking Next button")
            #     await input_el.click()
            #     break
            
            # Handle Next button
            if input_id == "pageFooterNextButton":
                print("Found Next button")
                break

            # Process other elements normally
            group_label, aria_labelledby = await self._get_group_label_and_aria(input_el)
            question = await self._get_nearest_label_text(input_el) or group_label or 'UNLABELED'
            
            role = await input_el.get_attribute('role')
            placeholder = await input_el.get_attribute('placeholder')
            required = await input_el.get_attribute('required')

            # Handle special case for disability date section
            if "dateSection" in input_id and aria_labelledby == "selfIdentifiedDisabilityData-section":
                formatted_date = date.today().strftime("%d-%m-%Y")
                day, month, year = formatted_date.split('-')
                print(f"Day: {day}, Month: {month}, Year: {year}")
                response = None
                
                if "day" in input_id.lower():
                    input_type = "spinbutton"
                    input_tag = "input"
                    input_id = "selfIdentifiedDisabilityData-day"
                    response = day
                elif "month" in input_id.lower():
                    input_type = "spinbutton"
                    input_tag = "input"
                    input_id = "selfIdentifiedDisabilityData-month"
                    response = month
                elif "year" in input_id.lower():
                    input_type = "spinbutton"
                    input_tag = "input"
                    input_id = "selfIdentifiedDisabilityData-year"
                    response = year
                
                if response:
                    await self._fill_single_element(
                        input_el, 
                        input_id, 
                        input_type,
                        input_tag,
                        response,
                        options=None,
                        question=f"Date field - {input_id}"
                    )
                    print(f"Filled date field {input_id} with: {response}")
                    i += 1
                    continue
            print(f"Previous question: {prev_answered_question}, Current question: {question}, previous type : {prev_type}, current_role : {role}")
            # Skip duplicate questions
            if question != 'UNLABELED' and question == prev_answered_question and role != "spinbutton" and prev_type == "button":
                print(f"⏩ Skipping duplicate question at index {i}: '{question}'")
                i += 1
                continue
            
            print("--------------------------------")
            print(f"Processing element {i}: Input ID: {input_id}, Question: {question}, Type: {input_type}")
            
            # Process other form elements one by one
            if role == "spinbutton":
                input_type = "spinbutton"
            
            tag_name = await input_el.evaluate("(el) => el.tagName.toLowerCase()")
            if tag_name and tag_name.lower() == 'textarea':
                input_type = 'textarea'
            input_tag = tag_name
            
            # Skip elements with certain directions (like RTL text)
            element_dir = await input_el.get_attribute('dir')
            if element_dir and element_dir != 'ltr':
                print(f"Skipping element {input_id} with dir={element_dir}")
                i += 1
                continue
            
            # Get options for relevant input types
            options = await self._get_element_options(input_el, input_tag, input_type)
            
            print(f"Processing form element: {question}")
            
            # Create element info for AI processing
            element_info = {
                'question': question or 'UNLABELED',
                'aria_labelledby': aria_labelledby,
                'input_type': input_type,
                'input_tag': input_tag,
                'input_id': input_id,
                'options': options,
                'placeholder': placeholder,
                'required': required,
                'role': role
            }
            
            # Get AI response for this single element
            full_key = f"[{element_info['question']}, {element_info['input_id']}, {element_info['input_type']}, {element_info['aria_labelledby']}, {element_info['input_tag']}]"
            ai_values, _ = await self._get_ai_response_without_skipping(
                self.user_data.get('personal_information', {}), 
                [element_info]
            )
            response = ai_values.get(full_key, 'SKIP')
            
            print(f"AI response for field '{question}': {response}")
            
            # Fill this single element
            await self._fill_single_element(
                input_el, 
                input_id, 
                input_type, 
                input_tag, 
                response,
                options,
                question
            )
            
            # Update tracking
            if question != 'UNLABELED':
                prev_answered_question = question
                prev_type = input_type
            
            # Move to next element
            i += 1
            
            # Small delay to prevent overwhelming the page
            await asyncio.sleep(0.5)

    async def _process_experience_section(self, section) -> None:
        """Process work experience section with add functionality"""
        print("Processing Work Experience section")
        await self._handle_section_with_add(section, "experience")

    async def _process_education_section(self, section) -> None:
        """Process education section with add functionality"""
        print("Processing Education section")
        await self._handle_section_with_add(section, "education")

    async def _process_language_section(self, section) -> None:
        """Process language section with add functionality"""
        print("Processing Language section")
        await self._handle_section_with_add(section, "language")

    async def _process_skills_section(self, section) -> None:
        """Process skills section"""
        print("Processing Skills section")
        
        # Extract form elements from this section
        form_elements = await self._extract_form_elements_from_section(section)
        
        if not form_elements:
            print("No form elements found in skills section")
            return

        # Get skills data
        skills_data = {
            "technical_skills": self.user_data.get('technical_skills', {}),
            "skills": self.user_data.get('personal_information', {}).get('professional_info', {}).get('skills', [])
        }
        
        # Use AI to map and fill the form
        ai_response, key_mapping = await self._get_ai_response_for_section(skills_data, form_elements)
        
        # Fill the form elements
        await self._fill_form_elements(ai_response, key_mapping)

    async def _select_appropriate_voluntary_disclosure_option(self, options, question_context: str, listbox_num: int):
        """Select appropriate option for voluntary disclosure questions"""
        # Convert options to text for analysis
        option_texts = []
        for option in options:
            text = await option.text_content()
            if text:
                option_texts.append(text.strip())
        
        # Define selection logic based on question context
        question_lower = question_context.lower()
        
        if any(keyword in question_lower for keyword in ["gender", "sex"]):
            # For gender questions, select "Male", "Female", or "Prefer not to disclose"
            for i, option in enumerate(options):
                text = await option.text_content()
                if text and any(gender in text.lower() for gender in ["male", "female", "prefer not"]):
                    return option
        
        elif any(keyword in question_lower for keyword in ["race", "ethnicity", "ethnic"]):
            # For ethnicity questions, select an appropriate option or "Prefer not to disclose"
            for i, option in enumerate(options):
                text = await option.text_content()
                if text and any(eth in text.lower() for eth in ["asian", "white", "prefer not", "decline"]):
                    return option
        
        elif any(keyword in question_lower for keyword in ["veteran", "military"]):
            # For veteran status, select "No" or appropriate option
            for i, option in enumerate(options):
                text = await option.text_content()
                if text and any(vet in text.lower() for vet in ["not a protected veteran", "no", "not applicable"]):
                    return option
        
        elif any(keyword in question_lower for keyword in ["disability", "disabled"]):
            # For disability questions, select "No" or "Prefer not to disclose"
            for i, option in enumerate(options):
                text = await option.text_content()
                if text and any(dis in text.lower() for dis in ["no", "do not have", "prefer not"]):
                    return option
        
        # Default: select first option or "Prefer not to disclose" if available
        for option in options:
            text = await option.text_content()
            if text and "prefer not" in text.lower():
                return option
        
        # If no "prefer not" option, select the first option
        return options[0] if options else None

    async def _get_listbox_question_context(self, listbox) -> str:
        """Get the question context for a listbox"""
        try:
            # Try to find the nearest label or legend
            question = await listbox.evaluate('''
                el => {
                    // Look for aria-labelledby
                    let labelledby = el.getAttribute('aria-labelledby');
                    if (labelledby) {
                        let labelEl = document.getElementById(labelledby);
                        if (labelEl && labelEl.textContent) return labelEl.textContent.trim();
                    }
                    
                    // Look for nearest fieldset legend
                    let fieldset = el.closest('fieldset');
                    if (fieldset) {
                        let legend = fieldset.querySelector('legend');
                        if (legend && legend.textContent) return legend.textContent.trim();
                    }
                    
                    // Look for nearest label
                    let label = el.closest('label');
                    if (label && label.textContent) return label.textContent.trim();
                    
                    // Look for aria-label
                    let ariaLabel = el.getAttribute('aria-label');
                    if (ariaLabel) return ariaLabel;
                    
                    return 'Unknown Question';
                }
            ''')
            return question or "Unknown Question"
        except:
            return "Unknown Question"

    async def _process_resume_section(self, section) -> None:
        """Process resume upload section"""
        print("Processing Resume section")
        
        # Look for file input
        file_input = await section.query_selector('input[type="file"]')
        if file_input:
            resume_path = self.user_data.get('documents', {}).get('resume_path', '')
            if resume_path and os.path.exists(resume_path):
                await file_input.set_input_files([resume_path])
                print(f"Uploaded resume: {resume_path}")
            else:
                print("Resume file not found or not specified")

    async def _process_disability_section(self, section) -> None:
        """Process disability disclosure section"""
        print("Processing Disability section")
        
        log_data = {'checkboxes': [], 'date_fields': []}
        
        # Find checkboxes
        checkboxes = await section.query_selector_all('input[type="checkbox"]')
        
        for i, checkbox in enumerate(checkboxes, 1):
            try:
                label_handle = await checkbox.evaluate_handle('el => el.closest("label")')
                label = label_handle.as_element() if label_handle else None
                label_text = await label.text_content() if label else ''
                
                # Select "do not have a disability" option
                if label_text and "do not have a disability" in label_text.lower():
                    checked = await checkbox.is_checked()
                    if not checked:
                        await checkbox.click()
                        print(f"Selected: {label_text.strip()}")
                    
                    log_data['checkboxes'].append({
                        'checkbox': i, 
                        'label': label_text.strip(), 
                        'checked': True
                    })
                    break
                    
            except Exception as e:
                print(f"Error processing disability checkbox {i}: {e}")
        
        # Fill date fields if present
        current_date = datetime.now()
        date_fields = [
            ("selfIdentifiedDisabilityData--dateSignedOn-dateSectionMonth-input", f"{current_date.month:02d}"),
            ("selfIdentifiedDisabilityData--dateSignedOn-dateSectionDay-input", f"{current_date.day:02d}"),
            ("selfIdentifiedDisabilityData--dateSignedOn-dateSectionYear-input", str(current_date.year)),
        ]
        
        for field_id, default_value in date_fields:
            selector = f'input[id="{field_id}"]'
            field = await self.page.query_selector(selector)
            if field:
                value = await field.input_value()
                if not value:
                    await field.fill(default_value)
                    log_data['date_fields'].append({'field_id': field_id, 'value': default_value})
        
        # Save log
        log_path = self.current_run_dir / "disability_disclosures.json"
        with open(log_path, 'w') as f:
            json.dump(log_data, f, indent=2)

    async def _process_generic_section(self, section, section_name: str, data=None) -> None:
        """Process any generic section using AI"""
        print(f"Processing Generic section: {section_name}")
        
        # Extract form elements from this section
        form_elements = await self._extract_form_elements_from_section(section)
        
        if not form_elements:
            print(f"No form elements found in {section_name} section")
            return
        if data == None:
            data = self.user_data
        # Use entire user data for unknown sections
        ai_response, key_mapping = await self._get_ai_response_for_section(data, form_elements)

        # Fill the form elements
        await self._fill_form_elements(ai_response, key_mapping)

    async def _handle_section_with_add(self, section, section_type: str) -> None:
        """Handle sections that have add functionality (experience, education, language)"""
        # Get appropriate data based on section type
        if section_type == "experience":
            items_data = self.user_data.get("work_experience", [])
        elif section_type == "education":
            items_data = self.user_data.get("education", [])
        elif section_type == "language":
            items_data = self.user_data.get("fluent_languages", [])
        else:
            items_data = []
        
        print(f"Found {len(items_data)} {section_type} entries")
        
        if not items_data:
            return
            
        # Process each item
        for i, item_data in enumerate(items_data):
            print(f"\n=== Filling {section_type} {i + 1} ===")
            
            # Click add button for each entry
            add_button = await section.query_selector('button[data-automation-id="add-button"]')
            if add_button:
                await add_button.click()
                await asyncio.sleep(2)
                print(f"Clicked add button for {section_type} {i + 1}")
            
            inputs = await section.query_selector_all('input, button, textarea, select')
            panel_elements = []
            previous_question = None
            previous_type = None

            for input_el in inputs:
                input_id = await input_el.get_attribute('data-automation-id') or await input_el.get_attribute('aria-haspopup') or 'unknown'
                if input_id in ["pageFooterBackButton", "pageFooterNextButton", "backToJobPosting"]:
                    continue

                group_label, aria_labelledby = await self._get_group_label_and_aria(input_el)
                question = await self._get_nearest_label_text(input_el) or 'UNLABELED'

                input_type = await input_el.get_attribute('type') or 'unknown'
                role = await input_el.get_attribute('role')
                placeholder = await input_el.get_attribute('placeholder')
                required = await input_el.get_attribute('required')

                if role == "spinbutton":
                    input_type = "spinbutton"

                # Enhanced duplicate question detection like in the notebook
                print(f"Input ID: {input_id}, Question: {question}, aria-labelledby: {aria_labelledby or 'None'}")
                print(f"Previous question: {previous_question}, Previous type: {previous_type}")
                
                if (question != 'UNLABELED' and 
                    question == previous_question and 
                    previous_type == "button" and 
                    input_id != "file-upload-input-ref"):
                    print(f"Skipping duplicate question: '{question}'")
                    continue

                input_tag = await input_el.evaluate("(el) => el.tagName.toLowerCase()")
                if input_tag and input_tag.lower() == 'textarea':
                    input_type = 'textarea'
                
                # Get options for all relevant input types
                options = await self._get_element_options(input_el, input_tag, input_type)

                # Only include elements that belong to the current panel
                if aria_labelledby and f'{i + 1}-panel' in aria_labelledby:
                    panel_elements.append({
                        'element': input_el,
                        'question': question or 'UNLABELED',
                        'aria_labelledby': aria_labelledby,
                        'input_type': input_type,
                        'input_tag': input_tag,
                        'input_id': input_id,
                        'options': options,
                        'placeholder': placeholder,
                        'required': required,
                        'role': role
                    })

                # Update tracking variables like in the notebook
                if question != 'UNLABELED':
                    previous_question = question
                    previous_type = input_type

            if panel_elements:
                print(f"Panel Elements Count: {len(panel_elements)}")
                for field in panel_elements:
                    input_type = field['input_type']
                    options = field['options'] if field['options'] else 'None'
                    print(f"Element: {field['question']}, Type: {input_type}, Options: {options}")

                # Get AI response with complete element information
                ai_values, key_mapping = await self._get_ai_response_for_section(item_data, panel_elements)
                print("AI Response:", ai_values)

                # Fill all elements with validation
                await self._fill_form_elements(ai_values, key_mapping)
                
            await asyncio.sleep(2)

    async def _extract_form_elements_from_section(self, section) -> List[Dict[str, Any]]:
        """Extract form elements from a specific section with duplicate question filtering and radio button grouping"""
        try:
            elements = []
            radio_groups = {}  # Group radio buttons by question/name
            
            # Find all input elements in the section
            inputs = await section.query_selector_all('input, button, textarea, select')
            
            for input_el in inputs:
                element_info = await self._extract_element_info(input_el)
                if element_info:
                    current_question = element_info['question'].lower().strip()
                    is_current_listbox = (element_info['input_tag'] == 'button' and 
                                        await input_el.get_attribute('aria-haspopup') == 'listbox')
                    
                    # Handle radio buttons - group them by question/name
                    if element_info['input_type'] == 'radio':
                        group_key = await self._get_radio_group_key(input_el, element_info)
                        
                        if group_key not in radio_groups:
                            radio_groups[group_key] = {
                                'question': await self._get_radio_group_question(input_el),
                                'input_type': 'radio_group',
                                'input_tag': 'radio_group',
                                'options': [],
                                'elements': [],
                                'input_id': f"radio_group_{group_key}"
                            }
                        
                        # Add this radio option to the group
                        option_label = element_info['question']  # This is actually the option label
                        radio_groups[group_key]['options'].append(option_label)
                        radio_groups[group_key]['elements'].append(input_el)
                        continue
                    
                    # Skip if this question is the same as previous AND previous was a listbox
                    if (self.previous_question and 
                        current_question == self.previous_question and 
                        self.previous_was_listbox):
                        print(f"Skipping duplicate question '{element_info['question']}' because previous question was a listbox")
                        continue
                    
                    # Update tracking for next iteration
                    self.previous_question = current_question
                    self.previous_was_listbox = is_current_listbox
                    
                    elements.append(element_info)
            
            # Add radio groups to elements
            for group_key, group_info in radio_groups.items():
                elements.append(group_info)
            
            return elements
            
        except Exception as e:
            print(f"Error extracting form elements from section: {e}")
            return []

    async def _get_radio_group_key(self, input_el, element_info) -> str:
        """Get a unique key for grouping radio buttons"""
        try:
            # Try to use the 'name' attribute first
            name = await input_el.get_attribute('name')
            if name:
                return name
            
            # Fallback to aria-labelledby or group context
            aria_labelledby = element_info.get('aria_labelledby')
            if aria_labelledby:
                return aria_labelledby
            
            # Fallback to parent fieldset or group
            group_id = await input_el.evaluate('''
                el => {
                    let group = el.closest("fieldset, [role='group']");
                    if (group) {
                        return group.id || group.getAttribute('aria-labelledby') || 'unnamed_group';
                    }
                    return 'no_group';
                }
            ''')
            
            return group_id or 'unknown_group'
        except:
            return 'unknown_group'

    async def _get_radio_group_question(self, input_el) -> str:
        """Get the question text for a radio button group"""
        try:
            # Look for fieldset legend
            question = await input_el.evaluate('''
                el => {
                    let group = el.closest("fieldset, [role='group']");
                    if (group) {
                        let legend = group.querySelector("legend");
                        if (legend && legend.textContent) return legend.textContent.trim();
                        
                        let labelledby = group.getAttribute("aria-labelledby");
                        if (labelledby) {
                            let labelEl = document.getElementById(labelledby);
                            if (labelEl && labelEl.textContent) return labelEl.textContent.trim();
                        }
                        
                        // Look for any label within the group that's not an option label
                        let labels = group.querySelectorAll("label");
                        for (let label of labels) {
                            // Skip labels that are directly for radio inputs (these are option labels)
                            if (!label.getAttribute('for') || !document.getElementById(label.getAttribute('for'))?.type === 'radio') {
                                if (label.textContent) return label.textContent.trim();
                            }
                        }
                    }
                    return 'Radio Question';
                }
            ''')
            
            return question or 'Radio Question'
        except:
            return 'Radio Question'

    async def _extract_form_elements_from_page(self) -> List[Dict[str, Any]]:
        """Extract all form elements from the current page with duplicate question filtering based on previous listbox"""
        try:
            elements = []
            
            # Find all input elements on the page
            inputs = await self.page.query_selector_all('input, button, textarea, select')
            
            for input_el in inputs:
                element_info = await self._extract_element_info(input_el)
                if element_info:
                    current_question = element_info['question'].lower().strip()
                    is_current_listbox = (element_info['input_tag'] == 'button' and 
                                        await input_el.get_attribute('aria-haspopup') == 'listbox')
                    
                    # Skip if this question is the same as previous AND previous was a listbox
                    if (self.previous_question and 
                        current_question == self.previous_question and 
                        self.previous_was_listbox):
                        print(f"Skipping duplicate question '{element_info['question']}' because previous question was a listbox")
                        continue
                    
                    # Update tracking for next iteration
                    self.previous_question = current_question
                    self.previous_was_listbox = is_current_listbox
                    
                    elements.append(element_info)
            
            return elements
            
        except Exception as e:
            print(f"Error extracting form elements from page: {e}")
            return []

    async def _extract_element_info(self, input_el) -> Optional[Dict[str, Any]]:
        """Extract information about a form element"""
        try:
            input_tag = await input_el.evaluate('el => el.tagName.toLowerCase()')
            input_type = await input_el.get_attribute('type') or 'unknown'
            input_id = await input_el.get_attribute('id') or 'unknown'
            
            # Get label information
            question = await self._get_nearest_label_text(input_el)
            group_label, aria_labelledby = await self._get_group_label_and_aria(input_el)
            
            # Get options for dropdown elements
            options = await self._get_element_options(input_el, input_tag, input_type)
            
            # Get other attributes
            placeholder = await input_el.get_attribute('placeholder')
            required = await input_el.get_attribute('aria-required')
            role = await input_el.get_attribute('role')
            
            return {
                'element': input_el,
                'question': question or 'Unknown',
                'input_id': input_id,
                'input_type': input_type,
                'input_tag': input_tag,
                'aria_labelledby': aria_labelledby,
                'options': options,
                'placeholder': placeholder,
                'required': required,
                'role': role
            }
            
        except Exception as e:
            print(f"Error extracting element info: {e}")
            return None

    async def _get_nearest_label_text(self, element) -> Optional[str]:
        """Get the nearest label text for a form element"""

        try:

            # Try multiple methods to find the label
            element_id = await element.get_attribute('id')
            if element_id and element_id != "unknown":
                label_elem = await self.page.query_selector(f'label[for="{element_id}"]')
                if label_elem:
                    label_text = await label_elem.text_content()
                    if label_text:
                        print("Found label by ID:", label_text)
                        return label_text.replace('*', '').strip()
            
            # Try parent label
            parent_label_handle = await element.evaluate_handle('el => el.closest("label")')
            parent_label = parent_label_handle.as_element() if parent_label_handle else None
            if parent_label:
                label_text = await parent_label.text_content()
                if label_text:
                    print("Found label by parent label:", label_text)
                    return label_text.replace('*', '').strip()
            
            # Try form field label
            form_field_label = await element.evaluate('''
                el => {
                    let cur = el.parentElement;
                    let depth = 0;
                    while (cur && depth < 15) {
                        if (cur.tagName.toLowerCase() === "div" &&
                            cur.getAttribute("data-automation-id")?.startsWith("formField-")) {
                            const lbl = cur.querySelector("label span, label");
                            if (lbl && lbl.textContent) return lbl.textContent.trim();
                        }
                        cur = cur.parentElement;
                        depth++;
                    }
                    return null;
                }
            ''')
            if form_field_label:
                print("Found label by form field:", form_field_label)
                return form_field_label.replace('*', '').strip()
            
            # Try aria-labelledby
            aria_labelledby = await element.get_attribute('aria-labelledby')
            if aria_labelledby:
                label_element = await self.page.query_selector(f'#{aria_labelledby}')
                if label_element:
                    label_text = await label_element.text_content()
                    if label_text:
                        print("Found label by aria-labelledby:", label_text)
                        return label_text.replace('*', '').strip()
            
            # Try fieldset legend
            fieldset_legend = await element.evaluate('''
                el => {
                    let fieldset = el.closest("fieldset");
                    if (fieldset) {
                        let legend = fieldset.querySelector("legend");
                        if (legend && legend.textContent && legend.textContent.trim() !== "") {
                            return legend.textContent.trim();
                        }
                    }
                    return null;
                }
            ''')
            
            if fieldset_legend:
                return fieldset_legend.replace('*', '').strip()

            # Try aria-label
            aria_label = await element.get_attribute('aria-label')
            if aria_label:
                print("Found label by aria-label:", aria_label)
                return aria_label.replace('*', '').strip()
            
            # Try placeholder as fallback
            placeholder = await element.get_attribute('placeholder')
            if placeholder:
                print("Found label by placeholder:", placeholder)
                return placeholder.replace('*', '').strip()
            
            return None
        except Exception as e:
            print(f"Error getting label for element: {e}")
            return None

    async def _get_group_label_and_aria(self, element) -> Tuple[Optional[str], Optional[str]]:
        """Get group label and aria-labelledby information"""
        try:
            result = await element.evaluate('''
                el => {
                    let group = el.closest("fieldset, [role='group']");
                    let aria_labelledby = null;
                    let label_text = null;
                    if (group) {
                        let legend = group.querySelector("legend");
                        if (legend && legend.textContent) label_text = legend.textContent.trim();
                        let labelledby = group.getAttribute("aria-labelledby");
                        if (labelledby) {
                            aria_labelledby = labelledby;
                            let labelEl = document.getElementById(labelledby);
                            if (labelEl && labelEl.textContent) label_text = labelEl.textContent.trim();
                        }
                        if (!label_text) {
                            let label = group.querySelector("label");
                            if (label && label.textContent) label_text = label.textContent.trim();
                        }
                    }
                    if (!label_text) {
                        let cur = el.parentElement;
                        let depth = 0;
                        while (cur && depth < 15) {
                            let labelledby = cur.getAttribute && cur.getAttribute("aria-labelledby");
                            if (labelledby) {
                                aria_labelledby = labelledby;
                                let labelEl = document.getElementById(labelledby);
                                if (labelEl && labelEl.textContent) {
                                    label_text = labelEl.textContent.trim();
                                    break;
                                }
                            }
                            cur = cur.parentElement;
                            depth++;
                        }
                    }
                    return {label_text, aria_labelledby};
                }
            ''')
            return result.get('label_text'), result.get('aria_labelledby')
        except:
            return None, None

    async def _get_element_options(self, input_el, input_tag: str, input_type: str) -> Optional[List[str]]:
        """Get options for dropdown/select elements"""
        try:
            options = None
            
            if input_tag == "button" or await input_el.get_attribute('role') == 'combobox':
                aria_haspopup = await input_el.get_attribute('aria-haspopup')
                if aria_haspopup == "listbox":
                    options = await self._get_listbox_options(input_el)
            
            return options
        except:
            return None

    async def _get_listbox_options(self, input_el) -> List[str]:
        """Extract options from a listbox by clicking it"""
        try:
            await input_el.click()
            await asyncio.sleep(1)
            
            options = []
            listbox_container = await self.page.query_selector('div[visibility="opened"]')
            
            if listbox_container:
                li_elements = await listbox_container.query_selector_all('li[role="option"]')
                for li in li_elements:
                    text = await li.text_content()
                    if text and text.strip():
                        options.append(text.strip())
                    else:
                        div_text = await li.query_selector('div')
                        if div_text:
                            nested_text = await div_text.text_content()
                            if nested_text and nested_text.strip():
                                options.append(nested_text.strip())

            await input_el.click()  # Close the dropdown
            await asyncio.sleep(0.5)
            return options
        except:
            return []

    async def _get_ai_response_without_skipping(self, current_data: Dict[str, Any], panel_elements: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Get AI response for form fields using OpenAI"""
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
            print(f"Error in get_ai_response_for_section: {e}")
            return {}, {}

    async def _get_ai_response_for_section_for_personal_information(self, current_data: Dict[str, Any], panel_elements: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Get AI response for form fields using OpenAI"""
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
  - Choose the option that best matches the user's profile. If the question is have you worked at the company before, the answer is no so respond accoringly based on question and radio option
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
            print(f"Error in get_ai_response_for_section: {e}")
            return {}, {}

    async def _get_ai_response_for_section(self, current_data: Dict[str, Any], panel_elements: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Get AI response for form fields using OpenAI"""
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
- For language fields asking fluency, use the closest match from the options list even if its not mentioned and make sure to fill all the listboxes about language fluency based on multiple metrics
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

    async def _fill_form_elements(self, ai_response: Dict[str, Any], key_mapping: Dict[str, Any]) -> None:
        """Fill form elements based on AI response"""

        for full_key, response_value in ai_response.items():
            if full_key in key_mapping:
                element_info = key_mapping[full_key]
                
                try:
                    print(f"Filling element {element_info['input_id']} with response: {response_value}")
                    
                    # Handle radio groups
                    if element_info['input_type'] == 'radio_group':
                        await self._fill_radio_group(element_info, response_value)
                    else:
                        # Handle single elements
                        input_el = element_info['element']
                        await self._fill_single_element(
                            input_el, 
                            element_info['input_id'],
                            element_info['input_type'],
                            element_info['input_tag'],
                            response_value,
                            element_info.get('options'),
                            element_info.get('question', 'Unknown')
                        )
                except Exception as e:
                    print(f"Error filling element {element_info['input_id']}: {e}")

    async def _fill_radio_group(self, radio_group_info: Dict[str, Any], response_value: str) -> None:
        """Fill a radio button group by selecting the appropriate option"""
        try:
            if response_value == "SKIP":
                print(f"Skipping radio group {radio_group_info['input_id']} as per AI response")
                return
            
            # Record the radio group data
            question = radio_group_info.get('question', 'Unknown radio group')
            if question and question != "UNLABELED":
                question_data = {
                    "question": question,
                    "tag": "radio_group",
                    "type": "radio",
                    "options": radio_group_info.get('options'),
                    "response_filled": response_value
                }
                self.application_data.append(question_data)
                print(f"Recorded radio group data: {question} -> {response_value}")
            
            options = radio_group_info['options']
            elements = radio_group_info['elements']
            
            print(f"Radio group question: {radio_group_info['question']}")
            print(f"Available options: {options}")
            print(f"AI selected: {response_value}")
            
            # Find the matching option
            selected_index = -1
            
            # First try exact match
            for i, option in enumerate(options):
                if option.lower().strip() == response_value.lower().strip():
                    selected_index = i
                    break
            
            # If no exact match, try partial match
            if selected_index == -1:
                for i, option in enumerate(options):
                    if response_value.lower().strip() in option.lower().strip() or option.lower().strip() in response_value.lower().strip():
                        selected_index = i
                        break
            
            # If still no match, use first option as fallback
            if selected_index == -1:
                print(f"No exact match found for '{response_value}', using first option")
                selected_index = 0
            
            # Select the radio button
            if 0 <= selected_index < len(elements):
                selected_element = elements[selected_index]
                selected_option = options[selected_index]
                
                await selected_element.check()
                print(f"Selected radio option: '{selected_option}'")
            else:
                print(f"Invalid selection index: {selected_index}")
                
        except Exception as e:
            print(f"Error filling radio group: {e}")

    async def _fill_single_element(self, input_el, input_id: str, input_type: str, input_tag: str, response: Any, options: Optional[List[str]] = None, question: str = None) -> None:
        """Fill a single form element"""
        try:
            # Record the question and response data (skip duplicates)
            if response != "SKIP" and question and question != "UNLABELED":
                question_data = {
                    "question": question,
                    "tag": input_tag,
                    "type": input_type,
                    "options": options if options else None,
                    "response_filled": response
                }
                self.application_data.append(question_data)
                print(f"Recorded data: {question} -> {response}")
            
            if response == "SKIP":
                print(f"Skipping input {input_id} as per AI response")
                return

            # Handle file uploads
            if input_tag == "input" and input_type == "file" and isinstance(response, str):
                if os.path.exists(response):
                    await input_el.set_input_files([response])
                    print(f"Uploaded file: {response}")
                return

            # Check if element is inside a multiSelectContainer
            is_multi_select = await input_el.evaluate('''
                el => {
                    let cur = el.parentElement;
                    let depth = 0;
                    while (cur && depth < 10) {
                        if (cur.getAttribute("data-automation-id")?.includes("multiSelectContainer")) {
                            return true;
                        }
                        cur = cur.parentElement;
                        depth++;
                    }
                    return false;
                }
            ''')

            # Handle multi-select containers (skills, etc.)
            if is_multi_select:
                await self._fill_multi_select_element(input_el, input_id, response)
                return

            # Handle regular text inputs and textareas
            if input_tag in ["input", "textarea"] and input_type not in ["radio", "checkbox", "spinbutton"]:
                if isinstance(response, list):
                    response = ", ".join(response)
                await input_el.fill(str(response))
                print(f"Filled {input_id} with: {response}")
                return

            # Handle listbox/dropdown elements
            if input_tag == "button" or await input_el.get_attribute('role') == 'combobox':
                await self._fill_listbox_element(input_el, response)
                return

            # Handle radio buttons
            if input_type == "radio":
                if response in [True, "true", "yes", "Yes", 1]:
                    await input_el.check()
                    print(f"Selected radio button {input_id}")
                else:
                    print(f"Skipping radio button {input_id} as response is not affirmative")
                return

            # Handle checkboxes
            if input_type == "checkbox":
                if response in [True, "true", "yes", "Yes", 1]:
                    await input_el.check()
                    print(f"Checked checkbox {input_id}")
                return

            # Handle spinbutton (number inputs)
            if input_type == "spinbutton":
                await input_el.fill(str(response))
                print(f"Filled spinbutton {input_id} with: {response}")
                return

            print(f"Unhandled element type: {input_tag}/{input_type} for {input_id}")

        except Exception as e:
            print(f"Error filling element {input_id}: {e}")

    async def _fill_multi_select_element(self, input_el, input_id: str, response: Any) -> None:
        """Fill multi-select container element (like skills or how did you hear about us)"""
        try:
            if not isinstance(response, list):
                response = [response] if response else []

            print(f"Filling MultiInputContainer for {input_id} with responses: {response}")

            # Get the container
            container_handle = await input_el.evaluate_handle('''
                el => {
                    let cur = el.parentElement;
                    let depth = 0;
                    while (cur && depth < 10) {
                        if (cur.getAttribute("data-automation-id")?.includes("multiSelectContainer")) {
                            return cur;
                        }
                        cur = cur.parentElement;
                        depth++;
                    }
                    return null;
                }
            ''')

            container = container_handle.as_element() if container_handle else None
            if not container:
                print(f"Could not find multiSelectContainer for {input_id}")
                return

            # Determine if this is a nested multi-level field (like "how did you hear")
            question = await self._get_nearest_label_text(input_el)
            is_nested_field = any(keyword in question.lower() for keyword in ["hear", "source", "referral"])
            print("It is nested field:") if is_nested_field else print("It is single")
            
            # Add each item
            for item in response:
                try:
                    print(f"Adding item: {item}")
                    
                    # Click the container to focus
                    await container.click()
                    await asyncio.sleep(0.5)
                    
                    # Clear any existing text and type the item
                    await input_el.fill("")
                    await asyncio.sleep(0.5)
                    await input_el.fill(str(item))
                                        
                    # Press Enter to trigger dropdown
                    await input_el.press('Enter')
                    await asyncio.sleep(2)

                    if is_nested_field:
                        # Handle nested multi-level dropdown (like "how did you hear about us")
                        await self._handle_nested_dropdown(item)
                    else:
                        # Handle single-level dropdown (like skills)
                        await self._handle_single_dropdown(item)

                    print(f"Successfully added item: {item}")

                except Exception as e:
                    print(f"Error adding item '{item}': {e}")
                    continue

        except Exception as e:
            print(f"Error filling multi-select element {input_id}: {e}")

    async def _handle_single_dropdown(self, item: str) -> None:
        """Handle single-level dropdown (like skills)"""
        prompt_options = await self.page.query_selector_all('div[data-automation-id="promptLeafNode"]')
        
        if prompt_options:
            print(f"Found {len(prompt_options)} options for '{item}':")
            
            # Find the best matching option
            best_match = None
            best_score = 0
            item_lower = str(item).lower()
            
            for opt in prompt_options:
                option_text = await opt.text_content()
                option_lower = option_text.lower().strip()
                print(f"  - {option_text}")
                
                # Calculate match score
                if option_lower == item_lower:
                    best_match = opt
                    best_score = 100
                    break
                elif item_lower in option_lower or option_lower in item_lower:
                    score = len(item_lower) / len(option_lower) * 100
                    if score > best_score:
                        best_match = opt
                        best_score = score
            
            # Click the best match or first option if no good match
            selected_option = best_match if best_match else prompt_options[0]
            selected_text = await selected_option.text_content()
            
            await selected_option.click()
            print(f"Selected: '{selected_text}' (score: {best_score:.1f})")
            await asyncio.sleep(1)
        else:
            print(f"No dropdown options found for '{item}'")

    async def _handle_nested_dropdown(self, item: str) -> None:
        """Handle nested multi-level dropdown (like 'how did you hear about us')"""
        # First level dropdown
        first_level_options = await self.page.query_selector_all('div[data-automation-id="promptLeafNode"]')
        
        if first_level_options:
            print(f"Found {len(first_level_options)} first-level options for '{item}':")
            
            # Find best match for first level
            best_first_match = None
            best_first_score = 0
            item_lower = str(item).lower()
            
            for opt in first_level_options:
                option_text = await opt.text_content()
                option_lower = option_text.lower().strip()
                print(f"  Level 1: {option_text}")
                
                # Map common terms to first-level categories
                if any(term in item_lower for term in ['linkedin', 'facebook', 'twitter', 'instagram']) and 'social' in option_lower:
                    best_first_match = opt
                    best_first_score = 90
                    break
                elif any(term in item_lower for term in ['indeed', 'glassdoor', 'monster', 'job']) and 'job' in option_lower:
                    best_first_match = opt
                    best_first_score = 90
                    break
                elif any(term in item_lower for term in ['friend', 'colleague', 'referral']) and any(ref_term in option_lower for ref_term in ['referral', 'friend', 'colleague']):
                    best_first_match = opt
                    best_first_score = 90
                    break
                elif item_lower in option_lower or option_lower in item_lower:
                    score = len(item_lower) / len(option_lower) * 100
                    if score > best_first_score:
                        best_first_match = opt
                        best_first_score = score
            
            # Click first level option
            first_selected = best_first_match if best_first_match else first_level_options[0]
            first_selected_text = await first_selected.text_content()
            
            await first_selected.click()
            print(f"Selected first level: '{first_selected_text}'")
            await asyncio.sleep(1.5)  # Wait for second level to load
            
            # Second level dropdown
            second_level_options = await self.page.query_selector_all('div[data-automation-id="promptLeafNode"]')
            
            if second_level_options:
                print(f"Found {len(second_level_options)} second-level options:")
                
                # Find best match for second level
                best_second_match = None
                best_second_score = 0
                
                for opt in second_level_options:
                    option_text = await opt.text_content()
                    option_lower = option_text.lower().strip()
                    print(f"  Level 2: {option_text}")
                    
                    # Calculate match score for second level
                    if option_lower == item_lower:
                        best_second_match = opt
                        best_second_score = 100
                        break
                    elif item_lower in option_lower or option_lower in item_lower:
                        score = len(item_lower) / len(option_lower) * 100
                        if score > best_second_score:
                            best_second_match = opt
                            best_second_score = score
                
                # Click second level option
                second_selected = best_second_match if best_second_match else second_level_options[0]
                second_selected_text = await second_selected.text_content()
                
                await second_selected.click()
                print(f"Selected second level: '{second_selected_text}' (score: {best_second_score:.1f})")
                await asyncio.sleep(1)
            else:
                print("No second-level options found")
        else:
            print(f"No first-level options found for '{item}'")

    async def _fill_listbox_element(self, input_el, response: str) -> None:
        """Fill a listbox/combobox element"""
        try:
            await input_el.click()
            await asyncio.sleep(0.5)
            
            listbox = await self.page.query_selector('div[visibility="opened"]')
            if listbox:
                li_elements = await listbox.query_selector_all('li')
                for li in li_elements:
                    text = await li.text_content()
                    if text and (text.lower() == response.lower() or response.lower() in text.lower()):
                        await li.click()
                        print(f"Selected option: {text}")
                        return True
                        
                    # Check nested div elements
                    div_element = await li.query_selector('div')
                    if div_element:
                        div_text = await div_element.text_content()
                        if div_text and response.lower() in div_text.lower():
                            await li.click()
                            print(f"Selected option: {div_text}")
                            await asyncio.sleep(0.2)
                            return True
            
            print(f"Could not find option '{response}' in dropdown")
            return False
            
        except Exception as e:
            print(f"Error filling listbox element: {e}")
            return False

    async def submit_form(self) -> bool:
        """Submit the current form"""
        try:
            # Look for submit/continue button
            submit_selectors = [
                'button[data-automation-id="pageFooterNextButton"]',
                'button[aria-label*="Save and Continue"]',
                'button[aria-label*="Submit"]',
                'button[aria-label*="Next"]'
            ]
            
            for selector in submit_selectors:
                submit_btn = await self.page.query_selector(selector)
                if submit_btn:
                    await submit_btn.click()
                    print(f"Clicked submit button: {selector}")
                    await asyncio.sleep(5)
                    return True
            
            print("No submit button found")
            return False
            
        except Exception as e:
            print(f"Error submitting form: {e}")
            return False

    def save_application_data(self) -> str:
        """Save collected application data to JSON file"""
        try:
            filename = f"final_application_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = self.current_run_dir / filename
            
            # Create a summary of the data
            summary = {
                "timestamp": datetime.now().isoformat(),
                "total_questions": len(self.application_data),
                "application_data": self.application_data
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            
            print(f"Application data saved to: {filepath}")
            print(f"Total questions recorded: {len(self.application_data)}")
            return str(filepath)
            
        except Exception as e:
            print(f"Error saving application data: {e}")
            return ""

    async def close_browser(self) -> None:
        """Close the browser"""
        if self.browser:
            await self.browser.close()
            print("Browser closed")
