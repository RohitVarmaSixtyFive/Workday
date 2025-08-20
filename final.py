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

from ai_handler import AIResponseHandler

class JobApplicationBot:
    """Main class for job application automation"""
    
    def __init__(self, config_path: str = "data/user_profile_temp.json"):
        """Initialize the job application bot
        
        Args:
            config_path: Path to user profile configuration file
        """
        load_dotenv()
        self.config_path = config_path
        self.user_data = self._load_user_profile()
        self.client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.ai_handler = AIResponseHandler(self.client)  # Initialize AI handler
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.company: str = "unknown"  # Track current company
        
        # Application URLs for different companies
        self.company_urls = {
            "nvidia": "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/US%2C-CA%2C-Santa-Clara/Senior-AI-and-ML-Engineer---AI-for-Networking_JR2000376/apply/applyManually?q=ml+enginer",
            "salesforce": "https://salesforce.wd12.myworkdayjobs.com/en-US/External_Career_Site/job/Singapore---Singapore/Senior-Manager--Solution-Engineering--Philippines-_JR301876/apply/applyManually",
            "hitachi": "https://hitachi.wd1.myworkdayjobs.com/en-US/hitachi/job/Alamo%2C-Tennessee%2C-United-States-of-America/Project-Engineer_R0102918/apply/applyManually",
            "icf": "https://icf.wd5.myworkdayjobs.com/en-US/ICFExternal_Career_Site/job/Reston%2C-VA/Senior-Paid-Search-Manager_R2502057/apply/applyManually",
            "harris": "https://harriscomputer.wd3.myworkdayjobs.com/en-US/1/job/Florida%2C-United-States/Vice-President-of-Sales_R0030918/apply/applyManually",
            "walmart": "https://walmart.wd5.myworkdayjobs.com/en-US/WalmartExternal/job/Sherbrooke%2C-QC/XMLNAME--CAN--Self-Checkout-Attendant_R-2263567-1/apply/applyManually"
        }
        
        # Logging setup with company name and incrementing counter
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)
        self.run_number = self._get_next_run_number()
        self.current_run_dir = self.logs_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.company}_{self.run_number:03d}"
        self.current_run_dir.mkdir(exist_ok=True)
        self.url = None  # Store the current job URL
        # Track the previous question and whether it was a listbox
        self.previous_question = None
        self.previous_was_listbox = False
        
        # Data collection for final JSON output
        self.application_data = []
        self.extracted_elements = []  # Store all extracted elements
        self.filled_elements = []     # Store elements with responses
        
        # Timing profiling for questions
        self.question_timings = {}  # Store timing data for each question
        self.current_question_start_times = {}  # Track when questions are first identified

    def _get_next_run_number(self) -> int:
        """Get the next run number for the current company"""
        try:
            existing_runs = list(self.logs_dir.glob(f"*_{self.company}_*"))
            if not existing_runs:
                return 1
            
            # Extract numbers from existing run directories
            run_numbers = []
            for run_dir in existing_runs:
                parts = run_dir.name.split('_')
                if len(parts) >= 3 and parts[-2] == self.company:
                    try:
                        run_numbers.append(int(parts[-1]))
                    except ValueError:
                        continue
            
            return max(run_numbers, default=0) + 1
        except Exception:
            return 1

    def set_company(self, company: str) -> None:
        """Set the company for this application session"""
        self.company = company
        # Recreate the run directory with the company name
        self.run_number = self._get_next_run_number()
        self.current_run_dir = self.logs_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.company}_{self.run_number:03d}"
        self.current_run_dir.mkdir(exist_ok=True)
        print(f"Set company to {company}, run directory: {self.current_run_dir}")
        
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

    def _start_question_timing(self, question: str, question_id: str = None) -> None:
        """Record when a question is first identified/seen"""
        if not question or question == "UNLABELED":
            return
            
        # Create a unique key for the question
        timing_key = f"{question_id}_{question}" if question_id else question
        
        if timing_key not in self.current_question_start_times:
            start_time = datetime.now()
            self.current_question_start_times[timing_key] = start_time
            print(f"[TIMING] Question identified at {start_time.strftime('%H:%M:%S.%f')[:-3]}: {question}")

    def _end_question_timing(self, question: str, question_id: str = None, response: Any = None) -> None:
        """Record when a question is filled and calculate the time taken"""
        if not question or question == "UNLABELED":
            return
            
        # Create the same unique key used in start timing
        timing_key = f"{question_id}_{question}" if question_id else question
        
        if timing_key in self.current_question_start_times:
            start_time = self.current_question_start_times[timing_key]
            end_time = datetime.now()
            duration = end_time - start_time
            duration_ms = duration.total_seconds() * 1000
            
            # Store timing data
            self.question_timings[timing_key] = {
                "question": question,
                "question_id": question_id,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_ms": round(duration_ms, 2),
                "duration_readable": f"{duration_ms/1000:.2f}s",
                "response": str(response) if response and response != "SKIP" else None
            }
            
            # Clean up the start time tracking
            del self.current_question_start_times[timing_key]
            
            print(f"[TIMING] Question filled at {end_time.strftime('%H:%M:%S.%f')[:-3]}: {question} (took {duration_ms/1000:.2f}s)")
        else:
            print(f"[TIMING WARNING] No start time recorded for question: {question}")

    def get_timing_summary(self) -> Dict[str, Any]:
        """Get a summary of all question timings"""
        if not self.question_timings:
            return {"total_questions": 0, "total_time_ms": 0, "average_time_ms": 0, "timings": []}
        
        total_time = sum(timing["duration_ms"] for timing in self.question_timings.values())
        avg_time = total_time / len(self.question_timings)
        
        # Sort timings by start time
        sorted_timings = sorted(
            self.question_timings.values(),
            key=lambda x: x["start_time"]
        )
        
        return {
            "total_questions": len(self.question_timings),
            "total_time_ms": round(total_time, 2),
            "total_time_readable": f"{total_time/1000:.2f}s",
            "average_time_ms": round(avg_time, 2),
            "average_time_readable": f"{avg_time/1000:.2f}s",
            "fastest_question_ms": min(timing["duration_ms"] for timing in self.question_timings.values()),
            "slowest_question_ms": max(timing["duration_ms"] for timing in self.question_timings.values()),
            "timings": sorted_timings
        }

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
        self.url = url  # Store URL for later use
        await self.page.goto(url, wait_until='networkidle', timeout=30000)
        print(f"Navigated to {company} job application page")

    async def handle_authentication(self, auth_type: int = 1) -> bool:
        """Handle authentication - tries signup first, then falls back to signin if needed.
        
        Args:
            auth_type: 1 for sign in, 2 for sign up (legacy parameter, now tries signup first regardless).
        """
        try:
            # First, try signup
            print("Attempting signup first...")
            signup_success = await self._handle_signup()
            
            # await till networkidle
            await self.page.wait_for_load_state('networkidle')
            
            await asyncio.sleep(10)
            print("Waited for sign up to work")
            # Check if email and password fields are still present (indicating signup failed/needs signin)
            email_input = await self.page.query_selector('input[data-automation-id="email"]')
            password_input = await self.page.query_selector('input[data-automation-id="password"]')
            
            if email_input and password_input:
                # Fields are still there, try signin instead
                print("Email and password fields still present, attempting signin...")
                return await self._handle_signin()
            else:
                # Fields are gone, signup was successful
                print("Signup appears to be successful")
                return True
                
        except Exception as e:
            print(f"Error during authentication: {e}")
            # Fallback to signin if anything goes wrong
            try:
                return await self._handle_signin()
            except Exception as signin_error:
                print(f"Error during signin fallback: {signin_error}")
                return False

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
                await asyncio.sleep(1)
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
            
            ai_values, _ = await self.ai_handler.get_ai_response_without_skipping(
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
                option_label = await self._get_radio_option_label(radio_el)
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
            
            ai_values, _ = await self.ai_handler.get_ai_response_without_skipping(
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
            print(f"Processing element {i}: Input ID: {input_id}, Question: {question}, Type: {input_type}", 
                  f"Role: {role}, Placeholder: {placeholder}, Required: {required}")
            
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
            
            # Start timing for this question when it's identified
            if question and question != "UNLABELED":
                self._start_question_timing(question, input_id)
            
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
            ai_values, _ = await self.ai_handler.get_ai_response_for_personal_information(
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
        print("Processing later sections")

        await asyncio.sleep(5)  # Wait for page to load
        
        main_page = await self.page.query_selector('div[data-automation-id="applyFlowPage"]')
        
        # Check for disability status fieldset first
        disability_status_group = await self.page.query_selector('fieldset[data-automation-id="disabilityStatus-CheckboxGroup"]')
        if disability_status_group:
            print("Found disability status checkbox group in later sections, using specialized handler")
            await self._handle_disability_status_checkboxes(disability_status_group)
            await asyncio.sleep(0.5)  # Wait after handling
        
        INPUT_SELECTOR = 'button, input, select, textarea, [role="button"]'
        
        i = 0
        prev_answered_question = None
        prev_type = None
    
        while True:
            # Re-extract elements on each iteration (fresh DOM state)
            inputs = await main_page.query_selector_all(INPUT_SELECTOR)
            # for input_el in inputs:
            #     input_type = await input_el.get_attribute('type')
            #     input_id = await input_el.get_attribute('data-automation-id') or await input_el.get_attribute('aria-haspopup') or 'unknown'
            #     print(f"Input_id :{input_id}  Input type: {input_type}")
                
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

            if disability_status_group and input_type == "checkbox":
                i+=1
                continue
            
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
            
            # disability_status = await main_page.query_selector('div[data-automation-id="formField-disabilityStatus"]')
            # if disability_status:
            #     print("Disability status section found, handling with special method")
            #     await self.handle_disability_status_checkboxes(disability_status)
            #     continue
            # print("Disability status section not found continue with regular processing")      
               
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
            
            # Start timing for this question when it's identified
            if question and question != "UNLABELED":
                self._start_question_timing(question, input_id)
            
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
            ai_values, _ = await self.ai_handler.get_ai_response_without_skipping(
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
        ai_response, key_mapping = await self.ai_handler.get_ai_response_for_section(skills_data, form_elements)
        
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
        
        # Check if this is the special disability status checkbox group
        disability_status_group = await section.query_selector('fieldset[data-automation-id="disabilityStatus-CheckboxGroup"]')
        if disability_status_group:
            print("Found disability status checkbox group, using specialized handler")
            await self._handle_disability_status_checkboxes(disability_status_group)
            return
        
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
    
    async def _handle_disability_status_checkboxes(self, checkbox_group) -> None:
        """Handle the disability status checkbox group that requires exactly one selection"""
        print("Processing disability status checkbox group")
        
        # Find all checkboxes in the group
        checkboxes = await checkbox_group.query_selector_all('input[type="checkbox"]')
        
        if not checkboxes or len(checkboxes) == 0:
            print("No checkboxes found in disability status group")
            return
            
        print(f"Found {len(checkboxes)} disability status checkboxes")
        
        # Choose which option to select (option index 2 = "I do not want to answer")
        # Options are typically:
        # 0: Yes, I have a disability
        # 1: No, I do not have a disability
        # 2: I do not want to answer
        selected_option = 1
        
        try:
            # First uncheck all boxes to avoid conflicts
            for i, checkbox in enumerate(checkboxes):
                is_checked = await checkbox.is_checked()
                if is_checked:
                    print(f"Unchecking checkbox {i}")
                    await checkbox.uncheck()
                    await asyncio.sleep(1)  # Wait for UI to update
            
            # Now check the desired option if we have enough options
            if selected_option < len(checkboxes):
                checkbox = checkboxes[selected_option]
                
                # Try to get the label for better logging
                try:
                    label = await checkbox.evaluate('(el) => { const label = document.querySelector(`label[for="${el.id}"]`); return label ? label.textContent : "Unknown"; }')
                    print(f"Selecting disability option: {label}")
                except Exception:
                    print(f"Selecting disability option {selected_option}")
                
                # Check the checkbox with retry logic
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        await checkbox.check()
                        await asyncio.sleep(0.5)  # Longer wait for page to stabilize
                        
                        # Verify it's checked
                        is_checked = await checkbox.is_checked()
                        if is_checked:
                            print(f"Successfully selected disability option {selected_option}")
                            # Verify other checkboxes are unchecked
                            all_others_unchecked = True
                            for i, other_checkbox in enumerate(checkboxes):
                                if i != selected_option:
                                    if await other_checkbox.is_checked():
                                        all_others_unchecked = False
                                        print(f"Warning: Checkbox {i} is still checked!")
                            
                            if all_others_unchecked:
                                print("All other checkboxes are properly unchecked")
                            break
                        else:
                            print(f"Attempt {attempt+1}: Failed to check the checkbox")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(1)
                    except Exception as e:
                        print(f"Attempt {attempt+1} error: {str(e)}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)
            else:
                print(f"Selected option {selected_option} is out of range (only {len(checkboxes)} checkboxes found)")
                
        except Exception as e:
            print(f"Error handling disability status checkboxes: {str(e)}")

    async def _process_generic_section(self, section, section_name: str, data=None) -> None:
        """Process any generic section using AI"""
        print(f"Processing Generic section: {section_name}")
        
        # Check for disability status fieldset first
        disability_status_group = await section.query_selector('fieldset[data-automation-id="disabilityStatus-CheckboxGroup"]')
        if disability_status_group:
            print(f"Found disability status checkbox group in {section_name}, using specialized handler")
            await self._handle_disability_status_checkboxes(disability_status_group)
            return
        
        # Extract form elements from this section
        form_elements = await self._extract_form_elements_from_section(section)
        
        if not form_elements:
            print(f"No form elements found in {section_name} section")
            return
        if data == None:
            data = self.user_data
        # Use entire user data for unknown sections
        ai_response, key_mapping = await self.ai_handler.get_ai_response_for_section(data, form_elements)

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
        previous_aria_label_section_number = None
        # Process each item
        for i, item_data in enumerate(items_data):
            print(f"\n=== Filling {section_type} {i + 1} ===")
            
            # Click add button for each entry
            add_button = await section.query_selector('button[data-automation-id="add-button"]')
            if add_button and (previous_aria_label_section_number == None or previous_aria_label_section_number < f"{len(items_data)}-panel"):
                await add_button.click()
                await asyncio.sleep(2)
                print(f"Clicked add button for {section_type} {i + 1}")
                previous_aria_label_section_number = f"{len(items_data)}-panel"
            
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
                    print(f"Skipping duplicate question: '{question}', previous type was '{previous_type}'")
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
                ai_values, key_mapping = await self.ai_handler.get_ai_response_for_section(item_data, panel_elements)
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
                                'question': element_info['question'],  # Use the group question from element_info
                                'input_type': 'radio_group',
                                'input_tag': 'radio_group',
                                'options': [],
                                'elements': [],
                                'input_id': f"radio_group_{group_key}"
                            }
                        
                        # Add this radio option to the group using the specific option label
                        option_label = element_info.get('option_label', 'Unknown Option')
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
            
            # Special handling for radio buttons
            if input_type == 'radio':
                # For radio buttons, get both group question and specific option label
                group_question = question or group_label or 'UNLABELED'
                option_label = await self._get_radio_option_label(input_el)
                
                return {
                    'element': input_el,
                    'question': group_question,  # e.g., "Gender"
                    'option_label': option_label,  # e.g., "Male", "Female", etc.
                    'input_id': input_id,
                    'input_type': input_type,
                    'input_tag': input_tag,
                    'aria_labelledby': aria_labelledby,
                    'options': None,
                    'placeholder': None,
                    'required': await input_el.get_attribute('aria-required'),
                    'role': await input_el.get_attribute('role')
                }
            
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
            # PRIORITY 1: Try form field container label (most reliable for this structure)
            form_field_label = await element.evaluate('''
                el => {
                    // First, try to find the immediate formField container
                    let cur = el.parentElement;
                    let depth = 0;
                    while (cur && depth < 10) {
                        if (cur.tagName.toLowerCase() === "div" &&
                            cur.getAttribute("data-automation-id")?.startsWith("formField-")) {
                            // Found the form field container, now find its label
                            const lbl = cur.querySelector("label");
                            if (lbl && lbl.textContent) {
                                return lbl.textContent.trim();
                            }
                        }
                        cur = cur.parentElement;
                        depth++;
                    }
                    return null;
                }
            ''')
            if form_field_label:
                print("Found label by form field container:", form_field_label)
                return form_field_label.replace('*', '').strip()

            # PRIORITY 2: Try label that correctly references this element's ID
            element_id = await element.get_attribute('id')
            if element_id and element_id != "unknown":
                # Make sure the label's 'for' attribute matches exactly AND the element is in the same form field
                correct_label = await element.evaluate(f'''
                    el => {{
                        // Find all labels with matching 'for' attribute
                        const labels = document.querySelectorAll('label[for="{element_id}"]');
                        
                        // Check each label to see if it's in the same form field container as this element
                        for (let label of labels) {{
                            let labelContainer = label.closest('[data-automation-id^="formField-"]');
                            let elementContainer = el.closest('[data-automation-id^="formField-"]');
                            
                            // If both are in the same container, this is the correct label
                            if (labelContainer && elementContainer && labelContainer === elementContainer) {{
                                return label.textContent ? label.textContent.trim() : null;
                            }}
                        }}
                        return null;
                    }}
                ''')
                if correct_label:
                    print("Found correct label by ID match in same container:", correct_label)
                    return correct_label.replace('*', '').strip()
            
            # PRIORITY 3: Try parent label
            parent_label_handle = await element.evaluate_handle('el => el.closest("label")')
            parent_label = parent_label_handle.as_element() if parent_label_handle else None
            if parent_label:
                label_text = await parent_label.text_content()
                if label_text:
                    print("Found label by parent label:", label_text)
                    return label_text.replace('*', '').strip()
            
            # PRIORITY 4: Try aria-labelledby
            aria_labelledby = await element.get_attribute('aria-labelledby')
            if aria_labelledby:
                label_element = await self.page.query_selector(f'#{aria_labelledby}')
                if label_element:
                    label_text = await label_element.text_content()
                    if label_text:
                        print("Found label by aria-labelledby:", label_text)
                        return label_text.replace('*', '').strip()
            
            # PRIORITY 5: Try fieldset legend
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

            # PRIORITY 6: Try aria-label
            aria_label = await element.get_attribute('aria-label')
            if aria_label:
                print("Found label by aria-label:", aria_label)
                return aria_label.replace('*', '').strip()
            
            # PRIORITY 7: Try placeholder as fallback
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

    async def _get_radio_option_label(self, radio_element) -> str:
        """Get the specific option label for a radio button (not the group label)"""
        try:
            # Method 1: Check for direct label associated with this specific radio
            # This is the most reliable method for the Workday structure
            radio_id = await radio_element.get_attribute('id')
            if radio_id:
                # Look for label with for attribute pointing to this radio
                specific_label = await self.page.query_selector(f'label[for="{radio_id}"]')
                if specific_label:
                    label_text = await specific_label.inner_text()
                    if label_text and label_text.strip():
                        print(f"Found radio option label by ID '{radio_id}': {label_text.strip()}")
                        return label_text.strip()
            
            # Method 2: Look for nearby label in the same radio container
            # This handles cases where the structure is slightly different
            container_label = await radio_element.evaluate("""
                (element) => {
                    // Look for a label element in the same immediate container
                    let parent = element.parentElement;
                    if (parent) {
                        // First check immediate parent for label
                        let label = parent.querySelector('label:not([id])');
                        if (label && label.textContent && label.textContent.trim()) {
                            return label.textContent.trim();
                        }
                        
                        // Check parent's parent (one level up)
                        let grandParent = parent.parentElement;
                        if (grandParent) {
                            let grandLabel = grandParent.querySelector('label:not([id])');
                            if (grandLabel && grandLabel.textContent && grandLabel.textContent.trim()) {
                                return grandLabel.textContent.trim();
                            }
                        }
                    }
                    return '';
                }
            """)
            
            if container_label and container_label.strip():
                print(f"Found radio option label by container: {container_label.strip()}")
                return container_label.strip()
            
            # Method 3: Look for text in sibling elements
            try:
                sibling_text = await radio_element.evaluate("""
                    (element) => {
                        const nextSibling = element.nextElementSibling;
                        if (nextSibling && nextSibling.textContent) {
                            let text = nextSibling.textContent.trim();
                            if (text && text.length < 50) {
                                return text;
                            }
                        }
                        
                        const prevSibling = element.previousElementSibling;
                        if (prevSibling && prevSibling.textContent) {
                            let text = prevSibling.textContent.trim();
                            if (text && text.length < 50) {
                                return text;
                            }
                        }
                        
                        return '';
                    }
                """)
                
                if sibling_text and len(sibling_text) < 50:
                    print(f"Found radio option label by sibling: {sibling_text}")
                    return sibling_text
                    
            except:
                pass
            
            # Method 4: Get value attribute as fallback
            value = await radio_element.get_attribute('value')
            if value and value != 'on':
                # Convert common values to readable text
                if value.lower() == 'true':
                    return 'Yes'
                elif value.lower() == 'false':
                    return 'No'
                else:
                    print(f"Found radio option label by value: {value}")
                    return value
                
            print(f"Could not find radio option label, using fallback")
            return "Unknown Option"
            
        except Exception as e:
            print(f"Error getting radio option label: {e}")
            return "Unknown Option"

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
            question = radio_group_info.get('question', 'Unknown radio group')
            input_id = radio_group_info.get('input_id', 'radio_group')
            
            # Start timing for this question
            if question and question != "UNLABELED":
                self._start_question_timing(question, input_id)
            
            if response_value == "SKIP":
                print(f"Skipping radio group {input_id} as per AI response")
                # End timing for skipped questions
                if question and question != "UNLABELED":
                    self._end_question_timing(question, input_id, "SKIP")
                return
            
            # Record the radio group data
            if question and question != "UNLABELED":
                # Log extracted element info
                element_data = {
                    "question": question,
                    "input_id": input_id,
                    "input_type": "radio",
                    "input_tag": "radio_group",
                    "aria_labelledby": radio_group_info.get('aria_labelledby'),
                    "options": radio_group_info.get('options'),
                    "placeholder": None,
                    "required": radio_group_info.get('required'),
                    "role": "radiogroup"
                }
                self.extracted_elements.append(element_data)
                
                # Log filled element info (with response)
                filled_data = element_data.copy()
                filled_data["response_filled"] = response_value
                self.filled_elements.append(filled_data)
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
                
                # End timing for successful radio group selection
                if question and question != "UNLABELED":
                    self._end_question_timing(question, input_id, response_value)
            else:
                print(f"Invalid selection index: {selected_index}")
                # End timing for failed selection
                if question and question != "UNLABELED":
                    self._end_question_timing(question, input_id, f"FAILED: Invalid index {selected_index}")
                
        except Exception as e:
            print(f"Error filling radio group: {e}")
            # End timing for exceptions
            if question and question != "UNLABELED":
                self._end_question_timing(question, input_id, f"ERROR: {str(e)}")

    async def handle_disability_status_checkboxes(self, section) -> None:
        """Handle the disability status checkbox group that requires exactly one selection"""
        print("Processing disability status section")
        
        # Find the checkbox container
        checkbox_group = await section.query_selector('fieldset[data-automation-id="disabilityStatus-CheckboxGroup"]')
        
        if not checkbox_group:
            print("Disability status checkbox group not found")
            return
            
        # Find all checkboxes in the group
        checkboxes = await checkbox_group.query_selector_all('input[type="checkbox"]')
        
        if not checkboxes or len(checkboxes) == 0:
            print("No checkboxes found in disability status group")
            return
            
        print(f"Found {len(checkboxes)} disability status checkboxes")
        
        selected_option = 1
        
        # First uncheck all boxes to avoid conflicts
        for i, checkbox in enumerate(checkboxes):
            is_checked = await checkbox.is_checked()
            if is_checked:
                await checkbox.uncheck()
                await asyncio.sleep(1)  # Wait for UI to update
        
        # Now check the desired option
        try:
            # Get the checkbox and its label for better logging
            checkbox = checkboxes[selected_option]
            label_element = await checkbox.evaluate('(el) => el.nextElementSibling.nextElementSibling.textContent')
            
            # Check the checkbox
            await checkbox.check()
            await asyncio.sleep(2)  # Longer wait for page to stabilize
            
            # Verify it's checked
            is_checked = await checkbox.is_checked()
            if is_checked:
                print(f"Successfully selected disability option: {label_element}")
            else:
                print(f"Failed to select disability option: {label_element}")
                
        except Exception as e:
            print(f"Error selecting disability status checkbox: {str(e)}")

    async def _fill_single_element(self, input_el, input_id: str, input_type: str, input_tag: str, response: Any, options: Optional[List[str]] = None, question: str = None) -> None:
        """Fill a single form element"""
        try:
            # Start timing for this question if we have a valid question
            if question and question != "UNLABELED":
                self._start_question_timing(question, input_id)
            
            # Get complete element information for logging
            group_label, aria_labelledby = await self._get_group_label_and_aria(input_el)
            placeholder = await input_el.get_attribute('placeholder')
            required = await input_el.get_attribute('required')
            role = await input_el.get_attribute('role')
            
            # Log extracted element info
            element_data = {
                "question": question,
                "input_id": input_id,
                "input_type": input_type,
                "input_tag": input_tag,
                "aria_labelledby": aria_labelledby,
                "options": options,
                "placeholder": placeholder,
                "required": required,
                "role": role
            }
            self.extracted_elements.append(element_data)
            
            # Log filled element info (with response)
            if response != "SKIP" and question and question != "UNLABELED":
                filled_data = element_data.copy()
                filled_data["response_filled"] = response
                self.filled_elements.append(filled_data)
                print(f"Recorded data: {question} -> {response}")
            
            if response == "SKIP":
                print(f"Skipping input {input_id} as per AI response")
                # End timing even for skipped questions
                if question and question != "UNLABELED":
                    self._end_question_timing(question, input_id, "SKIP")
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
                print("Inside fill single element handling the checkbox")
                normalized = str(response).strip().lower()
                truthy_values = {"true", "yes", "1", "y", "on"}
                falsy_values = {"false", "no", "0", "n", "off"}
                
                # Get current state
                current_state = await input_el.is_checked()
                desired_state = normalized in truthy_values
                
                # Only act if we need to change the state
                if current_state != desired_state:
                    max_retries = 3
                    
                    for attempt in range(max_retries):
                        try:
                            if desired_state:
                                await input_el.check()
                            else:
                                await input_el.uncheck()
                            
                            # Wait longer for UI to update
                            await asyncio.sleep(1.0)
                            
                            # Verify the change worked
                            new_state = await input_el.is_checked()
                            if new_state == desired_state:
                                print(f"{'Checked' if desired_state else 'Unchecked'} checkbox {input_id}")
                                break
                        except Exception as retry_error:
                            print(f"Attempt {attempt+1} failed: {retry_error}")
                            await asyncio.sleep(1.5)  # Longer wait between retries
                    else:
                        print(f"Warning: Failed to {'check' if desired_state else 'uncheck'} checkbox {input_id} after {max_retries} attempts")
                else:
                    print(f"Checkbox {input_id} already in desired state: {desired_state}")
                return

            # Handle spinbutton (number inputs)
            if input_type == "spinbutton":
                if isinstance(response, str) and response.isdigit():
                    response = int(response)
                await input_el.fill(str(response))
                print(f"Filled spinbutton {input_id} with: {response}")
                return

            print(f"Unhandled element type: {input_tag}/{input_type} for {input_id}")

            # End timing for successfully processed questions
            if question and question != "UNLABELED":
                self._end_question_timing(question, input_id, response)

        except Exception as e:
            print(f"Error filling element {input_id}: {e}")
            # End timing even for failed questions
            if question and question != "UNLABELED":
                self._end_question_timing(question, input_id, f"ERROR: {str(e)}")

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
            
            checkbox_inside = await selected_option.query_selector('input[type="checkbox"]')
            if checkbox_inside:
                if(await checkbox_inside.is_checked()):
                    print(f"Checkbox already checked for option: {selected_text}")
                else:
                    await checkbox_inside.check()
                    print(f"Checked checkbox for option: {selected_text}")
            else:
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
            await asyncio.sleep(0.1)
            await input_el.click()
            await asyncio.sleep(0.7)
            
            listbox = await self.page.query_selector('div[visibility="opened"]')
            if listbox:
                li_elements = await listbox.query_selector_all('li')
                for li in li_elements:
                    text = await li.text_content()
                    if text and (text.lower() == response.lower() or response.lower() in text.lower()):
                        await li.click()
                        print(f"Selected option: {text}")
                        await asyncio.sleep(0.5)
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
        """Save collected application data to JSON files"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Save extracted elements (all elements found)
            extracted_filename = f"{self.company}_extracted_elements_{timestamp}_run{self.run_number:03d}.json"
            extracted_filepath = self.current_run_dir / extracted_filename
            
            extracted_summary = {
                "timestamp": datetime.now().isoformat(),
                "company": self.company,
                "url" : self.url,
                "run_number": self.run_number,
                "total_extracted_elements": len(self.extracted_elements),
                "extracted_elements": self.extracted_elements
            }
            
            with open(extracted_filepath, 'w', encoding='utf-8') as f:
                json.dump(extracted_summary, f, indent=2, ensure_ascii=False)
            
            # Save filled elements (elements with responses)
            filled_filename = f"{self.company}_filled_elements_{timestamp}_run{self.run_number:03d}.json"
            filled_filepath = self.current_run_dir / filled_filename
            
            # Get timing summary
            timing_summary = self.get_timing_summary()
            
            filled_summary = {
                "timestamp": datetime.now().isoformat(),
                "company": self.company,
                "run_number": self.run_number,
                "total_extracted_elements": len(self.extracted_elements),
                "total_filled_elements": len(self.filled_elements),
                "timing_profile": timing_summary,  # Add timing information
                "extracted_elements": self.extracted_elements,
                "filled_elements": self.filled_elements
            }
            
            # Also save a separate timing report
            timing_filename = f"{self.company}_timing_profile_{timestamp}_run{self.run_number:03d}.json"
            timing_filepath = self.current_run_dir / timing_filename
            
            with open(timing_filepath, 'w', encoding='utf-8') as f:
                json.dump(timing_summary, f, indent=2, ensure_ascii=False)
            
            with open(filled_filepath, 'w', encoding='utf-8') as f:
                json.dump(filled_summary, f, indent=2, ensure_ascii=False)
            
            print(f"Extracted elements saved to: {extracted_filepath}")
            print(f"Filled elements saved to: {filled_filepath}")
            print(f"Timing profile saved to: {timing_filepath}")
            print(f"Company: {self.company}")
            print(f"Run number: {self.run_number}")
            print(f"Total extracted elements: {len(self.extracted_elements)}")
            print(f"Total filled elements: {len(self.filled_elements)}")
            print(f"Total questions with timing: {timing_summary['total_questions']}")
            if timing_summary['total_questions'] > 0:
                print(f"Average time per question: {timing_summary['average_time_readable']}")
                print(f"Total time spent on questions: {timing_summary['total_time_readable']}")
            
            return str(filled_filepath)
            
        except Exception as e:
            print(f"Error saving application data: {e}")
            return ""

    async def close_browser(self) -> None:
        """Close the browser"""
        if self.browser:
            await self.browser.close()
            print("Browser closed")