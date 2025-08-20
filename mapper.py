"""
Element Mapper - AI Response Generator

Simple mapper that takes extracted elements and generates AI responses using OpenAI.

Author: Automated Job Application System
Version: 1.0
"""

import asyncio
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
import traceback
import openai
from dotenv import load_dotenv
import re


PROMPT_RULES = """
You receive:
USER_PROFILE (candidate JSON) and one FORM_ELEMENT (single field).
Task: return SAME FORM_ELEMENT plus key "response". Output ONLY one JSON object.

OUTPUT RULES:
- Preserve all original keys/values unchanged; just add "response".
- No markdown, no arrays unless rules require, no extra keys, no trailing commas.
- Use "SKIP" only if answering would be uninformed or risky.

DECISION LOGIC ORDER:
1. Single-select options: choose exactly one valid option (avoid placeholders like "Select One" unless only safe choice).
2. Multi-value (skills/technolog*/tool*/language(s)/competenc*/proficienc*/certification):
   If clearly multi-select: response = JSON array of distinct profile-derived items (no fabrication, 3–12 typical).
3. Yes/No / compliance (eligibility, sponsorship, prior employment, restrictions, convictions):
   Defaults if absent: Eligible=Yes (if profile location supports), Sponsorship=No (unless visa hint), Prior employment=No, Restrictions=No, Convictions=No.
4. Demographic / voluntary: choose neutral privacy option if available; never guess sensitive data.
5. Dates:
   - Full date: "MM / DD / YYYY".
   - Standalone month field: "MM".
   - Standalone year field: "YYYY".
   - Do not fabricate missing chronology; prefer SKIP if uncertain.
6. Address / contact: use exact profile values; match option spelling; SKIP if uncertain.
7. Education: map degree to provided option; no fake GPA.
8. Languages/proficiency: consistent high level only if profile supports; arrays only when field expects list.
9. Descriptions / summaries: reuse profile text; concise (<=3 sentences); no invention.
10. Unknown / decorative / upload triggers: SKIP.
11. Search fields: provide best exact profile term if clearly valid; else SKIP.
12. Duplicates: keep consistent unless multiple distinct entries exist in profile.
13. Boolean formatting: use "Yes"/"No" if that style appears; raw true/false only if obviously expected.
14. No fabrication of employers, dates, degrees, certifications, statuses.
15. Sanitize: plain JSON value (string/number/boolean/array). No markdown.

Edge:
- Prefer "No" over "N/A" unless truly not applicable.
- Disability / veteran sets: pick privacy or neutral if present.

Return only the updated JSON object with added "response".
""".strip()


