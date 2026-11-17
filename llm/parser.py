import google.generativeai as genai
import os
import re
from dotenv import load_dotenv
import json
from dsl.validator import ALLOWED_FIELDS

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if api_key and api_key != "your_gemini_api_key_here":
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        print(f"Failed to configure Gemini API: {e}")

SECTOR_MAP = {
    "tech": "Technology",
    "technology": "Technology",
    "healthcare": "Healthcare",
    "health": "Healthcare",
    "finance": "Financial Services",
    "financials": "Financial Services",
    "financial services": "Financial Services",
    "consumer": "Consumer Cyclical",
    "consumer cyclical": "Consumer Cyclical",
    "industrials": "Industrials",
    "energy": "Energy",
    "utilities": "Utilities",
    "real estate": "Real Estate",
    "communication": "Communication Services",
    "basic materials": "Basic Materials",
}

def rule_based_fallback_parser(query: str) -> dict:
    """Deterministic fallback parser for common financial queries when LLM is unavailable or rate-limited."""
    q_lower = query.strip().lower()
    filters = []
    
    # 1. Sector matching
    for key, sector_name in SECTOR_MAP.items():
        pattern = r"\b" + re.escape(key) + r"\b"
        if re.search(pattern, q_lower):
            filters.append({"field": "sector", "operator": "=", "value": sector_name})
            break
            
    # 2. PE ratio matching: e.g. "pe < 30", "pe_ratio <= 25", "p/e > 15"
    pe_match = re.search(r"(?:pe|pe_ratio|p/e)\s*(=|<=|>=|<|>)\s*(\d+(?:\.\d+)?)", q_lower)
    if pe_match:
        op = pe_match.group(1)
        val = float(pe_match.group(2))
        filters.append({"field": "pe_ratio", "operator": op, "value": val})
        
    # 3. EPS matching: e.g. "eps > 5"
    eps_match = re.search(r"\beps\s*(=|<=|>=|<|>)\s*(\d+(?:\.\d+)?)", q_lower)
    if eps_match:
        op = eps_match.group(1)
        val = float(eps_match.group(2))
        filters.append({"field": "eps", "operator": op, "value": val})
        
    # 4. Market Cap matching: e.g. "market cap > 50B", "market_cap < 100B"
    cap_match = re.search(r"(?:market\s*cap|market_cap)\s*(=|<=|>=|<|>)\s*(\d+(?:\.\d+)?)\s*([tbmk])?", q_lower)
    if cap_match:
        op = cap_match.group(1)
        val = float(cap_match.group(2))
        unit = (cap_match.group(3) or "").lower()
        if unit == "t":
            val *= 1e12
        elif unit == "b":
            val *= 1e9
        elif unit == "m":
            val *= 1e6
        elif unit == "k":
            val *= 1e3
        filters.append({"field": "market_cap", "operator": op, "value": val})

    # 5. Revenue growth matching: e.g. "growth > 10", "revenue growth > 15"
    growth_match = re.search(r"(?:revenue\s*growth|growth)\s*(=|<=|>=|<|>)\s*(\d+(?:\.\d+)?)", q_lower)
    if growth_match:
        op = growth_match.group(1)
        val = float(growth_match.group(2))
        filters.append({"field": "revenue_growth", "operator": op, "value": val})

    if filters:
        return {"filters": filters, "logic": "AND"}
    return None

def parse_query_to_dsl(query: str) -> dict:
    prompt = f"""
    You are a financial query parser. Convert the following natural language query into a structured DSL JSON format.
    
    ### Guidelines:
    1. Return ONLY valid JSON.
    2. Do not include markdown code blocks (e.g., ```json).
    3. Do not include any explanations or extra text.
    4. Allowed fields: {', '.join(ALLOWED_FIELDS)}
    5. Allowed operators: =, <, >, <=, >=
    6. Logic must be "AND" or "OR".
    7. For time-based queries, use "time_filter".
    
    ### DSL Schema:
    {{
      "filters": [
        {{
          "field": "string",
          "operator": "string",
          "value": number or string
        }}
      ],
      "logic": "AND" | "OR",
      "time_filter": {{
        "type": "quarter",
        "value": "YYYY-QX"
      }} // Optional.
    }}

    ### Examples:
    - "Tech stocks with PE < 20": 
      {{"filters": [{{"field": "sector", "operator": "=", "value": "Technology"}}, {{"field": "pe_ratio", "operator": "<", "value": 20}}], "logic": "AND"}}
    
    - "Companies with net income > 5B in 2024-Q1":
      {{"filters": [{{"field": "net_income", "operator": ">", "value": 5000000000}}], "logic": "AND", "time_filter": {{"type": "quarter", "value": "2024-Q1"}}}}

    Query: {query}
    """
    
    llm_error = None
    if api_key and api_key != "your_gemini_api_key_here":
        try:
            model = genai.GenerativeModel("gemini-flash-latest")
            # 12-second explicit timeout prevents socket hang on 429 quota backoff
            response = model.generate_content(prompt, request_options={"timeout": 12.0})
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:-3].strip()
            elif text.startswith("```"):
                text = text[3:-3].strip()
            return json.loads(text)
        except Exception as e:
            llm_error = e
            print(f"Gemini API generation failed/rate-limited: {e}. Trying fallback parser...")
    else:
        llm_error = RuntimeError("GEMINI_API_KEY is not configured.")

    # Execute fallback parser
    fallback_result = rule_based_fallback_parser(query)
    if fallback_result:
        return fallback_result

    # If fallback cannot parse and LLM threw error, raise error
    if llm_error:
        raise RuntimeError(f"Error communicating with Gemini API: {llm_error}")
    raise ValueError("Unable to parse query with either Gemini or fallback parser.")
