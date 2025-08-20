
import asyncio
import json
import os
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path

import openai
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from dotenv import load_dotenv

from authentication import Authentication
from processors import FormProcessor
from utils import FormUtils

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
        
        self.company_urls = {
            "nvidia": "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/US%2C-CA%2C-Santa-Clara/Senior-AI-and-ML-Engineer---AI-for-Networking_JR2000376/apply/applyManually?q=ml+enginer",
            "salesforce": "https://salesforce.wd12.myworkdayjobs.com/en-US/External_Career_Site/job/Singapore---Singapore/Senior-Manager--Solution-Engineering--Philippines-_JR301876/apply/applyManually",
            "hitachi": "https://hitachi.wd1.myworkdayjobs.com/en-US/hitachi/job/Alamo%2C-Tennessee%2C-United-States-of-America/Project-Engineer_R0102918/apply/applyManually",
            "icf": "https://icf.wd5.myworkdayjobs.com/en-US/ICFExternal_Career_Site/job/Reston%2C-VA/Senior-Paid-Search-Manager_R2502057/apply/applyManually",
            "harris": "https://harriscomputer.wd3.myworkdayjobs.com/en-US/1/job/Florida%2C-United-States/Vice-President-of-Sales_R0030918/apply/applyManually",
            "walmart":"https://walmart.wd5.myworkdayjobs.com/en-US/WalmartExternal/job/Sherbrooke%2C-QC/XMLNAME--CAN--Self-Checkout-Attendant_R-2263567-1/apply/applyManually"
        }
        
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)
        self.current_run_dir = self.logs_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.current_run_dir.mkdir(exist_ok=True)
        
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

    async def submit_form(self) -> bool:
        """Submit the current form"""
        try:
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
            
            summary = {
                "timestamp": datetime.now().isoformat(),
                "total_questions": len(self.application_data),
                "application_data": self.application_data
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            
            print(f"Application data saved to: {filepath}")
            return str(filepath)
            
        except Exception as e:
            print(f"Error saving application data: {e}")
            return ""

    async def close_browser(self) -> None:
        """Close the browser"""
        if self.browser:
            await self.browser.close()
            print("Browser closed")

    async def run(self, company: str, auth_type: int = 1):
        """Run the full job application process."""
        await self.initialize_browser()
        await self.navigate_to_job(company)

        auth = Authentication(self.page, self.user_data)
        if not await auth.handle_authentication(auth_type):
            print("Authentication failed.")
            await self.close_browser()
            return

        print("Authentication successful!")
        
        await asyncio.sleep(10)  # Wait for page to load after authentication

        utils = FormUtils(self.page, self.client)
        processor = FormProcessor(self.page, self.user_data, utils)

        # Process the first page sections
        print("Processing initial application sections...")
        main_page = await self.page.query_selector('div[data-automation-id="applyFlowPage"]')
        
        if not main_page:
            print("Main page container not found")
            await self.close_browser()
            return

        print("Main page container found, proceeding with section processing")

        await processor.process_personal_information_section()

        await asyncio.sleep(5)  # Wait for personal info section to process

        # Find all sections in the application - EXACT original logic
        sections = await main_page.query_selector_all('div[role="group"][aria-labelledby]')
        print(f"Found {len(sections)} sections to process")
        
        for section in sections:
            aria_labelledby = await section.get_attribute('aria-labelledby')
            if not aria_labelledby:
                print("Section without aria-labelledby found, skipping")
                continue

            print(f"Processing section: {aria_labelledby}")

        for section in sections:
            aria_labelledby = await section.get_attribute('aria-labelledby')
            if not aria_labelledby:
                continue

            print(f"\n=== Processing section: {aria_labelledby} ===")

            if any(keyword in aria_labelledby.lower() for keyword in ["work", "experience", "history"]):
                print("Processing work experience section")
                await processor.process_experience_section(section)
            elif any(keyword in aria_labelledby.lower() for keyword in ["education"]):
                print("Processing education section")
                await processor.process_education_section(section)
            elif any(keyword in aria_labelledby.lower() for keyword in ["language"]):
                print("Processing language section")
                await processor.process_language_section(section)
            elif any(keyword in aria_labelledby.lower() for keyword in ["skill"]):
                print("Processing skills section")
                await processor.process_skills_section(section)
            elif any(keyword in aria_labelledby.lower() for keyword in ["resume", "document"]):
                print("Processing resume section")
                await processor.process_resume_section(section)
            else:
                print(f"Unknown section type: {aria_labelledby}")
                await processor.process_generic_section(aria_labelledby)
        
        await asyncio.sleep(5)  # Wait for personal info section to process
        
        # Click the first Next button
        print("Looking for first Next button...")
        next_button = await self.page.query_selector('button[data-automation-id="pageFooterNextButton"]')
        if next_button:
            print("Clicking first Next button...")
            await next_button.click()
            await asyncio.sleep(5)
        
        # Process remaining pages
        print("Processing remaining application pages...")
        page_count = 1
        
        while True:
            print(f"\n=== Processing Page {page_count} ===")
            
            try:
                # Process sections on the new page
                await asyncio.sleep(5)
                await processor.process_later_sections()
                
                page_count += 1
                
                next_button = await self.page.query_selector('button[data-automation-id="pageFooterNextButton"]')
                
                if not next_button:
                    print("No Next button found - reached the end of the application")
                    break
                
                # Check if the button is visible
                is_visible = await next_button.is_visible()
                
                if not is_visible:
                    print("Next button found but not clickable - reached the end of the application")
                    break
                
                print("Next button found, clicking to proceed to next page...")
                await next_button.click()
                            
            except Exception as e:
                print(f"Error processing page {page_count}: {str(e)}")
                break
        
        print(f"Completed processing {page_count} pages total")

        self.application_data = processor.application_data
        saved_file = self.save_application_data()
        if saved_file:
            print(f"Application data successfully saved to: {saved_file}")
        
        await self.close_browser()
        print("\n=== Job Application Completed Successfully ===")

if __name__ == '__main__':
    async def main():
        bot = JobApplicationBot()
        
        # Get authentication choice
        print("Authentication Options:")
        print("1. Sign In")
        print("2. Sign Up")
        
        try:
            auth_choice = int(input("Enter 1 for sign in or 2 for sign up: "))
        except ValueError:
            auth_choice = 1
            print("Invalid input, defaulting to sign in")

        # Get company choice
        print("\nAvailable companies:")
        company_list = list(bot.company_urls.keys())
        for i, company in enumerate(company_list, 1):
            print(f"{i}. {company.title()}")

        try:
            company_choice = int(input("Select company (1-6): "))
            selected_company = company_list[company_choice - 1]
        except (ValueError, IndexError):
            selected_company = "harris"  # Default
            print("Invalid input, defaulting to Harris")
        
        print(f"Selected company: {selected_company.title()}")
        print("\n=== Starting Job Application Automation ===")
        
        await bot.run(company=selected_company, auth_type=auth_choice)
    
    asyncio.run(main())