class ElementMapper:
    """Maps extracted form elements to AI-generated responses"""
    
    def __init__(self, user_profile_path: str = "data/user_profile.json"):
        """Initialize the mapper with user profile"""
        load_dotenv()
        self.user_profile_path = user_profile_path
        self.user_data = self._load_user_profile()
        self.client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.max_concurrency = int(os.getenv("MAPPER_MAX_CONCURRENCY", "3"))
    
    def _load_user_profile(self) -> Dict[str, Any]:
        """Load user profile from JSON file"""
        try:
            with open(self.user_profile_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading user profile: {e}")
            return {}
    
    def _sanitize_model_output(self, content: str) -> str:
        """
        Best-effort cleanup to turn model output into valid JSON object.
        Removes markdown fences, language tags, trailing commas, and commentary lines.
        """
        if not content:
            return "{}"
        # Strip code fences
        if "```" in content:
            parts = content.split("```")
            # choose segment with most braces
            content = max(parts, key=lambda p: p.count("{") + p.count("}"))
        content = content.strip()
        # Remove leading 'json' tag
        if content.lower().startswith("json"):
            content = content[4:].lstrip()
        # Drop comment / prose lines at start/end
        cleaned = []
        for line in content.splitlines():
            ls = line.lstrip()
            if not ls:
                continue
            if ls.startswith(("#", "//")):
                continue
            if ls.lower().startswith(("return updated object", "output:", "note:", "answer:")):
                continue
            cleaned.append(line)
        content = "\n".join(cleaned).strip()
        # If multiple JSON objects concatenated, pick first full object
        first_brace = content.find("{")
        last_brace = content.rfind("}")
        if first_brace != -1 and last_brace != -1:
            content = content[first_brace:last_brace+1]
        # Remove trailing commas before } or ]
        content = re.sub(r',(\s*[}\]])', r'\1', content)
        return content.strip()
    
    async def _generate_single_element(self, element: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI response for a single form element."""
        try:
            profile_min = json.dumps(self.user_data, separators=(",", ":"))
            element_json = json.dumps(element, separators=(",", ":"))
            
            # question processing
            print("Question :", element.get("question", "Unknown"))
            
            prompt = (
                f"{PROMPT_RULES}\n\nUSER_PROFILE:\n{profile_min}\n\nFORM_ELEMENT:\n"
                f"{element_json}\n"
            )

            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You output ONLY valid JSON objects. No markdown."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=4000
            )
            content = response.choices[0].message.content or ""
            print("Raw AI response:", content)
            raw = content
            content = self._sanitize_model_output(content)
            print("Sanitized AI response:", content)

            # Ensure it's an object (not array)
            if content.strip().startswith('['):
                # If model wrongly returned array, try first object
                try:
                    arr = json.loads(content)
                    if isinstance(arr, list) and arr:
                        parsed = arr[0]
                    else:
                        raise ValueError("Unexpected array structure")
                except Exception:
                    raise json.JSONDecodeError("Unexpected array output", content, 0)
            else:
                parsed = json.loads(content)

            if not isinstance(parsed, dict):
                raise ValueError("Model did not return JSON object")

            # Guarantee original keys present
            for k, v in element.items():
                if k not in parsed:
                    parsed[k] = v

            if "response" not in parsed:
                parsed["response"] = "SKIP"

            return parsed

        except Exception as e:
            print(f"[single-element] Error: {e}")
            # Fallback with SKIP
            return {**element, "response": "SKIP"}

    async def generate_ai_responses(self, extracted_elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Strictly sequential processing: one element at a time (no concurrency).
        """
        results: List[Dict[str, Any]] = []
        total = len(extracted_elements)
        for i, el in enumerate(extracted_elements):
            print(f"  -> Mapping element {i+1}/{total}")
            res = await self._generate_single_element(el)
            results.append(res)
        return results
    
    async def process_extracted_elements_file(self, extracted_file_path: str) -> Dict[str, Any]:
        """Process an extracted elements JSON file and generate mapped responses"""
        try:
            # Load extracted elements
            with open(extracted_file_path, 'r') as f:
                extracted_data = json.load(f)
            
            # Extract the elements list
            elements = extracted_data.get('extracted_elements', [])
            
            print(f"Processing {len(elements)} elements...")
            
            # Generate mapped elements with AI responses
            mapped_elements = await self.generate_ai_responses(elements)
            
            # Create output structure
            output_data = {
                "timestamp": datetime.now().isoformat(),
                "source_file": extracted_file_path,
                "company": extracted_data.get('company', 'unknown'),
                "run_number": extracted_data.get('run_number', 1),
                "total_elements": len(mapped_elements),
                "mapped_elements": mapped_elements
            }
            
            return output_data
            
        except Exception as e:
            print(f"Error processing file {extracted_file_path}: {e}")
            traceback.print_exc()
            return {
                "timestamp": datetime.now().isoformat(),
                "source_file": extracted_file_path,
                "error": str(e),
                "mapped_elements": []
            }
    
    def save_mapped_elements(self, mapped_data: Dict[str, Any], output_path: str) -> None:
        """Save mapped elements to JSON file"""
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(mapped_data, f, indent=2)
            
            print(f"Mapped elements saved to: {output_path}")
            
        except Exception as e:
            print(f"Error saving mapped elements: {e}")


async def main(extracted_elements_path: str, output_path: Optional[str] = None) -> str:
    """Main function to process extracted elements and generate mapped responses"""
    # Initialize mapper
    mapper = ElementMapper()
    
    # Generate output path if not provided
    if output_path is None:
        input_path = Path(extracted_elements_path)
        output_dir = input_path.parent
        input_filename = input_path.stem
        
        # Replace 'extracted' with 'mapped' in filename
        output_filename = input_filename.replace('extracted', 'mapped')
        if 'extracted' not in input_filename:
            output_filename = f"mapped_{input_filename}"
        
        output_path = output_dir / f"{output_filename}.json"
    
    # Process the file
    print(f"Processing: {extracted_elements_path}")
    mapped_data = await mapper.process_extracted_elements_file(extracted_elements_path)
    
    # Save results
    mapper.save_mapped_elements(mapped_data, str(output_path))
    
    print(f"Processing complete!")
    print(f"Total elements processed: {mapped_data.get('total_elements', 0)}")
    
    return str(output_path)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python mapper.py <extracted_elements_path> [output_path]")
        sys.exit(1)
    
    extracted_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Run the mapping process
    result_path = asyncio.run(main(extracted_path, output_path))
    print(f"Mapped elements saved to: {result_path}")