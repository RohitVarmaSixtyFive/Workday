#!/usr/bin/env python3
"""
Test script to verify timing functionality
"""

import asyncio
import json
from final import JobApplicationBot

async def test_timing():
    """Test the timing functionality without running a full application"""
    bot = JobApplicationBot()
    
    # Simulate some questions being processed
    print("Testing timing functionality...")
    
    # Simulate question identification and filling
    bot._start_question_timing("What is your first name?", "firstName")
    await asyncio.sleep(1.5)  # Simulate time to fill
    bot._end_question_timing("What is your first name?", "firstName", "John")
    
    bot._start_question_timing("What is your email address?", "email")
    await asyncio.sleep(2.3)  # Simulate time to fill
    bot._end_question_timing("What is your email address?", "email", "john@example.com")
    
    bot._start_question_timing("Select your experience level", "experience")
    await asyncio.sleep(0.8)  # Simulate time to fill
    bot._end_question_timing("Select your experience level", "experience", "Senior")
    
    bot._start_question_timing("Upload your resume", "resume")
    await asyncio.sleep(3.1)  # Simulate time to upload
    bot._end_question_timing("Upload your resume", "resume", "resume.pdf")
    
    # Get timing summary
    timing_summary = bot.get_timing_summary()
    
    print("\n" + "="*50)
    print("TIMING SUMMARY TEST")
    print("="*50)
    print(f"Total questions: {timing_summary['total_questions']}")
    print(f"Total time: {timing_summary['total_time_readable']}")
    print(f"Average time: {timing_summary['average_time_readable']}")
    print(f"Fastest question: {timing_summary['fastest_question_ms']/1000:.2f}s")
    print(f"Slowest question: {timing_summary['slowest_question_ms']/1000:.2f}s")
    
    print("\nDETAILED TIMINGS:")
    for timing in timing_summary['timings']:
        print(f"  {timing['question']}: {timing['duration_readable']} -> {timing['response']}")
    
    # Test JSON serialization
    print(f"\nTiming data JSON:\n{json.dumps(timing_summary, indent=2)}")
    
    print("\n✅ Timing functionality test completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_timing())
