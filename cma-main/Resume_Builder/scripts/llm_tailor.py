"""llm_tailor.py — Batch AI Tailoring for Resumes with Rate-Limit Resilience.

Batches all projects and experiences into a single Gemini API call to stay well
within free tier rate limits (1 API call per resume generation instead of 5+).
"""

import json
import time
import copy
from google import genai
from scripts.utils import get_config, load_prompts


def _call_gemini_with_retry(client, model_name: str, prompt: str, max_retries: int = 3) -> str:
    """Call Gemini API with automatic exponential backoff on all exceptions."""
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(model=model_name, contents=prompt)
            return response.text.strip()
        except Exception as e:
            wait_time = 6.0 * (attempt + 1)
            print(f"[RateLimit] Gemini API error ({e}). Waiting {wait_time:.1f}s before retry ({attempt + 1}/{max_retries})...")
            time.sleep(wait_time)

    # Last try after backoff
    response = client.models.generate_content(model=model_name, contents=prompt)
    return response.text.strip()


def tailor_resume(
    selected: dict,
    jd_data: dict,
    master_data: dict,
    prompt_id: str = "star_metrics",
    custom_prompt: str = "",
) -> dict:
    """
    Tailor all selected projects and experiences in a SINGLE batch API call.

    Returns a copy of `selected` with bullet_points rewritten.
    """
    tailored = copy.deepcopy(selected)

    config = get_config()
    client = genai.Client(api_key=config["gemini_api_key"])

    role         = jd_data.get("role", "Software Engineer Intern")
    company      = jd_data.get("company", "")
    summary      = jd_data.get("summary", "")
    keywords_str = ", ".join(jd_data.get("keywords", [])[:12])
    tech_str     = ", ".join(jd_data.get("tech_stack", [])[:10])
    context      = f"Applying for {role}{' at ' + company if company else ''}. {summary}"

    # Build input payload of items to rewrite
    items_to_rewrite = {
        "projects": [
            {
                "id": idx,
                "name": p.get("name", "Project"),
                "bullets": p.get("bullet_points", [])
            }
            for idx, p in enumerate(tailored.get("projects", []))
        ],
        "experiences": [
            {
                "id": idx,
                "title": f"{e.get('role', 'Role')} at {e.get('company', 'Company')}",
                "bullets": e.get("bullet_points", [])
            }
            for idx, e in enumerate(tailored.get("experiences", []))
        ]
    }

    # Load custom or selected prompt strategy
    prompts = load_prompts()
    if custom_prompt.strip():
        strategy_instructions = custom_prompt.strip()
    elif prompt_id in prompts:
        strategy_instructions = prompts[prompt_id].get("template", "")
    else:
        strategy_instructions = "Use strong action verbs and quantified impact (STAR formula)."

    batch_prompt = f"""
You are an elite tech resume writer. Rewrite the bullet points for the candidate's projects and experiences to tailor them for the target role.

Target Role: {role}
Company: {company}
Key JD Keywords: {keywords_str}
Required Technologies: {tech_str}
Context: {context}

Strategy Guidelines:
{strategy_instructions}

Strict Rules:
1. Keep EVERY factual number, metric, and core technology truthful. Do not invent achievements.
2. Naturally weave in relevant JD keywords where accurate.
3. Keep each bullet point between 18 and 30 words so it fits on a single line on the printed resume.
4. Return ONLY a valid JSON object matching the exact schema below. No markdown or commentary.

Input Items to Rewrite:
{json.dumps(items_to_rewrite, indent=2)}

Required Output JSON Schema:
{{
  "projects": [
    {{"id": 0, "bullets": ["Rewritten bullet 1", "Rewritten bullet 2", "Rewritten bullet 3"]}}
  ],
  "experiences": [
    {{"id": 0, "bullets": ["Rewritten bullet 1", "Rewritten bullet 2"]}}
  ]
}}
"""

    try:
        raw_output = _call_gemini_with_retry(
            client=client,
            model_name=config["gemini_model"],
            prompt=batch_prompt,
        )

        if raw_output.startswith("```"):
            raw_output = raw_output.split("```")[1]
            if raw_output.startswith("json"):
                raw_output = raw_output[4:]

        parsed = json.loads(raw_output.strip())

        # Map rewritten bullets back to projects
        for proj_res in parsed.get("projects", []):
            p_id = proj_res.get("id")
            if p_id is not None and 0 <= p_id < len(tailored.get("projects", [])):
                new_bullets = proj_res.get("bullets", [])
                if isinstance(new_bullets, list) and len(new_bullets) > 0:
                    tailored["projects"][p_id]["bullet_points"] = new_bullets

        # Map rewritten bullets back to experiences
        for exp_res in parsed.get("experiences", []):
            e_id = exp_res.get("id")
            if e_id is not None and 0 <= e_id < len(tailored.get("experiences", [])):
                new_bullets = exp_res.get("bullets", [])
                if isinstance(new_bullets, list) and len(new_bullets) > 0:
                    tailored["experiences"][e_id]["bullet_points"] = new_bullets

    except Exception as e:
        print(f"Warning: Batch tailoring encountered exception ({e}). Using original high-quality bullets as fallback.")

    return tailored
