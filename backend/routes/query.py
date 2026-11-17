import os
import requests
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
import hashlib

from database import get_db
from auth_dependency import get_current_user
from models import User
from dsl.validator import validate_dsl
from execution.query_executor import execute_query
from cache import get_cache, set_cache

router = APIRouter(prefix="/query", tags=["query"])

# Default to localhost for development, but in K8s this will be a service URL
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://localhost:8001")

class QueryRequest(BaseModel):
    query: str

@router.post("/")
def run_query(request: QueryRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    clean_query = request.query.strip()
    if not clean_query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Simple cache key generation
    query_hash = hashlib.md5(clean_query.lower().encode()).hexdigest()
    cache_key = f"query_{query_hash}"
    
    cached_result = get_cache(cache_key)
    if cached_result:
        return cached_result
        
    dsl_dict = None
    try:
        # 1. Call LLM Microservice with 15-second socket timeout
        try:
            response = requests.post(
                f"{LLM_SERVICE_URL}/parse",
                json={"query": clean_query},
                timeout=15.0
            )
            if response.status_code == 200:
                dsl_dict = response.json()
            else:
                # If LLM microservice errors, fall back to in-process parser
                from llm.parser import parse_query_to_dsl
                dsl_dict = parse_query_to_dsl(clean_query)
        except Exception:
            # If LLM microservice times out or is unreachable, fall back to in-process parser
            try:
                from llm.parser import parse_query_to_dsl
                dsl_dict = parse_query_to_dsl(clean_query)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Query parsing failed: {e}"
                )
        
        if not dsl_dict:
            raise HTTPException(status_code=400, detail="Failed to parse query to DSL.")

        # 2. Validate DSL (Local validation for extra safety)
        dsl = validate_dsl(dsl_dict)
        
        # 3. Compile and Execute against database
        result = execute_query(db, dsl)
        
        # 4. Cache the result for 5 minutes
        set_cache(cache_key, result, ttl=300)
        
        return result
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=str(e))
