#!/usr/bin/env python3
"""
Batch job application script that runs multiple applications simultaneously

This script reads job URLs from jobagent.jobs.json and processes
3-4 applications concurrently to speed up the automation process.
"""

import asyncio
import json
import sys
import signal
from final import JobApplicationBot

# Global counters
GLOBAL_STATS = {
    'successful_applications': 0,
    'failed_applications': 0,
    'submitted_applications': 0,  # New counter for actual submissions
    'total_processed': 0
}

def print_final_stats():
    """Print final statistics"""
    print(f"\n{'='*50}")
    print(f"FINAL BATCH PROCESS STATISTICS")
    print(f"{'='*50}")
    print(f"Total applications processed: {GLOBAL_STATS['total_processed']}")
    print(f"Successfully submitted: {GLOBAL_STATS['submitted_applications']}")
    print(f"Completed without submission: {GLOBAL_STATS['successful_applications'] - GLOBAL_STATS['submitted_applications']}")
    print(f"Failed applications: {GLOBAL_STATS['failed_applications']}")
    print(f"Success rate: {(GLOBAL_STATS['submitted_applications'] / max(1, GLOBAL_STATS['total_processed'])) * 100:.1f}%")
    print(f"{'='*50}")

def signal_handler(signum, frame):
    """Handle keyboard interrupt gracefully"""
    print(f"\n\nKeyboard interrupt received. Stopping batch process...")
    print_final_stats()
    sys.exit(0)

# Set up signal handler for graceful shutdown
signal.signal(signal.SIGINT, signal_handler)

async def process_single_application(url, semaphore, application_index):
    """Process a single job application with 10-minute timeout"""
    async with semaphore:  # Limit concurrent applications
        bot = JobApplicationBot()
        was_submitted = False
        
        try:
            print(f"\n=== Starting Application {application_index + 1}: {url} ===")
            print(f"[App {application_index + 1}] Timeout set to 15 minutes")
            
            # Wrap the entire process in a timeout
            async with asyncio.timeout(900):  # 900 seconds = 15 minutes
                # Add the custom URL to the bot's company_urls
                custom_company_name = f"batch_job_{application_index + 1}"
                bot.company_urls[custom_company_name] = url

                # Set the company for proper logging
                bot.set_company(custom_company_name)
                # Initialize browser
                print(f"[App {application_index + 1}] Initializing browser...")
                await bot.initialize_browser(headless=False)  # Use headless for batch processing

                # Navigate to job
                print(f"[App {application_index + 1}] Navigating to job page...")
                await bot.navigate_to_job(custom_company_name)
                
                # Additional steps for custom links before authentication
                print(f"[App {application_index + 1}] Waiting for page to load and clicking apply buttons...")
                await bot.page.wait_for_load_state('networkidle')
                await asyncio.sleep(0.5)
                
                try:
                    apply_button = await bot.page.query_selector('a[data-automation-id="adventureButton"]')
                    if apply_button:
                        await apply_button.click()
                        await asyncio.sleep(1)
                    apply_manually_button = await bot.page.query_selector('a[data-automation-id="applyManually"]')
                    if apply_manually_button:
                        await apply_manually_button.click()
                        await asyncio.sleep(0.5)

                    await bot.page.wait_for_load_state('networkidle')
                except Exception as e:
                    print(f"[App {application_index + 1}] Apply buttons not found or already on application page: {e}")

                # Handle authentication (sign up only)
                print(f"[App {application_index + 1}] Handling authentication (sign up)...")
                auth_success = await bot.handle_authentication(2)  # 2 for sign up
                if not auth_success:
                    print(f"[App {application_index + 1}] Authentication failed")
                    return False, False

                print(f"[App {application_index + 1}] Authentication successful!")

                await asyncio.sleep(10)  # Wait for page to load after authentication

                # Process the first page sections
                print(f"[App {application_index + 1}] Processing initial application sections...")
                success = await process_application_sections(bot, application_index + 1)

                await asyncio.sleep(5)  # Wait for personal info section to process

                if not success:
                    print(f"[App {application_index + 1}] Failed to process initial sections")
                    return False, False

                # Click the first Next button
                print(f"[App {application_index + 1}] Looking for first Next button...")
                next_button = await bot.page.query_selector('button[data-automation-id="pageFooterNextButton"]')
                if next_button:
                    print(f"[App {application_index + 1}] Clicking first Next button...")
                    await next_button.click()
                    await asyncio.sleep(5)
                else:
                    print(f"[App {application_index + 1}] No Next button found on first page")

                # Process remaining pages
                print(f"[App {application_index + 1}] Processing remaining application pages...")
                was_submitted = await process_remaining_pages(bot, application_index + 1)

                # Save application data to JSON
                print(f"[App {application_index + 1}] Saving application data...")
                saved_file = bot.save_application_data()
                if saved_file:
                    print(f"[App {application_index + 1}] Application data successfully saved to: {saved_file}")
                    
                    # Print timing summary for this application
                    timing_summary = bot.get_timing_summary()
                    if timing_summary['total_questions'] > 0:
                        print(f"[App {application_index + 1}] Timing Summary:")
                        print(f"[App {application_index + 1}]   - Questions processed: {timing_summary['total_questions']}")
                        print(f"[App {application_index + 1}]   - Total time: {timing_summary['total_time_readable']}")
                        print(f"[App {application_index + 1}]   - Average per question: {timing_summary['average_time_readable']}")
                        print(f"[App {application_index + 1}]   - Fastest: {timing_summary['fastest_question_ms']/1000:.2f}s")
                        print(f"[App {application_index + 1}]   - Slowest: {timing_summary['slowest_question_ms']/1000:.2f}s")

                if was_submitted:
                    print(f"\n=== Application {application_index + 1} SUBMITTED Successfully ===")
                else:
                    print(f"\n=== Application {application_index + 1} Completed (No Submission) ===")
                
                return True, was_submitted

        except asyncio.TimeoutError:
            print(f"[App {application_index + 1}] TIMEOUT: Application exceeded 15-minute limit - terminating")
            return False, False
            
        except Exception as e:
            print(f"[App {application_index + 1}] Error during job application process: {str(e)}")
            import traceback
            print(f"[App {application_index + 1}] Full traceback: {traceback.format_exc()}")
            return False, False
        
        finally:
            # Clean up browser resources
            if bot.browser:
                print(f"[App {application_index + 1}] Cleaning up browser resources...")
                try:
                    await bot.browser.close()
                except:
                    pass  # Ignore cleanup errors


