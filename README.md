# Workday Job Application Automation System

An intelligent automation system for applying to jobs on Workday-based platforms with batch processing capabilities, AI-powered form filling, and comprehensive timing analytics.

## Features

- **Batch Processing**: Apply to multiple jobs simultaneously (3-4 concurrent applications)
- **AI-Powered Form Filling**: Uses OpenAI to intelligently fill forms based on your profile
- **Timing Analytics**: Detailed profiling of how long each question takes to fill
- **Comprehensive Logging**: Complete application data and timing saved to JSON files
- **Error Handling**: Robust error handling with graceful failures
- **Resume Management**: Automatic resume upload and document handling
- **Multi-Company Support**: Pre-configured URLs for major companies

## Prerequisites

### Software Requirements

1. **Python 3.8+**
2. **Node.js** (for Playwright browser automation)
3. **Git** (for version control)

### Python Dependencies

Install the required packages:

```bash
pip install -r requirements.txt
```

**Required packages:**
- `playwright>=1.40.0` - Browser automation
- `openai>=1.0.0` - AI form filling
- `python-dotenv>=1.0.0` - Environment variable management
- `asyncio` - Asynchronous programming (built-in)
- `json` - JSON handling (built-in)
- `pathlib` - Path handling (built-in)

### Browser Setup

Install Playwright browsers:

```bash
playwright install chromium
```

## Configuration

### 1. Environment Variables

Create a `.env` file in the project root:

```bash
OPENAI_API_KEY=your_openai_api_key_here
```

**Getting OpenAI API Key:**
1. Go to [OpenAI API Keys](https://platform.openai.com/api-keys)
2. Create a new API key
3. Copy and paste it into your `.env` file

### 2. User Profile Configuration

Update `data/user_profile_temp.json` with your information:

```json
{
  "personal_information": {
    "first_name": "Your First Name",
    "last_name": "Your Last Name",
    "email": "your.email@example.com",
    "phone": "+1234567890",
    "address": {
      "street": "123 Main St",
      "city": "Your City",
      "state": "Your State",
      "zip_code": "12345",
      "country": "United States"
    }
  },
  "work_experience": [
    {
      "company": "Previous Company",
      "position": "Your Position",
      "start_date": "2020-01",
      "end_date": "2023-12",
      "description": "Description of your role and achievements"
    }
  ],
  "education": [
    {
      "institution": "Your University",
      "degree": "Bachelor of Science",
      "field_of_study": "Computer Science",
      "graduation_date": "2020-05"
    }
  ],
  "skills": [
    "Python",
    "JavaScript",
    "Machine Learning",
    "Data Analysis"
  ]
}
```

## Usage

### Running Batch Applications

1. **Basic Batch Run:**
   ```bash
   python batch_apply.py
   ```

2. **The system will prompt you for:**
   - Number of concurrent applications (recommended: 3-4)
   - Starting job index (which job to start from)
   - Number of jobs to process

3. **Example interaction:**
   ```
   Found 15 job applications to process
   How many applications to run simultaneously? (recommended: 3-4): 3
   Start from which job? (1-15): 1
   How many jobs to process? (max 15): 10
   ```

### Running Single Applications

For testing or single applications:

```bash
python main.py
```

## Output and Logging

### Directory Structure

```
logs/
├── run_20250820_143022_batch_job_1_001/
│   ├── Company_extracted_elements_20250820_143045_run001.json
│   ├── Company_filled_elements_20250820_143045_run001.json
│   └── Company_timing_profile_20250820_143045_run001.json
├── run_20250820_143022_batch_job_2_002/
└── ...
```

### Generated Files

1. **Extracted Elements**: All form fields found on the page
2. **Filled Elements**: Form fields that were successfully filled
3. **Timing Profile**: Detailed timing analytics for each question


## Features

### Error Handling
- Graceful handling of authentication failures
- Automatic retry mechanisms for transient errors
- Comprehensive error logging
- Cleanup of browser resources

### Monitoring
- Real-time progress updates
- Per-application statistics
- Keyboard interrupt handling (Ctrl+C)
- Final batch statistics summary

## Troubleshooting

### Common Issues

1. **OpenAI API Key Error**
   - Verify your API key in `.env` file
   - Check API key permissions and billing

2. **Browser Launch Issues**
   - Run `playwright install chromium`
   - Check if Chromium is properly installed

3. **Authentication Failures**
   - Verify job URLs are direct application links

4. **Timeout Issues**
   - Reduce concurrent applications
   - Check internet connection stability
   - Verify Workday site accessibility

### Debug Mode

For debugging, modify the browser launch parameters in `final.py`:

```python
await bot.initialize_browser(headless=False, slow_mo=1000)
```

### Log Analysis

Check the generated JSON files for:
- Failed form submissions
- Timing bottlenecks
- Skipped questions
- Error patterns