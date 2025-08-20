
import asyncio
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, date
from playwright.async_api import Page, ElementHandle
from utils import FormUtils

class FormProcessor:
    """Handles processing of different sections of the job application form."""

    def __init__(self, page: Page, user_data: Dict[str, Any], utils: FormUtils):
        """
        Initialize the FormProcessor.

        Args:
            page: The Playwright page object.
            user_data: The user's profile data.
            utils: An instance of FormUtils.
        """
        self.page = page
        self.user_data = user_data
        self.utils = utils
        self.application_data = []

    async def _process_radio_group_as_whole(self, main_page, inputs, radio_indices: List[int]) -> None:
        """Process an entire radio group as a single unit for AI decision"""
        try:
            if not radio_indices:
                return
            
            first_radio = inputs[radio_indices[0]]
            group_question = await self.utils._get_radio_group_question(first_radio)
            
            group_label, aria_labelledby = await self.utils._get_group_label_and_aria(first_radio)
            
            options = []
            radio_elements = []
            
            for radio_index in radio_indices:
                radio_el = inputs[radio_index]
                option_label = await self.utils._get_nearest_label_text(radio_el) or f'Option {len(options) + 1}'
                options.append(option_label)
                radio_elements.append(radio_el)
            
            print(f"Processing radio group: '{group_question}' with options: {options}")
            
            element_info = {
                'question': group_question,
                'input_type': 'radio_group',
                'input_tag': 'radio_group',
                'input_id': f"radio_group_{await first_radio.get_attribute('name')}",
                'aria_labelledby': aria_labelledby,
                'options': options,
                'placeholder': None,
                'required': await first_radio.get_attribute('required'),
                'role': 'radiogroup'
            }
            
            full_key = f"[{group_question}, {element_info['input_id']}, radio_group, {aria_labelledby}, radio_group]"
            
            ai_values, _ = await self.utils._get_ai_response_without_skipping(
                self.user_data.get('personal_information', {}), 
                [element_info]
            )
            
            response = ai_values.get(full_key, 'SKIP')
            
            if response and response != 'SKIP':
                selected_index = -1
                
                for i, option in enumerate(options):
                    if option.lower().strip() == response.lower().strip():
                        selected_index = i
                        break
                
                if selected_index == -1:
                    for i, option in enumerate(options):
                        if response.lower() in option.lower() or option.lower() in response.lower():
                            selected_index = i
                            break
                
                if selected_index >= 0:
                    selected_radio = radio_elements[selected_index]
                    selected_option = options[selected_index]
                    await selected_radio.check()
                    print(f"✅ Selected radio option: '{selected_option}' for question: '{group_question}'")
                else:
                    print(f" Could not find matching option for AI response: '{response}' in {options}")
            else:
                print(f"⏭ Skipping radio group: '{group_question}' (AI said SKIP)")
                
        except Exception as e:
            print(f"Error processing radio group: {e}")

    async def process_personal_information_section(self) -> None:
        """Process personal information section with radio/checkbox group handling"""
        print("Processing Personal Information section")
        
        await asyncio.sleep(5)
        
        main_page = await self.page.query_selector('div[data-automation-id="applyFlowPage"]')
        INPUT_SELECTOR = 'button, input, select, textarea, [role="button"]'
        
        i = 0
        prev_answered_question = None
    
        while True:
            inputs = await main_page.query_selector_all(INPUT_SELECTOR)
            
            if i >= len(inputs):
                print("Reached end of inputs, exiting loop")
                break
                
            input_el = inputs[i]
            
            input_id = await input_el.get_attribute('data-automation-id') or await input_el.get_attribute('aria-haspopup') or 'unknown'
            input_type = await input_el.get_attribute('type') or 'unknown'
            
            if input_id in ["pageFooterBackButton", "backToJobPosting"]:
                i += 1
                continue
            
            if input_id == "pageFooterNextButton":
                print("Clicking Next button")
                await input_el.click()
                break
            
            group_label, aria_labelledby = await self.utils._get_group_label_and_aria(input_el)
            question = await self.utils._get_nearest_label_text(input_el) or group_label or 'UNLABELED'
            
            role = await input_el.get_attribute('role')
            placeholder = await input_el.get_attribute('placeholder')
            required = await input_el.get_attribute('required')

            if input_type == "radio":
                radio_indices = await self.utils._get_radio_group(main_page, inputs, i, input_el)
                num_radios = len(radio_indices) if radio_indices else 0
                if radio_indices:
                    print(f"Found radio group with indices: {radio_indices}")
                    await self._process_radio_group_as_whole(main_page, inputs, radio_indices)
                    i += num_radios
                    continue

            if question != 'UNLABELED' and question == prev_answered_question:
                print(f"⏩ Skipping duplicate question at index {i}: '{question}'")
                i += 1
                continue
            
            print("--------------------------------")
            print(f"Processing element {i}: Input ID: {input_id}, Question: {question}, Type: {input_type}")
            
            if role == "spinbutton":
                input_type = "spinbutton"
            
            tag_name = await input_el.evaluate("(el) => el.tagName.toLowerCase()")
            if tag_name and tag_name.lower() == 'textarea':
                input_type = 'textarea'
            input_tag = tag_name
            
            element_dir = await input_el.get_attribute('dir')
            if element_dir and element_dir != 'ltr':
                print(f"Skipping element {input_id} with dir={element_dir}")
                i += 1
                continue
            
            options = await self.utils._get_element_options(input_el, input_tag, input_type)
            
            print(f"Processing form element: {question}")
            
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
            
            full_key = f"[{element_info['question']}, {element_info['input_id']}, {element_info['input_type']}, {element_info['aria_labelledby']}, {element_info['input_tag']}]"
            ai_values, _ = await self.utils._get_ai_response_for_section_for_personal_information(
                self.user_data.get('personal_information', {}), 
                [element_info]
            )
            response = ai_values.get(full_key, 'SKIP')
            
            print(f"AI response for field '{question}': {response}")
            
            await self.utils._fill_single_element(
                input_el, 
                input_id, 
                input_type, 
                input_tag, 
                response,
                options,
                question
            )
            
            if question != 'UNLABELED':
                prev_answered_question = question
            
            i += 1
            
            await asyncio.sleep(0.5)

    async def process_later_sections(self) -> None:
        """Process later sections with exact original logic"""
        print("Processing Later sections")
        
        await asyncio.sleep(5)
        
        main_page = await self.page.query_selector('div[data-automation-id="applyFlowPage"]')
        INPUT_SELECTOR = 'button, input, select, textarea, [role="button"]'
        
        i = 0
        prev_answered_question = None
        prev_type = None
    
        while True:
            inputs = await main_page.query_selector_all(INPUT_SELECTOR)
            
            if i >= len(inputs):
                print("Reached end of inputs, exiting loop")
                break
                
            input_el = inputs[i]
            
            input_id = await input_el.get_attribute('data-automation-id') or await input_el.get_attribute('aria-haspopup') or 'unknown'
            input_type = await input_el.get_attribute('type') or 'unknown'
            
            if input_id in ["pageFooterBackButton", "backToJobPosting"]:
                i += 1
                continue
            
            if input_id == "pageFooterNextButton":
                print("Clicking Next button")
                await input_el.click()
                break
            
            group_label, aria_labelledby = await self.utils._get_group_label_and_aria(input_el)
            question = await self.utils._get_nearest_label_text(input_el) or group_label or 'UNLABELED'
            
            role = await input_el.get_attribute('role')
            placeholder = await input_el.get_attribute('placeholder')
            required = await input_el.get_attribute('required')
            
            # Handle date fields like in the original
            if input_id and "date" in input_id.lower():
                date_mapping = {
                    'birthdate-datesectionmonth-input': "01",
                    'birthdate-datesectionday-input': "01", 
                    'birthdate-datesectionyear-input': "1990",
                    'availabilitydate-datesectionmonth-input': datetime.now().strftime("%m"),
                    'availabilitydate-datesectionday-input': datetime.now().strftime("%d"),
                    'availabilitydate-datesectionyear-input': str(datetime.now().year)
                }
                
                response = date_mapping.get(input_id.lower())
                if response:
                    await self.utils._fill_single_element(
                        input_el,
                        input_id,
                        input_type,
                        'input',
                        response,
                        options=None,
                        question=f"Date field - {input_id}"
                    )
                    print(f"Filled date field {input_id} with: {response}")
                    i += 1
                    continue
                    
            print(f"Previous question: {prev_answered_question}, Current question: {question}, previous type : {prev_type}, current_role : {role}")
            # Skip duplicate questions - EXACT original condition
            if question != 'UNLABELED' and question == prev_answered_question and role != "spinbutton" and prev_type == "button":
                print(f"⏩ Skipping duplicate question at index {i}: '{question}'")
                i += 1
                continue

    async def process_experience_section(self, section) -> None:
        """Process work experience section with add functionality"""
        print("Processing Work Experience section")
        await self._handle_section_with_add(section, "experience")

    async def process_education_section(self, section) -> None:
        """Process education section with add functionality"""
        print("Processing Education section")
        await self._handle_section_with_add(section, "education")

    async def process_language_section(self, section) -> None:
        """Process language section with add functionality"""
        print("Processing Language section")
        await self._handle_section_with_add(section, "language")

    async def process_skills_section(self, section) -> None:
        """Process skills section"""
        print("Processing Skills section")
        
        form_elements = await self.utils._extract_form_elements_from_section(section)
        
        if not form_elements:
            print("No form elements found in skills section")
            return

        skills_data = {
            "technical_skills": self.user_data.get('technical_skills', {}),
            "skills": self.user_data.get('personal_information', {}).get('professional_info', {}).get('skills', [])
        }
        
        ai_response, key_mapping = await self.utils._get_ai_response_for_section(skills_data, form_elements)
        
        await self.utils._fill_form_elements(ai_response, key_mapping)

    async def process_resume_section(self, section) -> None:
        """Process resume upload section"""
        print("Processing Resume section")
        
        file_input = await section.query_selector('input[type="file"]')
        if file_input:
            resume_path = self.user_data.get('documents', {}).get('resume_path', '')
            if resume_path and os.path.exists(resume_path):
                await file_input.set_input_files([resume_path])
                print(f"Uploaded resume: {resume_path}")
            else:
                print("Resume file not found or not specified")

    async def process_disability_section(self) -> None:
        """Process disability disclosure section"""
        print("Processing Disability section")
        
        checkboxes = await self.page.query_selector_all('input[type="checkbox"]')
        
        for checkbox in checkboxes:
            label_handle = await checkbox.evaluate_handle('el => el.closest("label")')
            label = label_handle.as_element() if label_handle else None
            label_text = await label.text_content() if label else ''
            
            if label_text and "do not have a disability" in label_text.lower():
                if not await checkbox.is_checked():
                    await checkbox.click()
                    print(f"Selected: {label_text.strip()}")
                break
        
        current_date = datetime.now()
        date_fields = [
            ("selfIdentifiedDisabilityData--dateSignedOn-dateSectionMonth-input", f"{current_date.month:02d}"),
            ("selfIdentifiedDisabilityData--dateSignedOn-dateSectionDay-input", f"{current_date.day:02d}"),
            ("selfIdentifiedDisabilityData--dateSignedOn-dateSectionYear-input", str(current_date.year)),
        ]
        
        for field_id, default_value in date_fields:
            selector = f'input[id="{field_id}"]'
            field = await self.page.query_selector(selector)
            if field and not await field.input_value():
                await field.fill(default_value)

    async def process_generic_section(self, section_name: str, data=None) -> None:
        """Process any generic section using AI"""
        print(f"Processing Generic section: {section_name}")
        
        form_elements = await self.utils._extract_form_elements_from_section(self.page)
        
        if not form_elements:
            print(f"No form elements found in {section_name} section")
            return
        if data is None:
            data = self.user_data

        ai_response, key_mapping = await self.utils._get_ai_response_for_section(data, form_elements)

        await self.utils._fill_form_elements(ai_response, key_mapping)

    async def _handle_section_with_add(self, section, section_type: str) -> None:
        """Handle sections that have add functionality (experience, education, language) - EXACT original logic"""
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

                group_label, aria_labelledby = await self.utils._get_group_label_and_aria(input_el)
                question = await self.utils._get_nearest_label_text(input_el) or 'UNLABELED'

                input_type = await input_el.get_attribute('type') or 'unknown'
                role = await input_el.get_attribute('role')
                placeholder = await input_el.get_attribute('placeholder')
                required = await input_el.get_attribute('required')

                if role == "spinbutton":
                    input_type = "spinbutton"

                # Enhanced duplicate question detection like in the notebook - EXACT original logic
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
                options = await self.utils._get_element_options(input_el, input_tag, input_type)

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
                    print(f"  - {field['question']} ({field['input_type']})")

                # Get AI response for this panel
                ai_response, key_mapping = await self.utils._get_ai_response_for_section(item_data, panel_elements)

                # Fill the form elements
                await self.utils._fill_form_elements(ai_response, key_mapping)
                
                await asyncio.sleep(2)
            else:
                print(f"No relevant panel elements found for {section_type} {i + 1}")

            await asyncio.sleep(2)