async def process_application_sections(bot, app_num):
    """Process all sections on the current application page"""
    await asyncio.sleep(10)
    main_page = await bot.page.query_selector('div[data-automation-id="applyFlowPage"]')
    
    if not main_page:
        print(f"[App {app_num}] Main page container not found")
        return False
    
    print(f"[App {app_num}] Main page container found, proceeding with section processing")

    await bot._process_personal_information_section(main_page)

    await bot.page.wait_for_load_state('networkidle') 
    await asyncio.sleep(5)  # Wait for personal info section to process

    # Find all sections in the application
    sections = await main_page.query_selector_all('div[role="group"][aria-labelledby]')
    print(f"[App {app_num}] Found {len(sections)} sections to process")
    
    for section in sections:
        aria_labelledby = await section.get_attribute('aria-labelledby')
        if not aria_labelledby:
            continue

        print(f"[App {app_num}] Processing section: {aria_labelledby}")

        if any(keyword in aria_labelledby.lower() for keyword in ["work", "experience", "history"]):
            print(f"[App {app_num}] Processing work experience section")
            await bot._process_experience_section(section)
        elif any(keyword in aria_labelledby.lower() for keyword in ["education"]):
            print(f"[App {app_num}] Processing education section")
            await bot._process_education_section(section)
        elif any(keyword in aria_labelledby.lower() for keyword in ["language"]):
            print(f"[App {app_num}] Processing language section")
            await bot._process_language_section(section)
        elif any(keyword in aria_labelledby.lower() for keyword in ["skill"]):
            print(f"[App {app_num}] Processing skills section")
            await bot._process_skills_section(section)
        elif any(keyword in aria_labelledby.lower() for keyword in ["resume", "document"]):
            print(f"[App {app_num}] Processing resume section")
            await bot._process_resume_section(section)
        elif any(keyword in aria_labelledby.lower() for keyword in ["website", "portfolio"]):
            continue  # Skip website/portfolio sections for now
        else:
            print(f"[App {app_num}] Unknown section type: {aria_labelledby}")
            await bot._process_generic_section(section, aria_labelledby)
    
    return True


async def process_remaining_pages(bot, app_num):
    """Process remaining application pages until no more Next buttons are found"""
    page_count = 1
    was_submitted = False
    
    while True:
        print(f"[App {app_num}] Processing Page {page_count}")
        
        try:
            # Process sections on the new page
            await asyncio.sleep(5)
            await bot._process_later_sections(bot.page)
            
            page_count += 1
            
            next_button = await bot.page.query_selector('button[data-automation-id="pageFooterNextButton"]')
            
            if not next_button:
                print(f"[App {app_num}] No Next button found - reached the end of the application")
                break
            
            # Check if the button is visible and enabled
            is_visible = await next_button.is_visible()
            
            if not is_visible:
                print(f"[App {app_num}] Next button found but not clickable - reached the end of the application")
                break
            
            print(f"[App {app_num}] Next button found, clicking to proceed to next page...")
            # Check if text content of next button indicates submission
            next_button_text = await next_button.text_content()
            if next_button_text and "submit" in next_button_text.lower():
                print(f"[App {app_num}] 🎉 SUBMISSION DETECTED! Button text: {next_button_text.strip()}")
                was_submitted = True
            else:
                print(f"[App {app_num}] Next button text: {next_button_text.strip() if next_button_text else 'No text content'}")
            
            await next_button.click()
            
            # If this was a submit button, break after clicking
            if was_submitted:
                await asyncio.sleep(3)  # Wait for submission to complete
                print(f"[App {app_num}] 🎉 APPLICATION SUBMITTED SUCCESSFULLY!")
                break
                        
        except Exception as e:
            print(f"[App {app_num}] Error processing page {page_count}: {str(e)}")
            break
    
    print(f"[App {app_num}] Completed processing {page_count} pages total")
    return was_submitted


