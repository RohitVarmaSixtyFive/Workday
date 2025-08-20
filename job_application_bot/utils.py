import asyncio
import json
import os
from typing import Dict, List, Any, Optional, Tuple
from playwright.async_api import Page, ElementHandle
import openai

class FormUtils:
    """Utility functions for form handling."""

    def __init__(self, page: Page, client: openai.AsyncOpenAI):
        self.page = page
        self.client = client
        self.previous_question = None
        self.previous_was_listbox = False

    def reset_duplicate_tracking(self) -> None:
        """Reset the duplicate question tracking for new applications"""
        self.previous_question = None
        self.previous_was_listbox = False
        print("Reset duplicate question tracking")

    async def _get_radio_group(self, main_page, inputs, current_index, current_radio) -> Optional[List[int]]:
        """Get all radio button indices that belong to the same group"""
        try:
            current_name = await current_radio.get_attribute('name')
            if not current_name:
                return None
            
            group_question = await self._get_radio_group_question(current_radio)
            
            radio_indices = []
            
            for i, input_el in enumerate(inputs):
                input_type = await input_el.get_attribute('type')
                if input_type == 'radio':
                    radio_name = await input_el.get_attribute('name')
                    if radio_name == current_name:
                        radio_indices.append(i)
            
            return radio_indices if len(radio_indices) > 1 else None
            
        except Exception as e:
            print(f"Error getting radio group: {e}")
            return None

    async def _get_radio_group_question(self, input_el) -> str:
        """Get the question text for a radio button group"""
        try:
            question = await input_el.evaluate('''
                el => {
                    let group = el.closest("fieldset, [role='group']");
                    if (group) {
                        let legend = group.querySelector("legend");
                        if (legend && legend.textContent) return legend.textContent.trim();
                    }
                    return 'Radio Question';
                }
            ''')
            return question or 'Radio Question'
        except:
            return 'Radio Question'

    async def _get_nearest_label_text(self, element) -> Optional[str]:
        """Get the nearest label text for a form element"""
        try:
            element_id = await element.get_attribute('id')
            if element_id:
                label_elem = await self.page.query_selector(f'label[for="{element_id}"]')
                if label_elem:
                    return (await label_elem.text_content() or "").strip()
            
            parent_label_handle = await element.evaluate_handle('el => el.closest("label")')
            if parent_label_handle.as_element():
                return (await parent_label_handle.as_element().text_content() or "").strip()

            aria_labelledby = await element.get_attribute('aria-labelledby')
            if aria_labelledby:
                label_element = await self.page.query_selector(f'#{aria_labelledby}')
                if label_element:
                    return (await label_element.text_content() or "").strip()

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
            if input_tag == "button" and await input_el.get_attribute('aria-haspopup') == "listbox":
                return await self._get_listbox_options(input_el)
            return None
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

            await input_el.click()
            await asyncio.sleep(0.5)
            return options
        except:
            return []

    async def _get_ai_response_without_skipping(self, current_data: Dict[str, Any], panel_elements: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Get AI response for form fields using OpenAI without skipping fields."""
        return await self._get_ai_response(current_data, panel_elements, skip_allowed=False)

    async def _get_ai_response_for_section_for_personal_information(self, current_data: Dict[str, Any], panel_elements: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Get AI response for personal information section."""
        return await self._get_ai_response(current_data, panel_elements, skip_allowed=False)

    async def _get_ai_response_for_section(self, current_data: Dict[str, Any], panel_elements: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Get AI response for a generic section."""
        return await self._get_ai_response(current_data, panel_elements, skip_allowed=True)

    async def _get_ai_response(self, current_data: Dict[str, Any], panel_elements: List[Dict[str, Any]], skip_allowed: bool) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Generic method to get AI response for form fields using OpenAI."""
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

            skip_instruction = 'If a field is not relevant, map it to "SKIP".' if skip_allowed else 'do not SKIP any field, fill up the most accurate response you can come up with based on user profile'

            prompt = f"""
You are helping fill a job application form. You are mapping user profile data to a web form.
You are given:
- User profile data (JSON)
- A list of form fields from the application (labels, field types, options)

Return a JSON dictionary mapping the EXACT "full_key" values to appropriate values. {skip_instruction}

CRITICAL: You MUST use the EXACT "full_key" value as the key in your response JSON.

Data from User Profile:
{json.dumps(current_data, indent=2)}

Form Fields:
{json.dumps(form_fields, indent=2)}

Respond ONLY with a valid JSON object.
"""
            
            response = await self.client.chat.completions.create(
                model="o4-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.choices[0].message.content.strip()
            
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            ai_response = json.loads(content)
            return ai_response, key_mapping
            
        except Exception as e:
            print(f"Error in _get_ai_response: {e}")
            return {}, {}

    async def _fill_form_elements(self, ai_response: Dict[str, Any], key_mapping: Dict[str, Any]) -> None:
        """Fill form elements based on AI response"""
        for full_key, response_value in ai_response.items():
            if full_key in key_mapping:
                element_info = key_mapping[full_key]
                try:
                    if element_info['input_type'] == 'radio_group':
                        await self._fill_radio_group(element_info, response_value)
                    else:
                        await self._fill_single_element(
                            element_info['element'], 
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
        if response_value == "SKIP":
            return
        
        options = radio_group_info['options']
        elements = radio_group_info['elements']
        
        selected_index = -1
        for i, option in enumerate(options):
            if option.lower().strip() == response_value.lower().strip():
                selected_index = i
                break
        
        if selected_index == -1:
            for i, option in enumerate(options):
                if response_value.lower().strip() in option.lower().strip():
                    selected_index = i
                    break
        
        if 0 <= selected_index < len(elements):
            await elements[selected_index].check()

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
                # Add to application_data if it exists (this would be passed from processor)
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

    async def _extract_form_elements_from_section(self, section) -> List[Dict[str, Any]]:
        """Extract form elements from a specific section."""
        elements = []
        inputs = await section.query_selector_all('input, button, textarea, select')
        
        for input_el in inputs:
            element_info = await self._extract_element_info(input_el)
            if element_info:
                elements.append(element_info)
        
        return elements

    async def _extract_element_info(self, input_el) -> Optional[Dict[str, Any]]:
        """Extract information about a form element"""
        try:
            input_tag = await input_el.evaluate('el => el.tagName.toLowerCase()')
            input_type = await input_el.get_attribute('type') or 'unknown'
            input_id = await input_el.get_attribute('id') or 'unknown'
            
            question = await self._get_nearest_label_text(input_el)
            group_label, aria_labelledby = await self._get_group_label_and_aria(input_el)
            
            options = await self._get_element_options(input_el, input_tag, input_type)
            
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
