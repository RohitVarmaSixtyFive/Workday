#!/usr/bin/env python3
"""
Main script for automated job application using JobApplicationBot

This script runs the complete job application automation process,
including authentication, form filling, and navigation through
multiple application pages.
"""

import asyncio
from final import JobApplicationBot


async def process_application_sections(bot):
    """Process all sections on the current application page"""
    await asyncio.sleep(10)
    main_page = await bot.page.query_selector('div[data-automation-id="applyFlowPage"]')
    
    if not main_page:
        print("Main page container not found")
        return False
    
    print("Main page container found, proceeding with section processing")

    await bot._process_personal_information_section(main_page)

    await asyncio.sleep(5)  # Wait for personal info section to process

    # Find all sections in the application
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
            await bot._process_experience_section(section)
        elif any(keyword in aria_labelledby.lower() for keyword in ["education"]):
            print("Processing education section")
            await bot._process_education_section(section)
        elif any(keyword in aria_labelledby.lower() for keyword in ["language"]):
            print("Processing language section")
            await bot._process_language_section(section)
        elif any(keyword in aria_labelledby.lower() for keyword in ["skill"]):
            print("Processing skills section")
            await bot._process_skills_section(section)
        elif any(keyword in aria_labelledby.lower() for keyword in ["resume", "document"]):
            print("Processing resume section")
            await bot._process_resume_section(section)
        else:
            print(f"Unknown section type: {aria_labelledby}")
            await bot._process_generic_section(section, aria_labelledby)
    
    return True


async def process_remaining_pages(bot):
    """Process remaining application pages until no more Next buttons are found"""
    page_count = 1
    
    while True:
        print(f"\n=== Processing Page {page_count} ===")
        
        # Check if there's a Next button on the current page
        try:
            
            # Process sections on the new page
            await asyncio.sleep(5)

            await bot._process_later_sections(bot.page)
            
            page_count += 1
            
            next_button = await bot.page.query_selector('button[data-automation-id="pageFooterNextButton"]')
            
            if not next_button:
                print("No Next button found - reached the end of the application")
                break
            
            # Check if the button is visible and enabled
            is_visible = await next_button.is_visible()
            
            if not (is_visible):
                print("Next button found but not clickable - reached the end of the application")
                break
            
            print("Next button found, clicking to proceed to next page...")
            await next_button.click()
                        
        except Exception as e:
            print(f"Error processing page {page_count}: {str(e)}")
            # Try to continue anyway
            break
    
    print(f"Completed processing {page_count} pages total")


async def main():
    """Main function to run the job application automation"""
    bot = JobApplicationBot()
    
    try:
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
            company_choice = int(input("Select company (1-5): "))
            selected_company = company_list[company_choice - 1]
        except (ValueError, IndexError):
            selected_company = "harris"  # Default
            print("Invalid input, defaulting to Harris")
        
        bot.company = selected_company
        print(f"Selected company: {selected_company.title()}")

        print("\n=== Starting Job Application Automation ===")

        # Initialize browser
        print("Initializing browser...")
        await bot.initialize_browser(headless=False)

        # Navigate to job
        print(f"Navigating to {selected_company} job page...")
        await bot.navigate_to_job(selected_company)

        # Handle authentication
        print("Handling authentication...")
        auth_success = await bot.handle_authentication(auth_choice)
        if not auth_success:
            print("Authentication failed, exiting...")
            return

        print("Authentication successful!")

        await asyncio.sleep(10)  # Wait for page to load after authentication

        # Process the first page sections
        print("Processing initial application sections...")
        success = await process_application_sections(bot)

        await asyncio.sleep(5)  # Wait for personal info section to process

        if not success:
            print("Failed to process initial sections")
            return

        # Click the first Next button
        print("Looking for first Next button...")
        next_button = await bot.page.query_selector('button[data-automation-id="pageFooterNextButton"]')
        if next_button:
            print("Clicking first Next button...")
            await next_button.click()
            await asyncio.sleep(5)
        else:
            print("No Next button found on first page")

        # Process remaining pages
        print("Processing remaining application pages...")
        await process_remaining_pages(bot)

        # Save application data to JSON
        print("Saving application data...")
        saved_file = bot.save_application_data()
        if saved_file:
            print(f"Application data successfully saved to: {saved_file}")

        print("\n=== Job Application Completed Successfully ===")

    except Exception as e:
        print(f"Error during job application process: {str(e)}")
        raise
    
    finally:
        # Clean up browser resources
        if bot.browser:
            print("Cleaning up browser resources...")
            await bot.browser.close()


if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())