async def main():
    """Main function to run batch job applications"""
    
    # Load job URLs from JSON file
    try:
        with open('jobagent.jobs.json', 'r') as f:
            jobs_data = json.load(f)
        
        job_urls = [job['url'] for job in jobs_data if 'url' in job]
        print(f"Loaded {len(job_urls)} job URLs from jobagent.jobs.json")
        
    except FileNotFoundError:
        print("Error: jobagent.jobs.json file not found!")
        return
    except json.JSONDecodeError:
        print("Error: Invalid JSON format in jobagent.jobs.json!")
        return
    
    if not job_urls:
        print("No job URLs found in the JSON file!")
        return
    
    # Get user preferences
    print(f"\nFound {len(job_urls)} job applications to process")
    
    try:
        concurrent_apps = int(input("How many applications to run simultaneously? (recommended: 3-4): "))
        concurrent_apps = max(1, min(concurrent_apps, 6))  # Limit between 1-6
    except ValueError:
        concurrent_apps = 3
        print("Invalid input, defaulting to 3 concurrent applications")
    
    try:
        start_index = int(input(f"Start from which job? (1-{len(job_urls)}): ")) - 1
        start_index = max(0, min(start_index, len(job_urls) - 1))
    except ValueError:
        start_index = 0
        print("Invalid input, starting from job 1")
    
    try:
        num_jobs = int(input(f"How many jobs to process? (max {len(job_urls) - start_index}): "))
        num_jobs = max(1, min(num_jobs, len(job_urls) - start_index))
    except ValueError:
        num_jobs = min(10, len(job_urls) - start_index)
        print(f"Invalid input, defaulting to {num_jobs} jobs")
    
    # Select the subset of jobs to process
    selected_jobs = job_urls[start_index:start_index + num_jobs]
    
    print(f"\n=== Starting Batch Job Application Process ===")
    print(f"Processing {len(selected_jobs)} jobs with {concurrent_apps} concurrent applications")
    print(f"Starting from job {start_index + 1}")
    print(f"Press Ctrl+C anytime to stop and see statistics")
    
    # Create semaphore to limit concurrent applications
    semaphore = asyncio.Semaphore(concurrent_apps)
    
    # Process jobs in batches
    batch_size = concurrent_apps
    
    try:
        for i in range(0, len(selected_jobs), batch_size):
            batch = selected_jobs[i:i + batch_size]
            batch_start_index = start_index + i
            
            print(f"\n--- Processing Batch {i//batch_size + 1} ---")
            print(f"Jobs {batch_start_index + 1} to {batch_start_index + len(batch)}")
            
            # Create tasks for this batch
            tasks = [
                process_single_application(url, semaphore, batch_start_index + j)
                for j, url in enumerate(batch)
            ]
            
            # Run batch concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count results
            for result in results:
                GLOBAL_STATS['total_processed'] += 1
                
                if isinstance(result, Exception):
                    GLOBAL_STATS['failed_applications'] += 1
                    print(f"Application failed with exception: {result}")
                elif isinstance(result, tuple) and len(result) == 2:
                    success, was_submitted = result
                    if success:
                        GLOBAL_STATS['successful_applications'] += 1
                        if was_submitted:
                            GLOBAL_STATS['submitted_applications'] += 1
                    else:
                        GLOBAL_STATS['failed_applications'] += 1
                else:
                    GLOBAL_STATS['failed_applications'] += 1
            
            print(f"Batch {i//batch_size + 1} completed")
            print(f"Current stats - Submitted: {GLOBAL_STATS['submitted_applications']}, "
                  f"Failed: {GLOBAL_STATS['failed_applications']}, "
                  f"Total: {GLOBAL_STATS['total_processed']}")
            
            # Small delay between batches
            if i + batch_size < len(selected_jobs):
                print("Waiting 5 seconds before next batch...")
                await asyncio.sleep(5)
    
    except KeyboardInterrupt:
        print(f"\n\nBatch process interrupted by user.")
    
    except Exception as e:
        print(f"\n\nUnexpected error in batch process: {e}")
    
    finally:
        print_final_stats()


if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())
